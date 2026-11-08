#!/usr/bin/env python3
"""Prepare an isolated, experimental two-connection Joy-Con driver."""
import shutil
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(ROOT / 'firmware/scripts/prepare_joycon2.py')], check=True)
source = ROOT / '.deps/joycon2-right/switch2_pro'
target = ROOT / '.deps/joycon2-dual/switch2_pro'
shutil.copytree(source, target, dirs_exist_ok=True)
cpp = (target / 'src/switch2_pro.cpp').read_text()
header = (target / 'include/switch2_pro.hpp').read_text()


def swap(old, new):
    global cpp
    # Do not silently patch a different upstream driver revision.
    assert cpp.count(old) == 1, old
    cpp = cpp.replace(old, new)


# Keep Nintendo's legacy advertising PDUs, using two BLE 5 advertising sets.
start = cpp.index('#if defined(CONFIG_BT_NIMBLE_EXT_ADV)')
end = cpp.index('#endif', start) + len('#endif')
cpp = cpp[:start] + cpp[end:]
swap('using namespace switch2;', '''using namespace switch2;
Switch2Pro *dual_lookup(NimBLEConnInfo &info);
''')
# Route every characteristic event to the connection's own protocol session.
swap('NimBLEConnInfo & /*conn*/) override {\n    auto value',
     'NimBLEConnInfo &conn) override {\n    auto *owner_ = dual_lookup(conn);\n    if (!owner_) return;\n    auto value')
swap('void onRead(NimBLECharacteristic * /*c*/, NimBLEConnInfo & /*conn*/) override {',
     'void onRead(NimBLECharacteristic * /*c*/, NimBLEConnInfo &conn) override {\n    auto *owner_ = dual_lookup(conn);\n    if (!owner_) return;')
swap('NimBLEConnInfo & /*conn*/,\n                   uint16_t sub_value) override {',
     'NimBLEConnInfo &conn,\n                   uint16_t sub_value) override {\n    auto *owner_ = dual_lookup(conn);\n    if (!owner_) return;')
swap('NimBLEConnInfo & /*conn*/, int code) override {',
     'NimBLEConnInfo &conn, int code) override {\n    auto *owner_ = dual_lookup(conn);\n    if (!owner_) return;')

# Reuse the proven per-session pairing, encryption, pacing and input code.
init_start = cpp.index('bool Switch2Pro::init() {')
init_end = cpp.index('Switch2Pro::~Switch2Pro()', init_start)
pace_start = cpp.index('  pace_timer_ =', init_start)
pace_end = cpp.index('  initialized_ = true;', pace_start)
pace_code = cpp[pace_start:pace_end]
cpp = cpp[:init_start] + '''bool Switch2Pro::init() { return false; }

bool Switch2Pro::init_dual(bool left, Switch2Pro *shared) {
  left_ = left;
  if (!PairingCrypto::self_test()) return false;
  configure_callbacks();
  reconnect_mode_ = load_bond();
  paired_ = reconnect_mode_.load();
  if (!shared) {
    if (!build_gatt()) return false;
  } else {
    common_input_ = shared->common_input_;
    pro2_input_ = shared->pro2_input_;
    command_response1_ = shared->command_response1_;
    command_response2_ = shared->command_response2_;
  }
''' + pace_code + '''  initialized_ = true;
  return true;
}

''' + cpp[init_end:]
swap('ble_gatt_server_.set_callbacks(callbacks);', 'dual_callbacks = callbacks;')
swap('auto *server = ble_gatt_server_.server();', 'auto *server = NimBLEDevice::getServer();')
swap('active_conn_handle_ = info.getConnHandle();', '''active_conn_handle_ = info.getConnHandle();
    if (paired_) inject_pairing_ltk(); // Select this half's persisted key on reconnect.''')
