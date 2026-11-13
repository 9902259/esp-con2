# Project folders

| Folder | Job |
| --- | --- |
| `firmware/main/` | ESP32-S3 application and controller emulation |
| `firmware/scripts/` | SDK setup, driver generation, build/flash helper |
| `host/python/` | Python 3.15 CLI, MCP server, build script and tests |
| `host/javascript/api.js` | Reusable strict-mode Web Serial ES module |
| `host/javascript/example/` | TypeScript browser example and static assets |
| `docs/` | Protocol and setup guides |
| `docs/research/` | Hardware trials, captures, and validation notes |
| `.agents/skills/esp-con2/` | Project AI skill |
| `debug/` | Optional BLE/controller diagnostic programs |
| `build/host/python/` | Generated CLI and MCP launchers/executables |
| `build/js/` | Compiled JavaScript API and declarations |
| `build/js/example/` | Compiled browser example |
| `build/venv/python/` | Python 3.15 host environment |
| `build/firmware/` | Generated ESP-IDF builds |
| `build/config/`, `build/cache/`, `build/logs/` | Generated configuration, caches, diagnostics |
| `.deps/` | Local SDK, toolchains and dependency caches |
| `backups/` | Local recovery images; never committed |

Run build commands from the project root. `make clean` removes host, JavaScript,
firmware, generated configuration and compiler caches. It preserves logs,
release images, recovery backups, SDK dependencies and the host Python environment.

See [host setup](host-setup.md) for MCP registration and the project skill.

Run USB diagnostics with `build/venv/python/bin/python debug/<script>.py`.
For `debug/scan_joycon.py`, first install its optional BLE dependency with
`build/venv/python/bin/python -m pip install bleak`.
