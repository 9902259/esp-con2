#!/usr/bin/env python3
"""Check that one ESP32-S3 board sustains two Joy-Con connections without screen access."""
import argparse
from pathlib import Path
import time
import serial
import sys
# Share the host protocol client rather than duplicating serial parsing.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host/python"))
from control import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--stable', type=int, default=20)
    parser.add_argument('--select-pair', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 120 or not 1 <= args.stable <= 120:
        parser.error('timeouts must be between 1 and 120 seconds')
    port = serial.Serial(port=None, baudrate=115200, timeout=.15, write_timeout=1, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = args.port
    port.open()
    log_path = Path(__file__).resolve().parents[2] / 'build/logs/joycon2-dual-live.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        end = time.monotonic() + args.timeout
        poll = time.monotonic() + 3
        streaming = False
        reconnect_requested = False
        with log_path.open('w') as log:
            while time.monotonic() < end:
                line = port.readline().decode('utf8', 'replace').strip()
                if line:
                    log.write(line + '\n')
                    log.flush()
                    if any(part in line for part in ('@STATUS', '@SIDES', 'connected:', 'disconnected:',
                                                      'dual advertising', 'failed', 'Failed', 'error', 'Error',
                                                      'abort', 'assert', 'Guru')):
                        print(line, flush=True)
                    if (line.startswith('@SIDES') and 'left_paired=1' in line and
                            'right_streaming=1' in line and 'left_connected=0' in line and
                            not reconnect_requested):
                        # The public half is already encrypted; now request the second saved bond.
                        port.write(b'WAKE\n')
                        reconnect_requested = True
                    if line.startswith('@STATUS'):
                        if 'name=Joy-Con 2 (L+R)' not in line:
                            raise RuntimeError('dual Joy-Con firmware is not active')
                        if 'streaming=1' in line:
                            streaming = True
                            break
                if time.monotonic() >= poll:
                    port.write(b'STATUS\n')
                    poll = time.monotonic() + 5
        if not streaming:
            raise RuntimeError(f'both streams did not start within {args.timeout} seconds; see {log_path}')
        if args.select_pair:
            # Select vertical paired grip with each half's shoulder button.
            until = time.monotonic() + 1
            while time.monotonic() < until:
                request(port, 'STATE 30 0 0 0 0')
                time.sleep(.08)
            request(port, 'RELEASE')
            print('L+R accepted and released.', flush=True)
        end = time.monotonic() + args.stable
        checks = 0
        while time.monotonic() < end:
            status = request(port, 'STATUS')
            if 'streaming=1' not in status:
                raise RuntimeError('a Joy-Con stream dropped: ' + status)
            checks += 1
            time.sleep(1)
        print(f'PASS: both streams stayed active for {args.stable} seconds ({checks} checks).', flush=True)
    finally:
        # Firmware leases also release input if USB disappears during this cleanup.
        try:
            request(port, 'RELEASE')
        except (RuntimeError, OSError):
            pass
        port.close()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit(str(error)) from error
