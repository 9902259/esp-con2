#pragma once

#include "switch2_pro.hpp"
#include "host/ble_gap.h"
#include "esp_timer.h"
#include <atomic>
#include <cstdio>
#include <cstring>

// NimBLE's internal declaration serializer is used by the paired discovery hook.
extern "C" int ble_uuid_flat(const ble_uuid_t *, void *);

inline std::atomic<unsigned> peer_checks{0}, peer_matches{0}, left_uuid_remaps{0};
inline std::atomic<unsigned> left_completed{0}, right_completed{0};
inline bool dual_peer_bypass_enabled = false; // Set before starting the dual BLE host.
extern "C" unsigned char __real_r_llm_is_dev_connected(const void *, unsigned char);
extern "C" unsigned char __wrap_r_llm_is_dev_connected(const void *address, unsigned char type) {
  // The pinned S3 controller otherwise rejects a second link from the same Switch.
  // Keep the original result as telemetry; this bypass is restricted to the dual build.
  auto result = __real_r_llm_is_dev_connected(address, type);
  peer_checks.fetch_add(1, std::memory_order_relaxed);
  if (result) peer_matches.fetch_add(1, std::memory_order_relaxed);
  return dual_peer_bypass_enabled ? 0 : result;
}

// One Bluetooth host, two independently paired controller protocol sessions.
class DualJoyCon {
public:
  bool left_started{false};
  int64_t next_left_attempt{0};
  // Reduce aggregate report traffic while diagnosing starvation between the two links.
  espp::Switch2Pro left{{.device_name="Joy-Con 2 (L)", .wake_console_on_boot_enabled=false,
                        .continuous_stream_divisor=4}};
  espp::Switch2Pro right{{.device_name="Joy-Con 2 (R)", .wake_console_on_boot_enabled=false,
                         .continuous_stream_divisor=4}};
  bool init();
  void tick() {
    static int64_t next_trace = 0;
    if (esp_timer_get_time() >= next_trace) {
      next_trace = esp_timer_get_time() + 5000000;
      std::printf("@PEER_CHECK calls=%u matches=%u left_uuid_remaps=%u left_completed=%u right_completed=%u\n",
                  peer_checks.load(), peer_matches.load(), left_uuid_remaps.load(),
                  left_completed.load(), right_completed.load());
    }
    // Serialize key exchanges: both session keys share NimBLE's peer-indexed security store.
    // Encrypted/subscribed flags do not guarantee the console has selected the pair.
    if (!left_started && left.is_input_streaming() && esp_timer_get_time() >= next_left_attempt) {
      next_left_attempt = esp_timer_get_time() + 2000000;
      left_started = right.start_dual_advertising();
    }
  }
  bool is_paired() const { return left.is_paired() && right.is_paired(); }
  bool is_connected() const { return left.is_connected() && right.is_connected(); }
  bool is_input_streaming() const { return left.is_input_streaming() && right.is_input_streaming(); }
  bool wake_console() {
    bool l = left.is_connected() || left.wake_console();
    bool r = right.is_connected() || right.wake_console();
    return l && r;
  }
  bool clear_bond() { bool l=left.clear_bond(); bool r=right.clear_bond(); return l && r; }
  void set_input_report(const espp::switch2::Pro2InputReport &report) {
    left.set_input_report(report); right.set_input_report(report);
  }
};

inline DualJoyCon *dual_device = nullptr;

// The shared table stores right UUIDs; translate left read-by-type requests.
extern "C" int esp_con2_dual_uuid_lookup(uint16_t handle, const ble_uuid_t *uuid,
                                           ble_uuid128_t *mapped) {
  if (!dual_device || dual_device->left.connection_handle() != handle) return 0;
  static const char *pairs[][2] = {
    {"d5a9e01e-2ffc-4cca-b20c-8b67142bf442", "cc1bbbb5-7354-4d32-a716-a81cb241a32a"},
    {"fa19b0fb-cd1f-46a7-84a1-bbb09e00c149", "289326cb-a471-485d-a8f4-240c14f18241"},
    {"65a724b3-f1e7-4a61-8078-a342376b27ff", "ce49a830-dced-48ae-931e-c8cf88aadbea"},
    {"640ca58e-0e88-410c-a7f3-426faf2b690b", "63a3810f-aec7-474b-9010-3d52403cb996"},
  };
  for (const auto &pair : pairs) {
    NimBLEUUID right(pair[0]), left(pair[1]);
    if (ble_uuid_cmp(uuid, left.getBase()) == 0) {
      std::memcpy(mapped, right.getBase(), sizeof(*mapped));
      return 1;
    }
    if (ble_uuid_cmp(uuid, right.getBase()) == 0) return -1;
  }
  return 0;
}

