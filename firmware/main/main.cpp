#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "esp_mac.h"
#include "esp_system.h"
#ifdef ESP_CON2_UNIFIED
#include "unified_controller.hpp"
#endif
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.hpp"
#include "switch2_pro.hpp"
#ifdef ESP_CON2_JOYCON2_DUAL
#include "dual_joycon.hpp"
#endif

#ifndef CONFIG_BT_CTRL_BLE_MIN_CONN_INTERVAL_ENABLE
#error "Update ESP-IDF: Switch 2 requires the official 5 ms BLE interval support."
#endif

using Report = espp::switch2::Pro2InputReport;
using Setter = void (Report::*)(bool);
// Bit order is shared with host/python/control.py; each STATE replaces all inputs.
constexpr std::array<Setter, 21> buttons = {
    &Report::set_a, &Report::set_b, &Report::set_x, &Report::set_y,
    &Report::set_l, &Report::set_r, &Report::set_zl, &Report::set_zr,
    &Report::set_minus, &Report::set_plus, &Report::set_lstick, &Report::set_rstick,
    &Report::set_up, &Report::set_down, &Report::set_left, &Report::set_right,
    &Report::set_home, &Report::set_capture, &Report::set_gl, &Report::set_gr,
    &Report::set_c};
constexpr unsigned valid_mask = (1u << 21) - 1;

static Report neutral() {
  Report report;
  report.set_power(9, false, true);
  report.set_left_stick(0, 0);
  report.set_right_stick(0, 0);
  return report;
}

static void reply(const char *message) {
  // Bound writes so unplugging the Mac cannot block the input watchdog.
  usb_serial_jtag_write_bytes(message, std::strlen(message), 0);
}

