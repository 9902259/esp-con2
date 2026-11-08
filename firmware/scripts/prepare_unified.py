#!/usr/bin/env python3
"""Combine isolated Pro protocol sources with the generated dual Joy-Con driver."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
subprocess.run([sys.executable, str(root / 'firmware/scripts/prepare_dual_joycon2.py')],
               env={**os.environ, 'ESP_CON2_DUAL_PUBLIC': '1'}, check=True)
source = root / '.deps/espp/components/switch2_pro'
target = root / '.deps/unified/unified_pro'
if target.exists():
    # Regenerate only this disposable component; avoid transforming old generated headers twice.
    shutil.rmtree(target)
shutil.copytree(source, target, dirs_exist_ok=True)
for file in list(target.rglob('*')):
    if not file.is_file() or file.suffix not in ('.hpp', '.cpp'):
        continue
    # Separate symbols and headers prevent either protocol from changing the other.
    text = file.read_text().replace('switch2_pro', 'unified_pro').replace('Switch2Pro', 'UnifiedPro')
    # Callback vtables also need unique symbols; otherwise dual handlers can consume Pro writes.
    text = text.replace('ChannelCallbacks', 'UnifiedProChannelCallbacks')
    text = text.replace('switch2::', 'unified_switch2::').replace('namespace espp::switch2', 'namespace espp::unified_switch2')
    text = text.replace('using namespace switch2;', 'using namespace unified_switch2;')
    if file.name == 'switch2_pro.cpp':
        # A new combined-image identity must not overwrite standalone Pro pairing records.
        text = text.replace('"switch2pro"', '"unifiedpro"')
        start = text.index('#if defined(CONFIG_BT_NIMBLE_EXT_ADV)')
        end = text.index('#endif', start) + len('#endif')
        text = text[:start] + text[end:]
        start = text.index('bool UnifiedPro::start_advertising(')
        end = text.index('\nbool UnifiedPro::advertise()', start)
        text = text[:start] + '''bool UnifiedPro::start_advertising(AdvMode mode, const std::array<uint8_t, 6> &host) {
  // Legacy Nintendo PDUs transported through the common extended-advertising API.
  auto *adv = NimBLEDevice::getAdvertising();
  adv->stop(0);
  auto mfr = MANUFACTURER_DATA_DISCOVERY;
  if (mode != AdvMode::Discovery) {
    std::copy(host.begin(), host.end(), mfr.begin() + MANUFACTURER_HOST_ADDR_OFFSET);
    if (mode == AdvMode::Wake) mfr[MANUFACTURER_WAKE_FLAG_OFFSET] = WAKE_FLAG;
  }
  NimBLEExtAdvertisement data;
  data.setLegacyAdvertising(true); data.setConnectable(true); data.setScannable(true);
  data.setMinInterval(0x20); data.setMaxInterval(0x40);
  data.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
  if (!data.setManufacturerData(mfr.data(), mfr.size()) || !adv->setInstanceData(0, data)) return false;
  NimBLEExtAdvertisement response; response.setName(device_name_);
  return adv->setScanResponseData(0, response) && adv->start(0);
}
''' + text[end:]
    if file.name == 'switch2_pro_report.hpp':
        text = text.replace('  const std::array<uint8_t, SIZE> &data()',
                            '  void assign(const std::array<uint8_t, SIZE> &value) { data_ = value; }\n'
                            '  const std::array<uint8_t, SIZE> &data()')
    destination = file.with_name(file.name.replace('switch2_pro', 'unified_pro'))
    destination.write_text(text)
    if destination != file:
        file.unlink()
print('Prepared unified Pro driver:', target)
