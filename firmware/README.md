# esp-con2 firmware

Targets ESP32-S3 development boards with at least 4 MB flash and accessible native USB. USB serial commands
control a BLE-emulated Joy-Con 2 pair or Pro Controller 2 on Switch 2. This does
not emulate Bluetooth Classic controllers for the original Switch.

From the project root:

```sh
bash firmware/scripts/dependencies.sh
make firmware
ESP_CON2_PROFILE=unified bash firmware/scripts/firmware.sh -p /dev/cu.usbmodemXXXX flash
```

The helper uses `build/firmware/unified` and `build/config/sdkconfig-unified`.
Flashing replaces the device application; keep needed backups. Firmware dependency
setup needs Python 3.12 compatible with pinned ESP-IDF; set `ESP_CON2_IDF_PYTHON`
if it is installed at another path. This is separate from the Python 3.15 host.
Existing IDF environments are selected automatically by the build helper.

## Files

- `main/main.cpp`: USB serial parsing, input lease, persistent mode selection.
- `main/dual_joycon.hpp`: two BLE protocol sessions and controller/GATT hooks.
- `main/unified_controller.hpp`: active-mode routing and saved mode.
- `scripts/`: pinned dependency installation, generated drivers, build/flash helper.
- `sdkconfig.defaults*`, `sdkconfig.dual`, `partitions.csv`: checked-in defaults.

## Modes and protocol

`MODE joycon` or `MODE pro` saves the selected mode, replies `@OK`, then reboots.
Only one mode runs at a time; each has separate pairing records. The default is
Joy-Con L+R. The wire identifier is `esp-con2`; hosts require this identifier.
NVS namespaces remain unchanged to preserve existing bonds.

See [serial commands](../docs/serial-commands.md) and
[combined firmware design](../docs/unified-firmware.md). The firmware neutralizes
input after a 500 ms lease expires. Every host must refresh held state and release
on completion, errors, cancellation, or disconnection.

## Validation limits

Single/dual profiles passed the console button tests documented in
[verified results](../docs/verified-dual-joycon.md). The combined firmware paired
in Pro mode and reconnected both Joy-Con halves when switched back. Transport
status is not proof of console-visible acceptance; sticks, motion, mouse, and
long-term reliability remain separate validation work. Do not change the pinned
S3 binary or its private hooks without revalidating pairing and report delivery.

## Board requirements

Connect the SoC native USB data port (GPIO19 D− / GPIO20 D+), rather than a
UART-only USB bridge: commands use USB Serial/JTAG. No display, keyboard, PSRAM,
or board-specific peripherals are required. Defaults target 4 MB flash; larger
flash boards can use the same layout. Smaller boards need a suitable partition
layout and build configuration. Radio/antenna performance and USB wiring remain
board-dependent. Hardware validation covers one ESP32-S3 board; other
boards require physical validation.
