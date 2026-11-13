# AI host setup

## JavaScript host

Use the [Web Serial control page](web-serial.md) when your AI can operate a local
desktop Chromium browser. Start it with `make web`, then select the board in the
browser's serial chooser. Wait for **Ready for input** before sending commands.

## Python MCP

Run `make python` to build the host. Register the stdio MCP server in your AI client's
own configuration. Replace the absolute path and optional port as appropriate.

Python 3.15:

```toml
[mcp_servers.esp_con2]
command = "/absolute/path/to/esp-con2/build/host/python/esp-con2-mcp"
# args = ["--port", "/dev/cu.usbmodemXXXX"]
```

The server accepts `ESP_CON2_PORT` as the default port. With one USB serial device, the
server can auto-detect it. Disconnect Web Serial and other serial tools first.
Restart/reconnect the MCP client after changing a path or rebuilding.

Tools: `list_devices`, `controller_status`, `controller_input`, `release_controls`,
`wake_console`, `reset_pairing`. Input arguments are `buttons`, `duration_ms`, and
`lx`, `ly`, `rx`, `ry`. Duration defaults to 120 ms and is bounded to 20–10000 ms;
axes are −1…1. Reset pairing only when intentionally forgetting the active bond.
Mode switching currently uses the CLI; reconnect MCP after the reboot.

The [project skill](../.agents/skills/esp-con2/SKILL.md) explains device ownership,
readiness, release behavior, and feedback limits. Codex can discover it from the
project. For other clients, share the skill file and its linked repository guides.

Example prompt:

> Use the esp-con2 skill. List devices, check readiness, wait two seconds after
> streaming starts, then press A for 100 ms and release. Do not inspect the screen.

A successful tool call confirms accepted commands, not game-state effects. Ask
for user feedback or use a separately authorized capture source when needed.
