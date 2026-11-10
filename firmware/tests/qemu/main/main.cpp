#include <cstdio>
#include <string>
#include "serial_transport.hpp"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

extern "C" void app_main() {
  // This UART/NVS diagnostic has no Bluetooth controller or simulated pairing state.
  serial_transport::init();
  ESP_ERROR_CHECK(nvs_flash_init());
  nvs_handle_t handle;
  ESP_ERROR_CHECK(nvs_open("virtual_test", NVS_READWRITE, &handle));
  uint32_t boots = 0;
  const auto result = nvs_get_u32(handle, "boots", &boots);
  ESP_ERROR_CHECK(result == ESP_ERR_NVS_NOT_FOUND ? ESP_OK : result);
  ESP_ERROR_CHECK(nvs_set_u32(handle, "boots", ++boots));
  ESP_ERROR_CHECK(nvs_commit(handle));
  nvs_close(handle);
  char ready[100];
  std::snprintf(ready, sizeof(ready), "@VTEST READY boots=%lu\n", static_cast<unsigned long>(boots));
  const auto reply = [](const char *text) { serial_transport::reply(serial_transport::Port::Uart, text); };
  reply(ready);
  std::string line;
  while (true) {
    char data[128];
    const int count = serial_transport::read(serial_transport::Port::Uart, data, sizeof(data));
    for (int i = 0; i < count; ++i) {
      if (data[i] == '\r') continue;
      if (data[i] != '\n') {
        if (line.size() < 160) line += data[i];
        continue;
      }
      if (line == "PING") reply("@VTEST PONG\n");
      else if (line == "LONG") {
        // Exceed the UART hardware FIFO to exercise the production TX ring buffer.
        const std::string response = "@VTEST LONG " + std::string(400, 'x') + "\n";
        reply(response.c_str());
      } else if (line == "REBOOT") {
        reply("@VTEST REBOOT\n");
        vTaskDelay(pdMS_TO_TICKS(100));
        esp_restart();
      } else reply("@VTEST UNKNOWN\n");
      line.clear();
    }
    vTaskDelay(1);
  }
}
