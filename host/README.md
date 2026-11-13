# esp-con2 host clients

Each host talks directly to the same firmware serial protocol. Use one USB owner
at a time. Close the Python client before connecting from the browser.

| Implementation | CLI | MCP | Build |
| --- | --- | --- | --- |
| Python 3.15 | `build/host/python/esp-con2` | `build/host/python/esp-con2-mcp` | `make python` |
| Web Serial | Browser controls |  | `make web-build` |

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

## Browser

```sh
make web
```

Open http://127.0.0.1:8765/example/ in Chromium. Select the ESP32-S3 board in the browser
chooser and wait for readiness. The reusable [API](javascript/api.js) is independent
of the TypeScript [example](javascript/example/). The browser uses Web Serial directly. You can serve the files from any HTTPS host.
See [Web Serial usage and API](../docs/web-serial.md).

## AI setup and pairing

Use the JavaScript control page when your AI can operate a local browser with
Web Serial support. If your client needs MCP, use [Python MCP setup](../docs/host-setup.md).
For either workflow, use the
[project skill](../.agents/skills/esp-con2/SKILL.md). On Switch 2, open Controllers →
Change Grip/Order. Wait for `streaming=1`, allow two seconds for initialization,
then send L+R for two seconds. Verify both halves on the console. Status cannot
observe the game. Opening USB or changing mode may restart/reconnect the board.
