# esp-con2

Control Nintendo Switch 2 from a computer using an ESP32-S3 board:

**Computer → native USB or USB-to-UART bridge → ESP32-S3 → Bluetooth LE → Switch 2**

The default firmware uses no PSRAM and fits boards with 2 MB or more flash.
See [board requirements](firmware/README.md#board-requirements) for pins and exceptions.
For Seeed reTerminal Sticky, use `ESP_CON2_BOARD=sticky make firmware` to keep
native USB disabled on its microphone pins.

One firmware supports Pro Controller 2 or paired left/right Joy-Con 2 emulation.
Only one mode runs at a time. Mode changes reboot the ESP32-S3 board and preserve
separate pairing records. See [verified behavior](docs/research/verified-dual-joycon.md)
for console-tested controls and remaining limitations.

## Build and use

Install Python, Node.js/npm, and connect the flashed ESP32-S3 board by USB.
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

Use the **JavaScript host** when the AI can control a local desktop Chromium
browser. Run `make web`, open [the control page](http://127.0.0.1:8765/example/),
and select the ESP32-S3 board in the browser's serial chooser. Once the page
shows **Ready for input**, ask the AI to use its controls.

For clients that need MCP, run `make python` and register the server using the
[host setup guide](docs/host-setup.md). The [project skill](.agents/skills/esp-con2/SKILL.md)
covers both paths. To verify a game action, check the Switch 2 screen separately.

## Development

- [Firmware guide](firmware/README.md): pinned SDK, build and flashing.
- [Host guide](host/README.md): Python 3.15 CLI/MCP, reusable JavaScript API.
- [Serial commands](docs/serial-commands.md): wire protocol and button masks.
- [Project folders](docs/project-layout.md): sources and generated output.
- [Research notes](docs/research/README.md): hardware trials and validation results.
- [TODO](TODO.md): planned work, including amiibo support.

Run `make test` after `make build`; use `make firmware` to build firmware.
Builds and host mocks do not replace physical console verification.
