# esp-con2 firmware

Targets ESP32-S3 development boards with at least 2 MB flash and native USB or a USB-to-UART bridge. Serial commands
control a BLE-emulated Joy-Con 2 pair or Pro Controller 2 on Switch 2. This does
not emulate Bluetooth Classic controllers for the original Switch.

From the project root:

```sh
bash firmware/scripts/dependencies.sh
make firmware
bash firmware/scripts/firmware.sh -p /dev/cu.usbmodemXXXX flash
```

The helper uses `build/firmware/generic` and `build/config/sdkconfig-generic`.
Flashing replaces the device application; keep needed backups. Firmware dependency
setup uses current stable Python 3.15, matching the host tooling; set
`ESP_CON2_IDF_PYTHON` if it is installed at another path. The SDK keeps its own
virtual environment, which the build helper selects by Python version even if
older environments remain installed.
Flashing defaults to 115200 baud for UART-bridge compatibility. Use `-b BAUD`
or `ESPBAUD` to override it when the connection supports faster transfers.

## Files

- `main/main.cpp`: serial parsing, input lease, persistent mode selection.
- `main/serial_transport.hpp`, `main/Kconfig.projbuild`: USB/UART transport and board pin options.
- `main/dual_joycon.hpp`: two BLE protocol sessions and controller/GATT hooks.
- `main/unified_controller.hpp`: active-mode routing and saved mode.
- `scripts/`: pinned dependency installation, generated drivers, build/flash helper.
- `sdkconfig.defaults*`, `sdkconfig.sticky`, `partitions.csv`: checked-in defaults.

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

### Experimental ESP32-C6 trial

The Pro profile builds and boots on an ESP32-C6FH4 (4 MB flash), accepts native
USB serial commands, and advertises as Pro Controller. A hardware trial reported
paired, connected, and streaming continuously for 40 seconds. Here streaming
means an encrypted link with input subscription; console-visible input, actual
connection interval, reconnect, and wake remain unverified. The pinned C6
controller lacks the S3/C3 5 ms interval option; this observation does not yet
establish full compatibility.
The C6 target defaults explicitly enable the experimental timing bypass and
USB-only transport. The S3 firmware retains its chip-specific Joy-Con hooks.

```sh
# Install the C6 compiler without changing the default S3 build.
IDF_TOOLS_PATH="$PWD/.deps/idf-tools" python3.15 .deps/esp-idf/tools/idf_tools.py install riscv32-esp-elf
bash firmware/scripts/firmware.sh \
  -B "$PWD/build/firmware/pro-c6-trial" \
  -D SDKCONFIG="$PWD/build/config/sdkconfig-pro-c6-trial" \
  -D IDF_TARGET=esp32c6 build
```

Use the same arguments with `-p PORT flash` in place of `build` to flash.
The tested board exposes USB Serial/JTAG; boards wired only to a UART bridge
need a separate transport configuration with board-appropriate UART pins.

### ESP32-S3 defaults

The default image accepts commands through either port:

| Connection | Board pins | Host settings |
| --- | --- | --- |
| Native USB Serial/JTAG | GPIO19 D− / GPIO20 D+ | Existing host tools |
| USB-to-UART bridge or external 3.3 V serial adapter | UART0 TX GPIO43 / RX GPIO44 | 115200 baud, 8N1, no flow control |

With an external adapter, cross TX/RX and connect GND. Open one control port at
a time. Each port has its own line buffer and receives its own replies, but both
control the same controller and input lease. SDK logs stay on native USB.
UART commands also work on boards that expose only their bridge USB port.
Native USB means Serial/JTAG, not a TinyUSB/USB-OTG CDC device.

No display, keyboard, LEDs, buttons, or PSRAM are initialized. Defaults use a
2 MB layout, DIO at 40 MHz, flash-mode auto-detection from the pinned SDK, and
internal RAM only. Larger flash and any PSRAM capacity can use the same image;
extra memory is unused. NVS and application start offsets remain unchanged.

Check the schematic: the default image reserves GPIO19/20 and GPIO43/44. If
those UART pins connect to other peripherals, choose **Native USB only** or set
different UART TX/RX pins in **esp-con2 board compatibility**:

```sh
bash firmware/scripts/firmware.sh menuconfig
make firmware
```

For UART-only boards whose USB pins are occupied, choose **UART only** and set
the SDK console to **None** under **Component config → ESP-STDIO** (also keep
the secondary console disabled). Disable **Enable USB-Serial-JTAG Module** under
**Component config → ESP-Driver:USB Serial/JTAG Configuration** if GPIO19/20
serve other peripherals.
Never assign serial pins to flash/PSRAM wiring. Some octal-flash boards need an
explicit **Serial flasher config → Enable Octal Flash** setting and rebuild;
SDK auto-detection does not guarantee support for every flash chip. Check the
board/module specification instead of inferring flash type from PSRAM capacity.
Boards with less than 2 MB flash need a separate layout and size validation.

