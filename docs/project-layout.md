# Project folders

```text
firmware/            ESP-IDF project (ESP32-S3 application)
  main/              Controller emulation, serial transport, Kconfig options
  scripts/           Dependency install, driver generation, idf.sh build/flash wrapper
  tests/qemu/        Virtual UART/NVS diagnostic project and run.py runner
host/
  python/            Python 3.15 CLI, MCP server and build script
    tests/           Host-only unit and MCP tests
  javascript/        Reusable Web Serial API module (api.js)
    example/         TypeScript browser example and static assets
    tests/           Node tests for the API
scripts/
  package.py         Release archive packaging used by CI and local releases
  diagnostics/       Optional BLE/controller hardware diagnostics
docs/                Protocol, setup and release guides
  research/          Hardware trials, captures, and validation notes
.agents/skills/      Project AI skill
.github/workflows/   CI build, test and release
```

Generated and local-only folders (ignored by git):

| Folder | Job |
| --- | --- |
| `build/host/python/` | Generated CLI and MCP launchers/executables |
| `build/js/` | Compiled JavaScript API and declarations |
| `build/js/example/` | Compiled browser example |
| `build/venv/python/` | Python 3.15 host environment |
| `build/firmware/` | Generated ESP-IDF builds |
| `build/config/`, `build/cache/`, `build/logs/` | Generated configuration, caches, diagnostics |
| `build/release/` | Release archives from `scripts/package.py` |
| `.deps/` | Local SDK, toolchains, generated drivers and dependency caches |
| `backups/` | Local recovery images; never committed |

Run build commands from the project root. `make clean` removes host, JavaScript,
firmware, generated configuration and compiler caches. It preserves logs,
release images, recovery backups, SDK dependencies and the host Python environment.

See [host setup](host-setup.md) for MCP registration and the project skill.

Run USB diagnostics with `build/venv/python/bin/python scripts/diagnostics/<script>.py`.
For `scripts/diagnostics/scan_joycon.py`, first install its optional BLE dependency with
`build/venv/python/bin/python -m pip install bleak`.
