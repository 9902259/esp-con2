# esp-con2 host clients

Each host talks directly to the same firmware serial protocol. Use one USB owner
at a time: Python, Go, and the browser cannot share a port.

| Implementation | CLI | MCP | Build |
| --- | --- | --- | --- |
| Python 3.15 | `build/host/python/esp-con2` | `build/host/python/esp-con2-mcp` | `make python` |
| Go | `build/host/go/esp-con2` | `build/host/go/esp-con2 mcp` | `make go` |
| Web Serial | Browser controls | Use Python or Go MCP instead | `make web-build` |

## Python 3.15

```sh
make python
build/host/python/esp-con2 ports
build/host/python/esp-con2 --port /dev/cu.usbmodemXXXX status
build/host/python/esp-con2 tap a --seconds 0.1
build/host/python/esp-con2 hold l+r --seconds 2
build/host/python/esp-con2 mode pro
build/host/python/esp-con2-mcp --port /dev/cu.usbmodemXXXX
```

`python/build.sh` installs requirements in `build/venv/python` and creates local
launchers. It requires `python3.15`. The MCP server keeps a persistent serial
connection and releases bounded inputs on completion/cancellation. Logs go to
stderr; stdout belongs to MCP. Direct source CLI: `python3.15 host/python/control.py`.

## Go

```sh
make go
build/host/go/esp-con2 ports
build/host/go/esp-con2 --port /dev/cu.usbmodemXXXX status
build/host/go/esp-con2 --seconds 0.1 tap a
build/host/go/esp-con2 --seconds 2 hold l+r
build/host/go/esp-con2 mode joycon
build/host/go/esp-con2 mcp --port /dev/cu.usbmodemXXXX
```

Go CLI flags precede the command; MCP accepts `esp-con2 mcp --port PORT`.
One binary contains both interfaces. No build script is required:

```sh
cd host/go
go build -trimpath -o ../../build/host/go/esp-con2 .
```

Plain `go build` in `host/go` also produces a local `esp-con2` executable.
Both implementations provide ports/status/release/wake/pair/mode, button chords,
and stick positions. Python input durations allow 0.02–60 seconds; Go/MCP input
uses 20–10000 ms. Each implementation validates axes in −1…1 and releases input.

## Browser

```sh
make web
```

Open http://127.0.0.1:8765/example/ in Chromium. Select the ESP32-S3 board in the browser
chooser and wait for readiness. The reusable [API](js/api.js) is independent
of the TypeScript [example](js/example/). Neither Python serial nor Go is
needed in the browser; the local HTTP server can be replaced with any HTTPS host.
See [Web Serial usage and API](../docs/web-serial.md).

## AI setup and pairing

Use [MCP setup](../docs/host-setup.md) with either MCP implementation and the
[portable skill](../docs/skills/esp-con2/SKILL.md). On Switch 2, open Controllers →
Change Grip/Order. Wait for `streaming=1`, allow two seconds for initialization,
then send L+R for two seconds. Verify both halves on the console. Status cannot
observe the game. Opening USB or changing mode may restart/reconnect the board.
