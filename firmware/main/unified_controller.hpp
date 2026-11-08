#pragma once
#include "dual_joycon.hpp"
#include "unified_pro.hpp"
#include "nvs.h"

// A reboot reconstructs GATT and controller identity cleanly when the mode changes.
inline bool load_pro_mode() {
  nvs_handle_t handle;
  uint8_t value = 0;
  if (nvs_open("console_mode", NVS_READONLY, &handle) == ESP_OK) {
    nvs_get_u8(handle, "pro", &value);
    nvs_close(handle);
  }
  return value == 1;
}

inline bool save_pro_mode(bool pro) {
  nvs_handle_t handle;
  if (nvs_open("console_mode", NVS_READWRITE, &handle) != ESP_OK) return false;
  auto result = nvs_set_u8(handle, "pro", pro ? 1 : 0);
  if (result == ESP_OK) result = nvs_commit(handle);
  nvs_close(handle);
  return result == ESP_OK;
}

class UnifiedController {
  bool pro_mode_;
  DualJoyCon dual_;
  espp::UnifiedPro pro_{{.device_name="Pro Controller", .wake_console_on_boot_enabled=false}};
public:
  // Retain existing dual diagnostic access; inactive halves report zero in Pro mode.
  espp::Switch2Pro &left = dual_.left;
  espp::Switch2Pro &right = dual_.right;
  explicit UnifiedController(bool pro) : pro_mode_(pro) {}
  bool init() { return pro_mode_ ? pro_.init() : dual_.init(); }
  void tick() { if (!pro_mode_) dual_.tick(); }
  bool is_paired() const { return pro_mode_ ? pro_.is_paired() : dual_.is_paired(); }
  bool is_connected() const { return pro_mode_ ? pro_.is_connected() : dual_.is_connected(); }
  bool is_input_streaming() const { return pro_mode_ ? pro_.is_input_streaming() : dual_.is_input_streaming(); }
  bool wake_console() { return pro_mode_ ? pro_.wake_console() : dual_.wake_console(); }
  bool clear_bond() { return pro_mode_ ? pro_.clear_bond() : dual_.clear_bond(); }
  void set_input_report(const espp::switch2::Pro2InputReport &report) {
    if (pro_mode_) {
      espp::unified_switch2::Pro2InputReport translated;
      translated.assign(report.data());
      pro_.set_input_report(translated);
    } else dual_.set_input_report(report);
  }
};
