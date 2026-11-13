"""Package only distributable sources or outputs, never local device data."""
import os
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
kind = sys.argv[1]
output = root / 'build/release'
output.mkdir(parents=True, exist_ok=True)
if kind == 'go':
    name = f"esp-con2-{os.environ['PLATFORM']}"
    files = [(root / 'build/host/go' / os.environ['EXECUTABLE'], os.environ['EXECUTABLE'])]
elif kind == 'python':
    name = 'esp-con2-python'
    files = [(p, str(p.relative_to(root))) for p in (root / 'host/python').glob('*') if p.is_file()]
    files += [(root / p, p) for p in ['README.md', 'host/README.md', 'docs/host-setup.md', 'docs/serial-commands.md']]
elif kind == 'web':
    name = 'esp-con2-web'
    source = root / 'build/js'
    files = [(p, str(p.relative_to(source))) for p in source.rglob('*') if p.is_file()]
elif kind == 'firmware':
    # Board-specific images must not be confused with the generic USB/UART image.
    board = os.environ.get('ESP_CON2_BOARD', 'generic')
    if board not in ('generic', 'sticky'):
        raise SystemExit(f'Unknown firmware board: {board}')
    suffix = '-sticky' if board == 'sticky' else ''
    name = f'esp-con2-firmware{suffix}'
    source = root / 'build/firmware' / board
    files = [(source / p, p) for p in ['esp_con2.bin', 'bootloader/bootloader.bin', 'partition_table/partition-table.bin', 'flash_args', 'flasher_args.json']]
else:
    raise SystemExit(f'Unknown package: {kind}')
if not files:
    raise SystemExit('No files to package')
with ZipFile(output / f'{name}.zip', 'w', ZIP_DEFLATED) as archive:
    for path, destination in files:
        archive.write(path, destination)
    if kind == 'firmware':
        # Relative flash_args paths remain valid after extracting the archive.
        transport = ('Seeed reTerminal Sticky: USB-C UART0 at 115200 8N1.\n'
                     'Native USB is disabled because GPIO19/20 connect to the microphone.\n'
                     if board == 'sticky' else
                     'Commands: native USB GPIO19/20 or UART0 TX=43 RX=44 at 115200 8N1.\n'
                     'Check board wiring before use: these pins must not serve other peripherals.\n')
        archive.writestr('README.txt',
            'ESP32-S3 unified firmware; 2 MB or larger flash, no PSRAM required.\n'
            + transport +
            'Octal flash or unusual wiring may need a custom build; see firmware/README.md.\n'
            'Extract all files together. Install esptool, then run from this directory:\n'
            'python -m esptool --chip esp32s3 --port PORT --baud 115200 write-flash @flash_args\n'
            'Flashing replaces the application. No device bonds or NVS images are included.\n')
        # Ship the board guide and its references alongside the flashable images.
        for guide in ['firmware/README.md', 'docs/serial-commands.md',
                      'docs/unified-firmware.md', 'docs/verified-dual-joycon.md']:
            archive.write(root / guide, guide)
print(output / f'{name}.zip')