swap('response_char->notify();', 'response_char->notify(active_conn_handle_.load());')
swap('    ++report_counter_; // +1 per delivered report, matching the real device', '''    ++report_counter_; // +1 per accepted notification.
    if (traced_buttons_[0] != buf[2] || traced_buttons_[1] != buf[3]) {
      traced_buttons_ = {buf[2], buf[3]};
      std::printf("@REPORT side=%s handle=%u b2=%02x b3=%02x\\n",
                  left_ ? "L" : "R", active_conn_handle_.load(), buf[2], buf[3]);
    }''')
swap('static uint32_t dbg_tick = 0;\n  if ((dbg_tick++ % 66) == 0)',
     'if ((send_attempts_ % 66) == 0)')
swap('constexpr const char *kNvsNamespace = "joycon2right";', '')
cpp = cpp.replace('kNvsNamespace', '(left_ ? "dual3left" : "dual3right")')
swap('0x02, 0x01, 0x04, 0x01, 0x0c, 0x00,',
     '0x02, 0x01, 0x04, static_cast<uint8_t>(left_ ? 0 : 1), 0x0c, 0x00,')
swap('static constexpr std::array<uint8_t, 12> fw', 'const std::array<uint8_t, 12> fw')
swap('simulated_flash_read(addr, read_len, reply.data() + 8);', '''simulated_flash_read(addr, read_len, reply.data() + 8);
    // The controller PID must agree with the identity used by this connection.
    if (addr <= 0x13014 && addr + read_len > 0x13014)
      reply[8 + 0x13014 - addr] = left_ ? 0x67 : 0x66;
    // The two emulated physical controllers must not share their factory serial.
    if (addr <= 0x1300f && addr + read_len > 0x1300f)
      reply[8 + 0x1300f - addr] = left_ ? '1' : '2';''')
swap('buf[2] = pro[2]; // ABXY, R/ZR, Plus and right-stick click have identical bits.',
     'buf[2] = left_ ? pro[3] : pro[2]; // Independent left/right button fields.')
swap('buf[3] = pro[4] & 0x11; // Home and C.',
     'buf[3] = left_ ? ((pro[4] & 0x02) >> 1) : (pro[4] & 0x11);')
swap('std::copy_n(pro.begin() + 8, 3, buf.begin() + 5);',
     'std::copy_n(pro.begin() + (left_ ? 5 : 8), 3, buf.begin() + 5);')
swap('buf[0x0f] = (enabled_features_ & switch2::FEATURE_IMU) ? 40 : 0;',
     'buf[left_ ? 0x0e : 0x0f] = (enabled_features_ & switch2::FEATURE_IMU) ? 40 : 0;')

start = cpp.index('bool Switch2Pro::start_advertising(')
end = cpp.index('\nbool Switch2Pro::advertise()', start)
cpp = cpp[:start] + '''bool Switch2Pro::start_advertising(AdvMode mode, const std::array<uint8_t, 6> &host) {
  auto *advertiser = NimBLEDevice::getAdvertising();
  const uint8_t instance = left_ ? 0 : 1;
  auto mfr = MANUFACTURER_DATA_DISCOVERY;
  mfr[7] = left_ ? 0x67 : 0x66;
  if (mode != AdvMode::Discovery) {
    std::copy(host.begin(), host.end(), mfr.begin() + MANUFACTURER_HOST_ADDR_OFFSET);
    if (mode == AdvMode::Wake) mfr[MANUFACTURER_WAKE_FLAG_OFFSET] = WAKE_FLAG;
  }
  advertiser->stop(instance);
  NimBLEExtAdvertisement advertisement;
  advertisement.setLegacyAdvertising(true);
  advertisement.setConnectable(true);
  advertisement.setScannable(true);
  advertisement.setMinInterval(0x20);
  advertisement.setMaxInterval(0x40);
  advertisement.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  if (left_) {
    // One controller exposes one public address; the second set has its own static random address.
    uint8_t mac[6]; esp_read_mac(mac, ESP_MAC_BT);
    ble_addr_t address{};
    address.type = BLE_ADDR_RANDOM;
    std::reverse_copy(mac, mac + 6, address.val);
    address.val[0] ^= 0x40;
    address.val[5] |= 0xc0;
    // The typed constructor preserves NimBLE wire order; the byte-array overload reverses it.
    advertisement.setAddress(NimBLEAddress(address));
  }
  if (!advertisement.setManufacturerData(mfr.data(), mfr.size()) ||
      !advertiser->setInstanceData(instance, advertisement)) return false;
  NimBLEExtAdvertisement response;
  response.setName(left_ ? "Joy-Con 2 (L)" : "Joy-Con 2 (R)");
  if (!advertiser->setScanResponseData(instance, response)) return false;
  const bool ok = advertiser->start(instance);
  logger_.info("dual advertising: side={} instance={} started={}", left_ ? "L" : "R", instance, ok);
  return ok;
}
''' + cpp[end:]

