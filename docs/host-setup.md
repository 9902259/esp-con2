# AI / MCP setup

The old `config/`, `.codex/`, and `.agents/` contents are consolidated here and in
`docs/skills/esp-con2/`; no client-specific hidden folders are required by this repo.
Build either host, then register exactly one stdio MCP server in your AI client's
own configuration. Replace the absolute path and optional port as appropriate.

Go:

```toml
[mcp_servers.esp_con2]
command = "/absolute/path/to/esp-con2/build/host/go/esp-con2"
args = ["mcp"]
# With multiple devices: args = ["mcp", "--port", "/dev/cu.usbmodemXXXX"]
```

Python 3.15:

```toml
[mcp_servers.esp_con2]
command = "/absolute/path/to/esp-con2/build/host/python/esp-con2-mcp"
# args = ["--port", "/dev/cu.usbmodemXXXX"]
```

Both accept `ESP_CON2_PORT` as the default port. With one USB serial device, the
hosts can auto-detect it. Disconnect Web Serial and other serial tools first.
Restart/reconnect the MCP client after changing a path or rebuilding.

Tools: `list_devices`, `controller_status`, `controller_input`, `release_controls`,
`wake_console`, `reset_pairing`. Input arguments are `buttons`, `duration_ms`, and
`lx`, `ly`, `rx`, `ry`. Duration defaults to 120 ms and is bounded to 20–10000 ms;
axes are −1…1. Reset pairing only when intentionally forgetting the active bond.
Mode switching currently uses the CLI; reconnect MCP after the reboot.

The portable [skill](skills/esp-con2/SKILL.md) explains device ownership, readiness,
release behavior, and feedback limits. Install that directory into your agent's
skill directory, or supply its contents manually. For example, a Codex user may
copy it into their user-level `~/.agents/skills/`; this project does not recreate
`.agents/` automatically.

Example prompt:

> Use the esp-con2 skill. List devices, check readiness, wait two seconds after
> streaming starts, then press A for 100 ms and release. Do not inspect the screen.

A successful tool call confirms accepted commands, not game-state effects. Ask
for user feedback or use a separately authorized capture source when needed.
