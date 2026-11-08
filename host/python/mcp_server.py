"""Python 3.15 esp-con2 MCP server; stdout is reserved for MCP JSON-RPC."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import os
import threading
from mcp.server.fastmcp import FastMCP
from bridge import Bridge, devices


def create_server(bridge):
    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            bridge.close()

    server = FastMCP('esp-con2', lifespan=lifespan)

    @server.tool()
    def list_devices() -> list[dict]:
        """List USB serial devices; does not press buttons."""
        return devices()

    @server.tool()
    def controller_status() -> str:
        """Read controller status, not screen or game state."""
        return bridge.command('STATUS')

    @server.tool()
    def release_controls() -> str:
        """Release buttons and center both sticks."""
        return bridge.command('RELEASE')

    @server.tool()
    def wake_console() -> str:
        """Request wake/reconnection using the active mode's saved bond."""
        return bridge.command('WAKE')

    @server.tool()
    def reset_pairing() -> str:
        """Forget the active bond only when the user requests pairing reset."""
        return bridge.command('PAIR')

    @server.tool()
    async def controller_input(buttons: list[str] | None = None, duration_ms: int = 120,
                               lx: float = 0, ly: float = 0, rx: float = 0, ry: float = 0) -> str:
        """Send bounded input then release; requires streaming and does not observe the console."""
        cancelled = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(bridge.input, buttons or [], [lx, ly, rx, ry], duration_ms, cancelled))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Let the worker neutralize controls before propagating cancellation.
            cancelled.set()
            try:
                await task
            finally:
                raise

    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default=os.environ.get('ESP_CON2_PORT'))
    args = parser.parse_args()
    create_server(Bridge(args.port)).run(transport='stdio')