# Opt-in, version-specific experiment: preserve the first link while changing public advertising identity.
if os.environ.get('ESP_CON2_DUAL_PUBLIC') == '1':
    begin = cpp.index('  if (left_) {\n    // One controller exposes')
    finish = cpp.index('\n  if (!advertisement.setManufacturerData', begin)
    cpp = cpp[:begin] + '''  // This RAM layout is specific to the pinned S3 controller binary.
  uint8_t base[6], desired[6]; esp_read_mac(base, ESP_MAC_BT);
  std::reverse_copy(base, base + 6, desired);
  if (left_) { desired[0] ^= 0x40; desired[5] |= 0xc0; }
  static std::array<uint8_t, 6> previous{};
  static bool checked = false;
  if (!checked) { std::reverse_copy(base, base + 6, previous.begin()); checked = true; }
  if (!p_llm_env) return false;
  auto *public_address = static_cast<uint8_t *>(p_llm_env) + 12;
  if (std::memcmp(public_address, previous.data(), 6) != 0) {
    logger_.error("public identity guard failed; refusing RAM write");
    return false;
  }
  std::memcpy(public_address, desired, 6);
  std::copy_n(desired, 6, previous.begin());
  ble_hs_id_set_pub(desired);
  logger_.info("public identity selected: side={}", left_ ? "L" : "R");
''' + cpp[finish:]
    cpp = '#include <cstring>\nextern "C" { extern void *p_llm_env; int ble_hs_id_set_pub(const unsigned char *); }\n' + cpp
    if os.environ.get('ESP_CON2_DUAL_NO_LINK_FILTER') == '1':
        # Pinned S3 implementation clears the upper filter bits at 0x60031304 for argument zero.
        cpp = 'extern "C" void btdm_linkbl_filter_init(unsigned char);\n' + cpp
        cpp = cpp.replace('  std::memcpy(public_address, desired, 6);',
                          '  btdm_linkbl_filter_init(0); // Test acceptance of a second link from the same central.\n'
                          '  logger_.info("experimental link filter disabled");\n'
                          '  std::memcpy(public_address, desired, 6);')

# Expose only lifecycle hooks needed by the shared GATT/GAP dispatcher.
header = header.replace('  // --- setup ---', '''public:
  bool init_dual(bool left, Switch2Pro *shared);
  bool start_dual_advertising() { return advertise(); }
  uint16_t connection_handle() const { return active_conn_handle_; }
  // Host-to-controller handoff telemetry; this is not an over-air acknowledgement.
  uint32_t input_handoffs() const { return tx_completions_.load(); }
  int64_t last_handoff_us() const { return last_tx_complete_us_.load(); }
  BleGattServer::Callbacks dual_callbacks;
protected:
  bool left_{false};
  std::array<uint8_t, 2> traced_buttons_{}; // Log accepted button changes only.
  // --- setup ---''')
