---
name: esp-con2
description: Control a Nintendo Switch 2 through an esp-con2 ESP32 bridge, or build and troubleshoot the bridge and its host tools.
---

# esp-con2

## Choose a host

Honor the user's chosen host. Otherwise, prefer the [JavaScript API](../../../host/javascript/api.js)
in the agent's persistent Node.js runtime when it can reach the local ESP32 serial port
and has a compatible adapter. Import `EspCon2` as an ES module and retain one instance
across calls. The adapter passed to `connect(port)` must expose `open(options)`,
`setSignals(signals)`, `close()`, and WHATWG readable and writable byte streams.
The repository ships the API without a Node serial adapter.

- **Node.js:** Call `await controller.connect(port)`, then read the startup status
  from the line callback or use `await controller.command('STATUS')`. Send bounded
  input with `await controller.input(['a'], [0, 0, 0, 0], 100)` for a 100 ms A press.
  Use `stop()` to interrupt a hold, then `close()` when handing off the port.
- **Browser:** If direct Node serial access is unavailable, use the
  [Web Serial page](../../../docs/web-serial.md) in desktop Chromium. Run `make web`,
  have the user select the board in the serial chooser, and wait for **Ready for input**.
- **MCP:** If the client needs MCP, use [Python MCP setup](../../../docs/host-setup.md#python-mcp).
  Call `list_devices` and `controller_status` before input. Use `controller_input`
  for bounded input and `release_controls` to interrupt it.

## Control the console

- Keep one serial owner and reuse its connection. Reopening USB can restart the board
  or interrupt BLE. Close the current host before opening another.
- Check the active mode in `name=` and require `streaming=1` before input. For first
  pairing, have the user open **Controllers → Change Grip/Order**. For paired Joy-Con 2,
  confirm both halves are streaming, wait two seconds, then send L+R together.
- Send chords in one call and await each input before starting another. Use 20–10000 ms
  and axes in `[lx, ly, rx, ry]` order from −1 to 1. See the
  [serial reference](../../../docs/serial-commands.md) for button names and status fields.
- After a transport error, release if possible and recheck readiness before retrying.
  Wake requires a saved bond. Reset pairing only at the user's request, since it
  clears the active mode's bond.
- Use the [mode guide](../../../docs/unified-firmware.md) to switch between Pro and
  Joy-Con. The board reboots, so reconnect and recheck readiness.
- Confirm visible effects on the console or through a separate capture source.
  Serial replies confirm command acceptance.

## Build or troubleshoot

- For host work, use the [host guide](../../../host/README.md) and run `make build`
  and `make test`. Preserve input release on errors and cancellation.
- For firmware work, use the [firmware guide](../../../firmware/README.md) and run
  `make firmware`. Preserve the pinned dependencies, S3's 5 ms BLE interval support,
  and the 500 ms input lease. Preserve a recovery image when the user needs to restore
  the current application before flashing.
- For profile diagnosis, use [verified Joy-Con results](../../../docs/research/verified-dual-joycon.md)
  to distinguish pairing and streaming from console button, motion, and recovery results.