extern "C" void app_main() {
  espp::Nvs nvs;
  std::error_code ec;
  nvs.init(ec);
  if (ec) { std::printf("NVS initialization failed\n"); return; }
  usb_serial_jtag_driver_config_t usb = {.tx_buffer_size = 2048, .rx_buffer_size = 2048};
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
  // Combined firmware persists its mode; reboot prevents stale GATT registrations.
#ifdef ESP_CON2_UNIFIED
  const bool pro_mode = load_pro_mode();
#endif
#if defined(ESP_CON2_JOYCON2_RIGHT) || defined(ESP_CON2_JOYCON2_LEFT) || defined(ESP_CON2_JOYCON2_DUAL)
#ifdef ESP_CON2_JOYCON2_LEFT
  const char *device_name = "Joy-Con 2 (L)";
  constexpr uint8_t identity_offset = 0x80;
#elif defined(ESP_CON2_JOYCON2_DUAL)
#ifdef ESP_CON2_UNIFIED
  const char *device_name = pro_mode ? "Pro Controller" : "Joy-Con 2 (L+R)";
#else
  const char *device_name = "Joy-Con 2 (L+R)";
#endif
  // New identities invalidate the cached right-only GATT table from the previous experiment.
#ifdef ESP_CON2_UNIFIED
  const uint8_t identity_offset = pro_mode ? 0xa0 : 0x60;
#else
  constexpr uint8_t identity_offset = 0x60;
#endif
#else
  const char *device_name = "Joy-Con 2 (R)";
  constexpr uint8_t identity_offset = 0x40;
#endif
  // Retain the working public-address type while separating the Joy-Con identity.
  uint8_t bt_mac[6];
  ESP_ERROR_CHECK(esp_read_mac(bt_mac, ESP_MAC_BT));
#ifdef ESP_CON2_DUAL_BOOTSTRAP
  bt_mac[5] ^= 0x50;
  bt_mac[0] |= 0xc0;
#else
  bt_mac[5] ^= identity_offset;
#endif
  ESP_ERROR_CHECK(esp_iface_mac_addr_set(bt_mac, ESP_MAC_BT));
  const auto verbosity = espp::Logger::Verbosity::INFO;
#else
  const char *device_name = "Pro Controller";
  const auto verbosity = espp::Logger::Verbosity::WARN;
#endif
#ifdef ESP_CON2_JOYCON2_DUAL
#ifdef ESP_CON2_UNIFIED
  UnifiedController controller(pro_mode);
#else
  DualJoyCon controller;
#endif
#else
  espp::Switch2Pro controller({.device_name = device_name,
                              .wake_console_on_boot_enabled = false,
                              .log_level = verbosity});
#endif
  if (!controller.init()) { reply("@ERR controller initialization\n"); return; }
  auto report = neutral();
  controller.set_input_report(report);
  int64_t deadline = 0;
  std::string line;
  bool overflow = false;
  reply("@READY esp-con2\n");
  while (true) {
#ifdef ESP_CON2_JOYCON2_DUAL
    controller.tick();
#endif
    char data[128];
    const int count = usb_serial_jtag_read_bytes(data, sizeof(data), pdMS_TO_TICKS(10));
    for (int i = 0; i < count; ++i) {
      const char ch = data[i];
      if (ch == '\r') continue;
      if (ch != '\n') {
        if (line.size() < 160 && !overflow) line += ch;
        else overflow = true;
        continue;
      }
      if (overflow) reply("@ERR line too long\n");
#ifdef ESP_CON2_UNIFIED
      else if (line == "MODE pro" || line == "MODE joycon") {
        controller.set_input_report(neutral());
        if (!save_pro_mode(line == "MODE pro")) reply("@ERR mode persistence\n");
        else { reply("@OK\n"); vTaskDelay(pdMS_TO_TICKS(100)); esp_restart(); }
      }
#endif
      else if (line == "STATUS") {
        char status[384];
        // Expose live advertising state without changing the host protocol prefix.
        std::snprintf(status, sizeof(status), "@STATUS device=esp-con2 protocol=1 paired=%d connected=%d streaming=%d advertising=%d name=%s\n",
                      controller.is_paired(), controller.is_connected(), controller.is_input_streaming(),
                      NimBLEDevice::getAdvertising()->isAdvertising(), device_name);
#ifdef ESP_CON2_JOYCON2_DUAL
        // Distinguish subscribed links from an input path that has stopped handing off reports.
        const auto used = std::strlen(status);
        std::snprintf(status + used - 1, sizeof(status) - used + 1,
          " left_tx=%lu right_tx=%lu left_tx_age_ms=%lld right_tx_age_ms=%lld\n",
          static_cast<unsigned long>(controller.left.input_handoffs()),
          static_cast<unsigned long>(controller.right.input_handoffs()),
          static_cast<long long>((esp_timer_get_time() - controller.left.last_handoff_us()) / 1000),
          static_cast<long long>((esp_timer_get_time() - controller.right.last_handoff_us()) / 1000));
#endif
        reply(status);
#ifdef ESP_CON2_JOYCON2_DUAL
        char sides[160];
        std::snprintf(sides, sizeof(sides), "@SIDES left_paired=%d left_connected=%d left_streaming=%d right_paired=%d right_connected=%d right_streaming=%d\n",
          controller.left.is_paired(), controller.left.is_connected(), controller.left.is_input_streaming(),
          controller.right.is_paired(), controller.right.is_connected(), controller.right.is_input_streaming());
        reply(sides);
#endif
      } else if (line == "WAKE") {
        reply(controller.wake_console() ? "@OK\n" : "@ERR wake requires a disconnected bond\n");
      } else if (line == "PAIR") {
        // Forget only this emulator's bond; the console must be on its pairing screen.
        report = neutral();
        deadline = 0;
        controller.set_input_report(report);
        reply(controller.clear_bond() ? "@OK\n" : "@ERR clear bond\n");
      } else if (line == "RELEASE") {
        report = neutral();
        deadline = 0;
        controller.set_input_report(report);
        reply("@OK\n");
      } else {
        unsigned mask = 0;
        float lx = 0, ly = 0, rx = 0, ry = 0;
        char trailing;
        const int fields = std::sscanf(line.c_str(), "STATE %x %f %f %f %f %c",
                                       &mask, &lx, &ly, &rx, &ry, &trailing);
        const auto axis_ok = [](float v) { return std::isfinite(v) && std::abs(v) <= 1; };
        if (fields != 5 || (mask & ~valid_mask) || !axis_ok(lx) || !axis_ok(ly) || !axis_ok(rx) || !axis_ok(ry)) {
          reply("@ERR invalid command\n");
        } else if (!controller.is_input_streaming()) {
          reply("@ERR controller is not streaming\n");
        } else {
          report = neutral();
          for (size_t b = 0; b < 21; ++b) (report.*buttons[b])((mask & (1u << b)) != 0);
          report.set_left_stick(lx, ly);
          report.set_right_stick(rx, ry);
          controller.set_input_report(report);
          deadline = esp_timer_get_time() + 500000;
          reply("@OK\n");
        }
      }
      line.clear();
      overflow = false;
    }
    // Release stale input after 500 ms, including USB loss or a crashed client.
    if (deadline && (esp_timer_get_time() >= deadline || !controller.is_input_streaming())) {
      report = neutral();
      controller.set_input_report(report);
      deadline = 0;
    }
    vTaskDelay(1);
  }
}
