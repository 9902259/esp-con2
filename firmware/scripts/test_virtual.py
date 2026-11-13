#!/usr/bin/env python3.15
"""Exercise real S3 UART/NVS drivers in QEMU; this does not validate BLE or USB."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/virtual'
SDK_PYTHON = ROOT / '.deps/idf-tools/python_env/idf6.1_py3.15_env/bin/python'
DIAGNOSTIC = ROOT / 'build/firmware/qemu-diagnostic'


def expect(actual, expected):
    # Keep checks and their I/O active even when Python optimization is enabled.
    if actual != expected:
        raise AssertionError(f'Expected {expected!r}, received {actual!r}')


class VirtualS3:
    def __init__(self, qemu, flash, log, psram=0, octal=False, gdb_port=None):
        self.temp = tempfile.TemporaryDirectory(prefix='esp-con2-', dir='/tmp')
        self.log = log
        self.output = log.with_suffix('.qemu.log').open('wb')
        uart = str(Path(self.temp.name) / 'uart.sock')
        monitor = str(Path(self.temp.name) / 'monitor.sock')
        args = [str(qemu), '-machine', 'esp32s3', '-display', 'none',
                '-monitor', f'unix:{monitor},server=on,wait=off',
                '-chardev', f'socket,id=uart0,path={uart},server=on,wait=on',
                '-serial', 'chardev:uart0', '-drive', f'file={flash},if=mtd,format=raw']
        if psram:
            args += ['-m', f'{psram}M']
        if octal:
            args += ['-global', 'driver=ssi_psram,property=is_octal,value=true']
        if gdb_port is not None:
            args += ['-gdb', f'tcp:127.0.0.1:{gdb_port}', '-S']
        self.process = subprocess.Popen(args, stdout=self.output, stderr=subprocess.STDOUT)
        self.uart = socket.socket(socket.AF_UNIX)
        self.buffer = b''
        self.transcript = bytearray()
        self.monitor = monitor
        try:
            deadline = time.monotonic() + 5
            while True:
                try:
                    self.uart.connect(uart)
                    break
                except (FileNotFoundError, ConnectionRefusedError):
                    if self.process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(f'QEMU did not start; see {self.output.name}')
                    time.sleep(.02)
            self.uart.settimeout(.1)
        except BaseException:
            self.close()
            raise

    def line(self, expected, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b'\n' in self.buffer:
                data, self.buffer = self.buffer.split(b'\n', 1)
                text = data.decode(errors='replace').strip()
                if text.startswith(expected):
                    return text
            try:
                data = self.uart.recv(8192)
            except socket.timeout:
                continue
            if not data:
                raise RuntimeError('QEMU UART disconnected')
            self.transcript.extend(data)
            self.buffer += data
        raise TimeoutError(f'No {expected!r}; see {self.log}')

    def command(self, text, expected):
        self.uart.sendall((text + '\n').encode())
        return self.line(expected)

    def registers(self):
        # Capture the virtual CPU location without requiring a separate GDB installation.
        with socket.socket(socket.AF_UNIX) as monitor:
            monitor.settimeout(.3)
            monitor.connect(self.monitor)
            monitor.recv(8192)
            monitor.sendall(b'stop\ninfo registers\n')
            data = bytearray()
            while True:
                try:
                    chunk = monitor.recv(8192)
                    if not chunk:
                        break
                    data.extend(chunk)
                except socket.timeout:
                    break
            return data.decode(errors='replace')

    def drain(self):
        # Recover after deliberately saturating TX; no radio state is simulated.
        self.buffer = b''
        end = time.monotonic() + 5
        while time.monotonic() < end:
            try:
                data = self.uart.recv(8192)
                if not data:
                    break
                self.transcript.extend(data)
            except socket.timeout:
                return
        raise TimeoutError('UART did not become idle after TX stress')

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.uart.close()
        self.output.close()
        self.log.write_bytes(self.transcript)
        self.temp.cleanup()


def merge(build, output, flash_mb):
    # Fresh erased images preserve the real bootloader, partition table and flash header.
    subprocess.run([str(SDK_PYTHON), '-m', 'esptool', '--chip', 'esp32s3',
                    'merge-bin', '--pad-to-size', f'{flash_mb}MB', '-o', str(output),
                    '@flash_args'], cwd=build, check=True, stdout=subprocess.DEVNULL)


def debug_production(qemu, production):
    candidates = sorted((ROOT / '.deps/idf-tools/tools/xtensa-esp-elf-gdb').glob(
        '*/xtensa-esp-elf-gdb/bin/xtensa-esp32s3-elf-gdb'))
    if not candidates:
        raise RuntimeError('Install xtensa-esp-elf-gdb with idf_tools.py for --debug-production')
    # The debugger connects only to this local virtual CPU, never a physical board.
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    flash = OUT / 'production-debug.bin'
    merge(production, flash, 2)
    vm = VirtualS3(qemu, flash, OUT / 'production-debug.uart.log', gdb_port=port)
    log = OUT / 'production-debugger.log'
    try:
        args = [str(candidates[-1]), '-batch', str(production / 'esp_con2.elf')]
        for command in ['set pagination off', f'target remote 127.0.0.1:{port}',
                        'hbreak _esp_error_check_failed', 'hbreak panic_abort',
                        'hbreak esp_panic_handler', 'continue', 'bt', 'info registers a2 a3 pc']:
            args += ['-ex', command]
        with log.open('w') as output:
            subprocess.run(args, stdout=output, stderr=subprocess.STDOUT, timeout=30, check=True)
    finally:
        vm.close()
    return log.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-build', action='store_true')
    parser.add_argument('--debug-production', action='store_true')
    args = parser.parse_args()
    candidates = sorted((ROOT / '.deps/idf-tools/tools/qemu-xtensa').glob('*/qemu/bin/qemu-system-xtensa'))
    qemu = Path(os.environ['ESP_CON2_QEMU']) if os.environ.get('ESP_CON2_QEMU') else next(iter(candidates), None)
    if qemu is None:
        raise SystemExit('Install qemu-xtensa with ESP-IDF idf_tools.py first; see firmware/README.md.')
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.skip_build:
        subprocess.run(['bash', 'firmware/scripts/firmware.sh', '-C', 'tests/qemu',
                        '-B', str(DIAGNOSTIC), '-D', f'SDKCONFIG={ROOT}/build/config/sdkconfig-qemu-diagnostic',
                        '-D', 'SDKCONFIG_DEFAULTS=sdkconfig.defaults', 'build'], cwd=ROOT, check=True)
    report = {'qemu': subprocess.check_output([str(qemu), '--version'], text=True).splitlines()[0],
              'coverage': 'Production UART transport and ESP-IDF NVS; no BLE, USB or GPIO wiring validation',
              'cases': []}
    configurations = [(2, 0, False), (2, 2, False), (4, 0, False), (4, 4, False),
                      (8, 0, False), (8, 8, False), (16, 0, False), (16, 8, True)]
    for flash_mb, psram_mb, octal in configurations:
        name = f'flash-{flash_mb}m-psram-{psram_mb}m' + ('-octal' if octal else '')
        flash = OUT / f'{name}.bin'
        merge(DIAGNOSTIC, flash, flash_mb)
        vm = VirtualS3(qemu, flash, OUT / f'{name}.uart.log', psram_mb, octal)
        try:
            expect(vm.line('@VTEST READY'), '@VTEST READY boots=1')
            for _ in range(20):
                expect(vm.command('PING', '@VTEST PONG'), '@VTEST PONG')
            vm.uart.sendall(b'PI')
            time.sleep(.02)
            vm.uart.sendall(b'NG\n')
            expect(vm.line('@VTEST PONG'), '@VTEST PONG')
            expect(vm.command('LONG', '@VTEST LONG'), '@VTEST LONG ' + 'x' * 400)
            vm.uart.sendall(b'LONG\n' * 100)
            time.sleep(.2)
            vm.drain()
            expect(vm.command('PING', '@VTEST PONG'), '@VTEST PONG')
            vm.command('REBOOT', '@VTEST REBOOT')
            expect(vm.line('@VTEST READY'), '@VTEST READY boots=2')
        finally:
            vm.close()
        vm = VirtualS3(qemu, flash, OUT / f'{name}.power-cycle.uart.log', psram_mb, octal)
        try:
            expect(vm.line('@VTEST READY'), '@VTEST READY boots=3')
            expect(vm.command('PING', '@VTEST PONG'), '@VTEST PONG')
        finally:
            vm.close()
        report['cases'].append({'flash_mb': flash_mb, 'attached_psram_mb': psram_mb,
                                'octal_psram': octal, 'psram_initialized': False, 'result': 'passed'})
        print(f'PASS {name}: UART, long replies, TX stress, reset and persistent NVS', flush=True)
    production = ROOT / 'build/firmware/sticky'
    flash = OUT / 'production-sticky.bin'
    merge(production, flash, 2)
    vm = VirtualS3(qemu, flash, OUT / 'production-sticky.uart.log')
    try:
        try:
            ready = vm.line('@READY', timeout=5)
        except TimeoutError:
            ready = None
        registers = vm.registers()
        (OUT / 'production-registers.txt').write_text(registers)
        report['production_probe'] = {'ready': ready, 'registers': 'production-registers.txt',
                                      'software_resets': vm.transcript.count(b'RTC_SW_CPU_RST'),
                                      'ble_validation': 'unsupported by QEMU'}
    finally:
        vm.close()
    if args.debug_production:
        report['production_probe']['debugger_log'] = debug_production(qemu, production)
    print(f'Full controller image: ready={ready!r}; BLE validation unsupported by QEMU.', flush=True)
    (OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {OUT}/results.json; full BLE/USB validation requires hardware.')


if __name__ == '__main__':
    main()
