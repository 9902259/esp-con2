"""Host-only tests: never open or send input to physical USB devices."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import Bridge


class BridgeTests(unittest.TestCase):
    def test_invalid_input_never_opens_port(self):
        bridge = Bridge('/not/a/device')
        for buttons, axes, duration in [(['bad'], [0]*4, 100), ([], [float('nan')]*4, 100), ([], [0]*4, 0)]:
            with self.assertRaises(ValueError):
                bridge.input(buttons, axes, duration)
        self.assertIsNone(bridge.port)

    def test_press_releases_after_transport_failure(self):
        bridge = Bridge()
        bridge.port = object()
        calls = []

        def request(_port, command):
            calls.append(command)
            if command.startswith('STATE'):
                raise OSError('disconnected')
            return '@OK'

        # Failure during input still attempts neutral state before closing transport.
        with patch.object(bridge, '_status', return_value='streaming=1'), patch.object(bridge, 'close') as close, patch('bridge.request', side_effect=request):
            with self.assertRaises(OSError):
                bridge.input(['a'], [0]*4, 100)
            self.assertEqual(calls[-1], 'RELEASE')
            close.assert_called_once()

    def test_press_releases(self):
        bridge = Bridge()
        with patch.object(bridge, '_status', return_value='streaming=1'), patch('bridge.request', return_value='@OK') as request:
            bridge.input(['a', 'a'], [0]*4, 20)
            self.assertEqual(request.call_args.args[1], 'RELEASE')
            self.assertTrue(request.call_args_list[0].args[1].startswith('STATE 1 '))


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_discovery_and_validation(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        # Listing tools and rejecting invalid input must not touch hardware.
        params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name('mcp_server.py')), '--port', '/not/a/device'])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 6)
                result = await client.call_tool('controller_input', {'buttons': ['invalid']})
                self.assertTrue(result.isError)


if __name__ == '__main__':
    unittest.main()