extern "C" void esp_con2_dual_completed(uint16_t handle, uint16_t count) {
  // HCI completion credits are controller telemetry, not proof of console UI recognition.
  if (!dual_device) return;
  if (handle == dual_device->left.connection_handle()) left_completed.fetch_add(count);
  if (handle == dual_device->right.connection_handle()) right_completed.fetch_add(count);
}

extern "C" void esp_con2_dual_gatt_uuid(uint16_t handle, uint8_t *bytes) {
  if (!dual_device || dual_device->left.connection_handle() != handle) return;
  // Keep handle layout shared while exposing the documented left report identities.
  static const char *pairs[][2] = {
    {"d5a9e01e-2ffc-4cca-b20c-8b67142bf442", "cc1bbbb5-7354-4d32-a716-a81cb241a32a"},
    {"fa19b0fb-cd1f-46a7-84a1-bbb09e00c149", "289326cb-a471-485d-a8f4-240c14f18241"},
    {"65a724b3-f1e7-4a61-8078-a342376b27ff", "ce49a830-dced-48ae-931e-c8cf88aadbea"},
    {"640ca58e-0e88-410c-a7f3-426faf2b690b", "63a3810f-aec7-474b-9010-3d52403cb996"},
  };
  for (const auto &pair : pairs) {
    uint8_t right[16];
    ble_uuid_flat(NimBLEUUID(pair[0]).getBase(), right);
    if (std::memcmp(bytes, right, 16) == 0) {
      ble_uuid_flat(NimBLEUUID(pair[1]).getBase(), bytes);
      left_uuid_remaps.fetch_add(1, std::memory_order_relaxed);
      return;
    }
  }
}

namespace espp {
Switch2Pro *dual_lookup(NimBLEConnInfo &info) {
  if (!dual_device) return nullptr;
  auto handle = info.getConnHandle();
  if (dual_device->left.connection_handle() == handle) return &dual_device->left;
  if (dual_device->right.connection_handle() == handle) return &dual_device->right;
  return nullptr;
}
}

class DualGapCallbacks : public NimBLEServerCallbacks {
  // Connection-local address determines which emulated identity the console selected.
  void onConnect(NimBLEServer *, NimBLEConnInfo &info) override {
    ble_gap_conn_desc desc{};
    if (ble_gap_conn_find(info.getConnHandle(), &desc) != 0) return;
    // The sequential public-address experiment identifies the second half by its address bytes.
    auto *session = (desc.our_ota_addr.val[5] & 0xc0) == 0xc0 ? &dual_device->left : &dual_device->right;
    session->dual_callbacks.connect_callback(info);
  }
  void onDisconnect(NimBLEServer *, NimBLEConnInfo &info, int reason) override {
    if (auto *session = espp::dual_lookup(info))
      session->dual_callbacks.disconnect_callback(info, static_cast<espp::BleGattServer::DisconnectReason>(reason));
  }
  void onAuthenticationComplete(NimBLEConnInfo &info) override {
    if (auto *session = espp::dual_lookup(info)) session->dual_callbacks.authentication_complete_callback(info);
  }
  void onConnParamsUpdate(NimBLEConnInfo &info) override {
    if (auto *session = espp::dual_lookup(info)) session->dual_callbacks.conn_params_update_callback(info);
  }
};

inline bool DualJoyCon::init() {
  dual_device = this;
  dual_peer_bypass_enabled = true;
  if (!NimBLEDevice::init("Joy-Con 2 pair")) return false;
  NimBLEDevice::setOwnAddrType(BLE_OWN_ADDR_PUBLIC);
  NimBLEDevice::setSecurityAuth(false, false, false);
  NimBLEDevice::setSecurityIOCap(BLE_HS_IO_NO_INPUT_OUTPUT);
  auto *server = NimBLEDevice::createServer();
  if (!server) return false;
  server->setCallbacks(new DualGapCallbacks());
  if (!left.init_dual(true, nullptr) || !right.init_dual(false, &left)) return false;
  if (!server->start()) return false;
  // Reverse the public-identity sequence to isolate a connection-order restriction.
  return left.start_dual_advertising();
}
