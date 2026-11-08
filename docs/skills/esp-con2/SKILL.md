---
name: esp-con2
description: Control a Nintendo Switch 2 through this project's USB-connected ESP32-S3 board using the esp-con2 MCP server, or build and troubleshoot that bridge.
---

# ESP32-S3 board Switch 2 bridge

The hardware route is Mac → USB serial → ESP32-S3 board (ESP32-S3) → BLE → Switch 2.
The unified firmware selects either a Pro Controller 2 or paired Joy-Con 2 mode.

The project also has separately tested left/right Joy-Con 2 profiles. Read the
README profile sections before changing firmware, and inspect `name=` in status
to identify what is actually flashed. The experimental dual Joy-Con profile now connects and encrypts both identities
on one Switch using a pinned-controller duplicate-peer bypass. Read the README
for the required public-address generator flag. Check both @SIDES streams;
connection success does not establish button, grip, motion, or recovery behavior.
See `docs/verified-dual-joycon.md` for console-verified buttons and current limits.
Allow two seconds after both streams become active before initial test input;
an earlier A press was missed. GL/GR send SL/SR on both halves together.
The unified firmware includes both modes: `host/python/control.py mode joycon` or
`host/python/control.py mode pro` saves the selected mode and reboots without reflashing.
Release the MCP serial session before using that CLI; reconnect afterward and
check `name=` and `streaming=1`. See `docs/unified-firmware.md` for build details.
Only one mode runs at a time; switching preserves the inactive mode's bonds.

Find the project from the MCP executable's location or the current workspace. Read its
README.md for build commands, serial setup, and MCP configuration. The executable is
`build/host/go/esp-con2 mcp`; its stdout is reserved for MCP. Use `--port /dev/cu.usbmodem…`
when more than one USB serial device exists. The MCP server keeps the serial port
open for its session. Keep the Python CLI and serial monitors closed for that entire
session. Reuse the same MCP server across calls; reopening USB can interrupt BLE.
The Web Serial page (`make web`, http://127.0.0.1:8765/example/) is another exclusive serial
owner. Disconnect it before using MCP or the CLI, and disconnect MCP before using
the browser. It provides manual controls, not an additional MCP endpoint or video.

## Control

- Call `list_devices` and `controller_status` before input. No USB device means the
  user must attach the ESP32-S3 board with a data cable. Do not substitute a Bluetooth port.
- Require `streaming=1` before `controller_input`. For first pairing, have the user
  open the console's Controllers pairing screen. Use `reset_pairing` only if they
  request fresh pairing or resetting the saved bond; it forgets the emulator's bond.
- Use `controller_input` for bounded presses, chords, or stick motion. Buttons are
  `a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c`.
  Example: `{"buttons":["l","r"],"duration_ms":1000}` to select the controller.
  Axes `lx ly rx ry` accept -1…1; omitted axes are centered. Confirm vertical-axis
  behavior on the console before relying on it in game automation.
- Each call releases all controls at completion. Duration defaults to 120 ms and is
  limited to 20–10000 ms. Hold simultaneous buttons in one call; do not parallelize
  input calls. `release_controls` stops input; `wake_console` requires a saved bond.
- This bridge has no screen capture, video feed, or game-state feedback. A successful
  command confirms serial acceptance, not a visible in-game outcome. Use a separately
  available capture source or the user's observation when feedback is needed.
- Keep actions within the user's requested game/task. A request to press a button
  does not authorize purchases, account changes, or unrelated console operations.
  After a transport error, release if possible and check status before retrying.

## Firmware work

Use the pinned dependencies in `firmware/scripts/dependencies.sh`. The S3 requires ESP-IDF's
`CONFIG_BT_CTRL_BLE_MIN_CONN_INTERVAL_ENABLE` for sustained Switch 2 input at 5 ms;
the firmware refuses to compile without it. Preserve the firmware's 500 ms input
lease and the MCP client's explicit release on errors/cancellation.

Run `make test` and `make build` for host changes; run `make firmware` for firmware
changes. Build success does not establish pairing or hardware compatibility. Flashing
replaces the current ESP32-S3 board application; preserve existing firmware before replacing
it when the user needs it. No ESP32-S3 board screen or keyboard support is implemented yet.
