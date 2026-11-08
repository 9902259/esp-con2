# Project folders

| Folder | Job |
| --- | --- |
| `firmware/main/` | ESP32-S3 application and controller emulation |
| `firmware/scripts/` | SDK setup, driver generation, build/flash helper |
| `host/python/` | Python 3.15 CLI, MCP server, build script and tests |
| `host/go/` | Single Go CLI/MCP executable source and shared serial library |
| `host/js/api.js` | Reusable strict-mode Web Serial ES module |
| `host/js/example/` | TypeScript browser example and static assets |
| `docs/` | Protocol, setup and hardware validation notes |
| `docs/skills/esp-con2/` | Portable AI skill |
| `debug/` | Optional BLE/controller diagnostic programs |
| `build/host/{python,go}/` | Generated CLI and MCP launchers/executables |
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

MCP registration formerly in `config/` and `.codex/` is consolidated in
[host setup](host-setup.md); the former `.agents/` skill lives under `docs/skills/`.
No project-local hidden AI configuration is required.

Run USB diagnostics with `build/venv/python/bin/python debug/<script>.py`.
For `debug/scan_joycon.py`, first install its optional BLE dependency with
`build/venv/python/bin/python -m pip install bleak`.
