# ESP32-S3 serial transport validation

## Seeed reTerminal Sticky

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

## QEMU UART and NVS

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

See the [firmware guide](../../firmware/README.md#virtual-esp32-s3-checks) for setup.
