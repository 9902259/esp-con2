"""Persistent serial transport shared by the esp-con2 Python MCP server."""
import math
import threading
import time
import serial
from serial.tools import list_ports
from control import BUTTONS, request


def devices():
    return [{'port': p.device, 'product': p.description} for p in list_ports.comports() if p.vid is not None]


class Bridge:
    def __init__(self, port=None):
        self.name = port
        self.port = None
        self.lock = threading.RLock()

    def close(self):
        with self.lock:
            if self.port:
                self.port.close()
                self.port = None

    def _status(self):
        if self.port is None:
            ports = devices()
            name = self.name
            if not name:
                if len(ports) != 1:
                    raise RuntimeError('Specify --port when zero or multiple USB devices exist')
                name = ports[0]['port']
            self.port = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=1, exclusive=True)
            self.port.dtr = False
            self.port.rts = False
            self.port.port = name
            self.port.open()
        status = request(self.port, 'STATUS')
        if not status.startswith('@STATUS device=esp-con2 protocol=1 '):
            raise RuntimeError('Selected device is not an esp-con2 compatible controller')
        return status

    def command(self, command):
        if command not in ['STATUS', 'RELEASE', 'WAKE', 'PAIR', 'MODE pro', 'MODE joycon']:
            raise ValueError('Unsupported command')
        with self.lock:
            try:
                status = self._status()
                result = status if command == 'STATUS' else request(self.port, command)
                if command.startswith('MODE '):
                    self.close()  # Mode changes reboot; never reuse this serial session.
                return result
            except Exception:
                self.close()
                raise

    def input(self, buttons, axes, duration_ms, cancelled=None):
        if any(b not in BUTTONS for b in buttons):
            raise ValueError('Unknown button')
        if not 20 <= duration_ms <= 10000:
            raise ValueError('duration_ms must be 20–10000')
        if len(axes) != 4 or any(not math.isfinite(v) or abs(v) > 1 for v in axes):
            raise ValueError('Axes must be finite and between −1 and 1')
        stop = cancelled or threading.Event()
        mask = sum(1 << BUTTONS.index(b) for b in set(buttons))
        with self.lock:
            try:
                if 'streaming=1' not in self._status():
                    raise RuntimeError('Controller is not streaming')
                end = time.monotonic() + duration_ms / 1000
                try:
                    # Renew the firmware lease without permitting overlapping input cycles.
                    while not stop.is_set():
                        request(self.port, f'STATE {mask:x} ' + ' '.join(map(str, axes)))
                        remaining = end - time.monotonic()
                        if remaining <= 0 or stop.wait(min(.1, remaining)):
                            break
                finally:
                    request(self.port, 'RELEASE')
                return 'Input completed and released'
            except Exception:
                self.close()
                raise
