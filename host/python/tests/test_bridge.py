"""Host-only tests: never open or send input to physical USB devices."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import Bridge
from control import request


class StartupTests(unittest.TestCase):
    def test_lost_startup_status_is_retried(self):
        now, writes, replies = [0.0], [], []

        class Port:
            # Simulate a bridge discarding bytes until the application has booted.
            def write(self, data):
                writes.append(data)
                if len(writes) > 1:
                    replies.append(b'@STATUS device=esp-con2 protocol=1 streaming=0\n')

            def readline(self):
                now[0] += .1
                return replies.pop(0) if replies else b''

        with patch('control.time.monotonic', side_effect=lambda: now[0]):
            self.assertIn('device=esp-con2', request(Port(), 'STATUS'))
        self.assertEqual(writes, [b'STATUS\n', b'STATUS\n'])

    def test_mutating_command_is_never_retried(self):
        now, writes = [0.0], []

        class Port:
            # A missing acknowledgement must not execute a mode change twice.
            def write(self, data):
                writes.append(data)

            def readline(self):
                now[0] += .1
                return b''

        with patch('control.time.monotonic', side_effect=lambda: now[0]):
            with self.assertRaises(RuntimeError):
                request(Port(), 'MODE pro')
        self.assertEqual(writes, [b'MODE pro\n'])


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
        params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).resolve().parents[1] / 'mcp_server.py'), '--port', '/not/a/device'])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 6)
                result = await client.call_tool('controller_input', {'buttons': ['invalid']})
                self.assertTrue(result.isError)


if __name__ == '__main__':
    unittest.main()
