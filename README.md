# esp-con2

Control Nintendo Switch 2 from a computer using an ESP32-S3 board:

**Computer → native USB or USB-to-UART bridge → ESP32-S3 → Bluetooth LE → Switch 2**

The default firmware uses no PSRAM and fits boards with 2 MB or more flash.
See [board requirements](firmware/README.md#board-requirements) for pins and exceptions.
For Seeed reTerminal Sticky, use `ESP_CON2_BOARD=sticky make firmware` to keep
native USB disabled on its microphone pins.

One firmware supports Pro Controller 2 or paired left/right Joy-Con 2 emulation.
Only one mode runs at a time. Mode changes reboot the ESP32-S3 board and preserve
separate pairing records. See [verified behavior](docs/verified-dual-joycon.md)
for console-tested controls and remaining limitations.

## Build and use

Install Python, Go, Node.js/npm, and connect the flashed ESP32-S3 board by USB.
From this directory:

```sh
make build
build/host/python/esp-con2 ports
build/host/python/esp-con2 status
build/host/python/esp-con2 mode joycon
# After the reboot, reopen the connection and check status.
build/host/python/esp-con2 tap a --seconds 0.1
```

Open Switch 2 **Controllers → Change Grip/Order** for initial pairing. Once both
halves stream, wait two seconds, then press L+R together to select the pair.
Use `mode pro` to switch back. CLI argument examples and MCP setup are in the
[host guide](host/README.md). Keep only one serial owner open at a time.

For browser controls:

```sh
make web
```

Open [the example](http://127.0.0.1:8765/example/) in desktop Chromium and click
**Connect ESP32-S3 board**. The compiled page and API use Web Serial directly;
Python only serves static files in this example command. Hosting `build/js/`
on HTTPS removes that local server requirement. See [Web Serial](docs/web-serial.md).

## Let an AI control it

1. Run `make go` or `make python`.
2. Register the matching MCP executable using [host setup](docs/host-setup.md).
3. Install or share [the AI skill](docs/skills/esp-con2/SKILL.md).
4. Ask the AI to check status and send a bounded input, for example:
   “Press A for 100 ms, then release.”

The MCP tools expose device discovery, status, input, release, wake, and pairing
reset. They provide no video or game-state feedback. Pairing reset forgets the
active mode's saved bond; use it only when fresh pairing is intended.

## Development

- [Firmware guide](firmware/README.md): pinned SDK, build and flashing.
- [Host guide](host/README.md): Python 3.15 and Go CLI/MCP, reusable JavaScript API.
- [Serial commands](docs/serial-commands.md): wire protocol and button masks.
- [Project folders](docs/project-layout.md): sources and generated output.
- [TODO](TODO.md): planned work, including amiibo support.

Run `make test` after `make build`; use `make firmware` to build firmware.
Builds and host mocks do not replace physical console verification.
