#!/usr/bin/env python3
"""Capture raw dual-controller logs around a bounded L+R input attempt."""
import argparse
from pathlib import Path
import time
import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=int, default=45)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 120:
        parser.error('seconds must be between 5 and 120')
    port = serial.Serial(port=None, baudrate=115200, timeout=.05, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = args.port
    port.open()
    log_path = Path('build/logs/dual-input-diagnostic.log')
    end = time.monotonic() + args.seconds
    next_status = next_state = 0
    hold_until = None
    attempted = False
    released = False
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open('w') as log:
            while time.monotonic() < end:
                now = time.monotonic()
                if now >= next_status:
                    port.write(b'STATUS\n')
                    next_status = now + 1
                if hold_until is not None:
                    # Refresh the firmware's input lease throughout the requested two-second chord.
                    if now < hold_until and now >= next_state:
                        port.write(b'STATE 30 0 0 0 0\n')
                        next_state = now + .1
                    elif now >= hold_until and not released:
                        port.write(b'RELEASE\n')
                        released = True
                        print('L+R released', flush=True)
                line = port.readline().decode('utf8', 'replace').strip()
                if not line:
                    continue
                log.write(line + '\n')
                log.flush()
                if any(word in line for word in ('@STATUS', '@SIDES', 'connected:', 'disconnected:',
                                                 'AUTH', 'WEDGE', 'error', 'failed', '@ERR')):
                    print(line, flush=True)
                if line.startswith('@STATUS') and 'streaming=1' in line and not attempted:
                    attempted = True
                    hold_until = time.monotonic() + 2
                    print('Starting two-second L+R diagnostic', flush=True)
    finally:
        # Always neutralize controls even when capture fails or is interrupted.
        port.write(b'RELEASE\n')
        port.close()
    print(f'Capture complete: {log_path}', flush=True)


if __name__ == '__main__':
    main()
