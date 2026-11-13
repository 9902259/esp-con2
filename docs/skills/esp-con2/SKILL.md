---
name: esp-con2
description: Control a Nintendo Switch 2 through the esp-con2 USB-to-BLE bridge, or build and troubleshoot its ESP32-S3 firmware and host tools.
---

# esp-con2

The host sends commands over USB serial to an ESP32-S3, which emulates a controller over BLE. Locate the repository from the current workspace or the MCP executable. Use the [project README](../../../README.md) for the supported board, build, and setup paths.

## Control the console

1. Call `list_devices` and `controller_status`. If no board appears, ask the user to attach it with a USB data cable. Use the board's USB serial port. If multiple devices appear, select the board explicitly with `--port`.
2. Check `name=` for the active profile and require `streaming=1` before sending input. For first pairing, have the user open **Controllers → Change Grip/Order**. For paired Joy-Con 2, verify both `@SIDES` streams, wait two seconds after both are active, then send L+R together to select the pair.
3. Send the requested input with `controller_input`. Put chords in one call and send input calls sequentially. Each call releases all controls when it finishes.
4. After a transport error, call `release_controls` if possible and check status before retrying. Serial acceptance confirms the command reached the bridge. Use console observation or a separate capture source to verify an on-screen result.

| Input | Values |
| --- | --- |
| Buttons | `a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c` |
| Sticks | `lx ly rx ry` from -1 to 1. Omitted axes are centered. Verify vertical direction on the console before automating it. |
| Duration | `duration_ms` from 20 to 10000 ms, default 120 ms. |

For example, send `{"buttons":["l","r"],"duration_ms":1000}` for a one-second L+R chord. In paired Joy-Con 2 mode, GL and GR send SL and SR respectively on both halves together.

Use `release_controls` to stop input and `wake_console` only when a saved bond exists. Use `reset_pairing` only when the user requests fresh pairing or removal of the active mode's saved bond. Keep input within the requested console task.

## Choose or switch the serial owner

Use one serial owner at a time. Keep the same MCP session across calls because reopening USB can interrupt BLE. Release MCP, the CLI, any serial monitor, or the Web Serial page before handing the port to another client.

- **MCP.** Read [host setup](../../host-setup.md) for the Go or Python executable and registration. The Go entry point is `build/host/go/esp-con2 mcp`. Reserve its stdout for MCP.
- **Mode change.** On ESP32-S3, release MCP and run `build/host/python/esp-con2 mode joycon` or `build/host/python/esp-con2 mode pro`. The board saves the selection and reboots without reflashing. Only one mode runs at a time and each mode keeps its own bonds. Reconnect MCP and check `name=` and `streaming=1` before input.
- **Manual browser control.** Read [Web Serial](../../web-serial.md) for `make web` and browser setup. The browser owns the same serial port while connected.

## Build or troubleshoot

- **Host changes.** Use the [host guide](../../../host/README.md) for CLI and MCP entry points. Run `make build`, then `make test`. Read [serial commands](../../serial-commands.md) when changing the wire protocol. Preserve the MCP client's explicit release on errors or cancellation.
- **Firmware changes.** Use the [firmware guide](../../../firmware/README.md) and pinned dependencies in `firmware/scripts/dependencies.sh`. Run `make firmware`. On ESP32-S3, keep `CONFIG_BT_CTRL_BLE_MIN_CONN_INTERVAL_ENABLE` for sustained 5 ms input and preserve the 500 ms input lease. Flashing replaces the board application. Preserve the existing firmware if the user needs to restore it.
- **Profile diagnosis.** Check `name=` before choosing instructions. Read [unified firmware](../../unified-firmware.md) for mode switching and [verified dual Joy-Con behavior](../../verified-dual-joycon.md) for console results and limits. Connection and encryption alone do not establish button, grip, motion, or recovery behavior.

Report build results and physical console results separately. The bridge provides no video or game-state feedback.