(target / 'src/switch2_pro.cpp').write_text(cpp)
(target / 'include/switch2_pro.hpp').write_text(header)
print('Prepared experimental shared-stack dual Joy-Con driver:', target)

# A diagnostic bootstrap pairs the second identity publicly before testing random-address reconnect.
subprocess.run([sys.executable, str(ROOT / 'firmware/scripts/prepare_joycon2.py'), '--side', 'left'], check=True)
bootstrap = ROOT / '.deps/joycon2-bootstrap/switch2_pro'
shutil.copytree(ROOT / '.deps/joycon2-left/switch2_pro', bootstrap, dirs_exist_ok=True)
file = bootstrap / 'src/switch2_pro.cpp'
file.write_text(file.read_text().replace('"joycon2left"', '"dual2left"'))

# A weak discovery hook keeps the default host unchanged outside the dual firmware.
gatts = ROOT / '.deps/esp-idf/components/bt/host/nimble/nimble/nimble/host/src/ble_gatts.c'
text = gatts.read_text()
if 'esp_con2_dual_gatt_uuid' not in text:
    old = '    ble_uuid_flat(chr->uuid, buf);\n\n    return 0;'
    assert text.count(old) == 1, 'unexpected pinned GATT declaration reader'
    text = text.replace(old, '''    ble_uuid_flat(chr->uuid, buf);
    /* Optional per-connection UUID view for the dual Joy-Con experiment. */
    extern void esp_con2_dual_gatt_uuid(uint16_t, uint8_t *) __attribute__((weak));
    if (ble_uuid_length(chr->uuid) == 16 && esp_con2_dual_gatt_uuid) {
        esp_con2_dual_gatt_uuid(conn_handle, buf);
    }

    return 0;''')
    gatts.write_text(text)

# Count controller completion credits per connection rather than relying on NOTIFY_TX.
hci = ROOT / '.deps/esp-idf/components/bt/host/nimble/nimble/nimble/host/src/ble_hs_hci_evt.c'
text = hci.read_text()
if 'esp_con2_dual_completed' not in text:
    old = '        num_pkts = le16toh(ev->completed[i].packets);'
    assert text.count(old) == 1, 'unexpected pinned HCI completion parser'
    text = text.replace(old, old + '''
        /* Optional diagnostics for the experimental dual controller. */
        extern void esp_con2_dual_completed(uint16_t, uint16_t) __attribute__((weak));
        if (esp_con2_dual_completed) {
            esp_con2_dual_completed(le16toh(ev->completed[i].handle), num_pkts);
        }''')
    hci.write_text(text)

# Translate ATT read-by-type UUIDs per connection; discovery rewriting alone is insufficient.
att = ROOT / '.deps/esp-idf/components/bt/host/nimble/nimble/nimble/host/src/ble_att_svr.c'
text = att.read_text()
if 'esp_con2_dual_uuid_lookup' not in text:
    old = '        entry = ble_att_svr_find_by_uuid(entry, uuid, end_handle);'
    assert text.count(old) == 1, 'unexpected pinned ATT read-by-type lookup'
    text = text.replace(old, '''        /* The optional hook presents a separate characteristic UUID view per link. */
        extern int esp_con2_dual_uuid_lookup(uint16_t, const ble_uuid_t *, ble_uuid128_t *) __attribute__((weak));
        ble_uuid128_t mapped_uuid;
        const ble_uuid_t *lookup_uuid = uuid;
        int reject_uuid = 0;
        if (esp_con2_dual_uuid_lookup) {
            int action = esp_con2_dual_uuid_lookup(conn_handle, uuid, &mapped_uuid);
            if (action < 0) reject_uuid = 1;
            if (action > 0) lookup_uuid = &mapped_uuid.u;
        }
        entry = reject_uuid ? NULL : ble_att_svr_find_by_uuid(entry, lookup_uuid, end_handle);''')
    att.write_text(text)
