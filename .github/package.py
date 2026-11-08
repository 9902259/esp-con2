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
    name = 'esp-con2-firmware'
    source = root / 'build/firmware/unified'
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
        archive.writestr('README.txt', 'ESP32-S3 unified firmware. Extract all files together.\nInstall esptool, then run from this directory:\npython -m esptool --chip esp32s3 --port PORT write-flash @flash_args\nFlashing replaces the application. No device bonds or NVS images are included.\n')
print(output / f'{name}.zip')
