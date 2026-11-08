#!/usr/bin/env python3
"""Observe Nintendo BLE advertisements; macOS identifiers are UUIDs, not MACs."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from bleak import BleakScanner


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path, default=Path('build/logs/joycon-scan.jsonl'))
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('seconds must be between 1 and 120')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with args.output.open('w') as log:
        def detected(device, advertisement):
            # Ignore unrelated nearby devices and retain only Nintendo manufacturer data.
            payload = advertisement.manufacturer_data.get(0x0553)
            if payload is None:
                return
            record = dict(time=time.time(), identifier=device.address,
                          name=advertisement.local_name, rssi=advertisement.rssi,
                          manufacturer=payload.hex())
            log.write(json.dumps(record) + '\n')
            log.flush()
            key = (device.address, payload, advertisement.local_name)
            if key not in seen:
                seen.add(key)
                print(json.dumps(record), flush=True)
        async with BleakScanner(detection_callback=detected):
            await asyncio.sleep(args.seconds)
    print(f'Scan complete: {len(seen)} distinct advertisement records; {args.output}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