Existing `build/config/sdkconfig-generic` files keep their saved settings. To
adopt the new defaults, back up and remove that file before `make firmware`.

Power, antenna switching, external RF hardware, disabled USB eFuses, and unusual
wiring can require board-specific changes. This broadens compatibility; it is
not a claim of physical validation on every ESP32-S3 board. Earlier console
button tests predate these transport changes; Sticky UART checks are below.

## Seeed Studio reTerminal Sticky

Use the Sticky image instead of the generic image. [Seeed's hardware guide](https://www.seeedstudio.com/sticky/docs/en/device-guide/hardware-overview/)
assigns GPIO19/20 to the PDM microphone and connects USB-C through UART0 on
GPIO43/44. The Sticky profile disables native USB and SDK console output while
keeping the command protocol on UART0 at 115200 baud. It uses the same BLE
controller implementations, 2 MB layout, and internal-RAM configuration.

```sh
ESP_CON2_BOARD=sticky make firmware
ESP_CON2_BOARD=sticky bash firmware/scripts/firmware.sh -p PORT flash
ESP_CON2_BOARD=sticky python3.15 .github/package.py firmware
```

Build/config files use `build/firmware/sticky` and
`build/config/sdkconfig-sticky`; the release archive is
`build/release/esp-con2-firmware-sticky.zip`. These are isolated from generic
builds. The host tools use Sticky's USB serial port normally. The controller
firmware does not update the E-Ink display or use the onboard sensors.

On the tested Sticky, 460800 and 921600 baud produced corrupt flashing packets;
115200 completed backup, flashing, and command tests. Opening its UART bridge
with Python also reset the MCU despite deasserting DTR/RTS. Hosts therefore retry only
read-only `STATUS` probes during startup. Keep a persistent MCP/API connection
open for stable BLE sessions; opening a new connection can restart BLE pairing
or reconnection. The Go CLI preserved the running BLE session in the tested
serial opens.

Physical checks on 2026-11-10: ESP32-S3 revision 0.2, 32 MB quad flash, 8 MB PSRAM
(unused). Both Pro mode and dual Joy-Con mode reported paired, connected, and
streaming after mode-change reboots. Invalid/oversized commands were rejected,
30 consecutive status requests succeeded, and a 100 ms L+R input was accepted
and released. The board was left in Joy-Con mode with inputs released. This
checks UART commands and BLE transport; console-visible button behavior, the
input lease under cable removal, and long-term reliability still need testing.

## Virtual ESP32-S3 checks

[Espressif QEMU](https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/README.md)
emulates S3 CPU, UART, flash and PSRAM, but has no Bluetooth, native USB, or GPIO
matrix emulation. The separate `tests/qemu` project compiles the production
`main/serial_transport.hpp` with real ESP-IDF drivers and NVS. It does not mock
pairing, run the production command parser, or validate physical board wiring.
Its diagnostic images are excluded from release archives.

After installing project dependencies, install QEMU (macOS also needs
`brew install libgcrypt`), then run:

```sh
IDF_TOOLS_PATH="$PWD/.deps/idf-tools" .deps/idf-tools/python_env/idf6.1_py3.15_env/bin/python \
  .deps/esp-idf/tools/idf_tools.py install qemu-xtensa
make virtual-test
```

Eight configurations cover 2/4/8/16 MB flash with absent, quad, or octal attached
PSRAM. PSRAM remains disabled, matching production firmware. Each tests 20
request/reply cycles, fragmented input, a 400-byte response, TX saturation
recovery, software reboot, and NVS persistence across process power cycles.
Results and UART logs are saved under `build/virtual/`; `results.json` records
the exact matrix and emulator version. The full Sticky controller image is
also boot-probed separately, without counting it as a BLE test. To repeat the
virtual runs without rebuilding: `python3.15 firmware/scripts/test_virtual.py --skip-build`.

For a reproducible full-image abort backtrace, install `xtensa-esp-elf-gdb` with
the same `idf_tools.py` command, then add `--debug-production`. The 2026-11-10
run passed all eight UART/NVS cases. The full controller image did not reach
`@READY`: GDB stopped at the BT low-power clock assertion in
`btdm_low_power_mode_init`, called by `esp_bt_controller_init`. This is recorded
as an incomplete production run on an emulator without Bluetooth support,
not a successful virtual pairing test. Backtraces are in
`build/virtual/production-debugger.log`.

Hardware references: [Espressif serial connections](https://docs.espressif.com/projects/esp-idf/en/release-v6.1/esp32s3/get-started/establish-serial-connection.html),
[S3 wiring](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html),
and [pinned SDK flash-mode detection limits](https://github.com/espressif/esp-idf/blob/f0114250e205e33a945e2f3e7ec40085c5a029a2/components/esptool_py/Kconfig.projbuild).
