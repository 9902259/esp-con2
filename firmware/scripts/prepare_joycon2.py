#!/usr/bin/env python3
"""Generate an experimental left or right Joy-Con 2 driver from pinned espp."""
from pathlib import Path
import shutil
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--side', choices=('left', 'right'), default='right')
side = parser.parse_args().side
left = side == 'left'
pid = '67' if left else '66'

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / '.deps/espp/components/switch2_pro'
target = ROOT / f'.deps/joycon2-{side}/switch2_pro'
target.mkdir(parents=True, exist_ok=True)
for directory in ('include', 'src'):
    shutil.copytree(source / directory, target / directory, dirs_exist_ok=True)
shutil.copy2(source / 'CMakeLists.txt', target / 'CMakeLists.txt')
shutil.copy2(ROOT / '.deps/espp/LICENSE', target / 'LICENSE')


def replace(path, old, new):
    # Fail on upstream drift rather than producing a partially patched identity.
    file = target / path
    text = file.read_text()
    assert text.count(old) == 1, (path, old)
    file.write_text(text.replace(old, new))


# Protocol facts: ndeadly/switch2_controller_research Bluetooth and HID tables.
protocol = 'include/switch2_pro_protocol.hpp'
for old, new in {
    '7492866c-ec3e-4619-8258-32755ffcc0f8': 'cc1bbbb5-7354-4d32-a716-a81cb241a32a' if left else 'd5a9e01e-2ffc-4cca-b20c-8b67142bf442',
    'cc483f51-9258-427d-a939-630c31f72b05': '289326cb-a471-485d-a8f4-240c14f18241' if left else 'fa19b0fb-cd1f-46a7-84a1-bbb09e00c149',
}.items():
    replace(protocol, old, new)
# Read the existing UUID constants so the patch stays tied to named fields.
import re
for name, uuid in {
    'VIBRATION_COMMAND_UUID': 'ce49a830-dced-48ae-931e-c8cf88aadbea' if left else '65a724b3-f1e7-4a61-8078-a342376b27ff',
    'COMMAND_RESPONSE2_UUID': '63a3810f-aec7-474b-9010-3d52403cb996' if left else '640ca58e-0e88-410c-a7f3-426faf2b690b',
}.items():
    text = (target / protocol).read_text()
    old = re.search(name + r'\s*=\s*"([^"]+)"', text).group(1)
    replace(protocol, old, uuid)
replace(protocol, 'PRODUCT_ID_PRO2 = 0x2069', f'PRODUCT_ID_PRO2 = 0x20{pid}')
replace(protocol, 'VIBRATION_COMMAND_PREFIX_SIZE = 33', 'VIBRATION_COMMAND_PREFIX_SIZE = 17')
replace(protocol, '0x05, 0x69, 0x20', f'0x05, 0x{pid}, 0x20')
cpp = 'src/switch2_pro.cpp'
replace(cpp, 'logger_.debug("cmd 0x{:02x}/0x{:02x} ({}B data)",',
        'logger_.info("cmd 0x{:02x}/0x{:02x} ({}B data)",')
replace(cpp, '"switch2pro"', f'"joycon2{side}"')
# Joy-Con command replies use the unprefixed command-response characteristic.
replace(cpp, 'auto *response_char = via_vibration_command ? command_response2_ : command_response1_;',
        'auto *response_char = command_response1_;')
replace(cpp, 'if (via_vibration_command)\n    out.resize(RESPONSE_PREFIX_SIZE, 0x00);',
        '// Joy-Con replies do not carry the Pro extended-response prefix.')
start = (target / cpp).read_text().index('  // Headset-audio attributes')
end = (target / cpp).read_text().index('  // services are started', start)
file = target / cpp
text = file.read_text()
file.write_text(text[:start] + '  // Joy-Con 2 has no Pro headset-audio service attributes.\n' + text[end:])
replace(cpp, '0x02, 0x01, 0x04, 0x02, 0x0c, 0x00,\n                                                   0x00, 0x00, 0x00, 0x02, 0x03, 0x00',
        f'0x02, 0x01, 0x04, 0x0{0 if left else 1}, 0x0c, 0x00,\n                                                   0x00, 0x00, 0x00, 0x00, 0x00, 0x00')
replace(cpp, 'static constexpr std::array<uint8_t, 4> blob01 = {0x01, 0x00, 0x00, 0x00};',
        'static constexpr std::array<uint8_t, 4> blob01 = {0x03, 0x00, 0x00, 0x00};')
replace(cpp, '0x61, 0x12, 0x50, 0x0d', '0x61, 0x12, 0x50, 0x10')
conversion = '''  // Convert the host's Pro-shaped snapshot to documented Joy-Con 2 (R) report 0x08.
  const auto pro = buf;
  buf.fill(0);
  buf[0] = pro[0];
  buf[1] = pro[1];
  buf[2] = pro[2]; // ABXY, R/ZR, Plus and right-stick click have identical bits.
  buf[3] = pro[4] & 0x11; // Home and C.
  if (pro[4] & 0x08) buf[3] |= 0x80; // GL/SL alias.
  if (pro[4] & 0x04) buf[3] |= 0x40; // GR/SR alias.
  buf[4] = 0x07;
  std::copy_n(pro.begin() + 8, 3, buf.begin() + 5);
  buf[8] = pro[0x0b];
  buf[0x0f] = (enabled_features_ & switch2::FEATURE_IMU) ? 40 : 0;
  // Mouse and motion payloads stay neutral in this experimental button profile.

  // Low-level notify so the exact rc is visible'''
if left:
    # Left report 0x07 shares the packet shape but has its own buttons and motion offset.
    conversion = conversion.replace('(R) report 0x08', '(L) report 0x07')
    conversion = conversion.replace('pro[2]; // ABXY, R/ZR, Plus and right-stick click have identical bits.',
                                    'pro[3]; // D-pad, L/ZL, Minus and left-stick click.')
    conversion = conversion.replace('pro[4] & 0x11; // Home and C.', '(pro[4] & 0x02) >> 1; // Capture.')
    conversion = conversion.replace('pro.begin() + 8', 'pro.begin() + 5').replace('buf[0x0f]', 'buf[0x0e]')
replace(cpp, '  // Low-level notify so the exact rc is visible', conversion)
replace('src/switch2_pro_flash.hpp', '0x05, 0x69, 0x20, 0x01, 0x06, 0x01',
        f'0x05, 0x{pid}, 0x20, 0x01, 0x08, 0x02')
print(f'Prepared experimental Joy-Con 2 ({side}) driver:', target)
