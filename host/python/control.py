#!/usr/bin/env python3.15
"""Control the ESP32-S3 board Switch 2 emulator over USB serial on macOS."""
import argparse
import math
import os
import time

BUTTONS = "a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c".split()


def button_mask(text):
    # Accept chords such as l+r without allowing unknown button names.
    names = text.lower().split("+")
    if any(name not in BUTTONS for name in names):
        raise argparse.ArgumentTypeError("Buttons: " + ", ".join(BUTTONS))
    return sum(1 << BUTTONS.index(name) for name in set(names))


def duration(text):
    value = float(text)
    if not math.isfinite(value) or not 0.02 <= value <= 60:
        raise argparse.ArgumentTypeError("Duration must be 0.02–60 seconds")
    return value


def axis(text):
    value = float(text)
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise argparse.ArgumentTypeError("Axis must be between -1 and 1")
    return value


def request(port, command):
    port.write((command + "\n").encode("ascii"))
    # UART bridges can reset the board on open and lose the first boot-time probe.
    retry_at = time.monotonic() + .5
    deadline = time.monotonic() + (4 if command == 'STATUS' else 2)
    while time.monotonic() < deadline:
        if command == 'STATUS' and time.monotonic() >= retry_at:
            port.write(b'STATUS\n')
            retry_at = time.monotonic() + .5
        line = port.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("@ERR"):
            raise RuntimeError(line)
        # Match the command's reply; a queued status must not acknowledge a reboot command.
        if (command == "STATUS" and line.startswith("@STATUS")) or (command != "STATUS" and line == "@OK"):
            return line
    raise RuntimeError("No response: check firmware and USB connection")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=os.environ.get("ESP_CON2_PORT"), help="USB serial port; auto-selected when exactly one exists")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("ports", "status", "pair", "wake", "release"):
        sub.add_parser(name)
    # Switching mode reboots the combined firmware and retains each mode's bond.
    mode = sub.add_parser("mode")
    mode.add_argument("profile", choices=("joycon", "pro"))
    for name in ("tap", "hold"):
        cmd = sub.add_parser(name)
        cmd.add_argument("buttons", type=button_mask, help="e.g. a or l+r")
        cmd.add_argument("--seconds", type=duration, default=0.12 if name == "tap" else 1.0)
    stick = sub.add_parser("stick")
    stick.add_argument("side", choices=("left", "right"))
    stick.add_argument("x", type=axis)
    stick.add_argument("y", type=axis)
    stick.add_argument("--seconds", type=duration, default=1.0)
    args = parser.parse_args()
    import serial
    from serial.tools import list_ports
    ports = [p for p in list_ports.comports() if "usb" in p.device.lower()]
    if args.command == "ports":
        for port in ports:
            print(port.device, port.description)
        if not ports:
            print("No USB serial devices found. Connect the ESP32-S3 board with a data cable.")
        return
    if not args.port:
        if len(ports) != 1:
            parser.error("Use --port /dev/cu.usbmodem…; run 'ports' to list devices")
        args.port = ports[0].device
    # Suppress modem-control resets and take an exclusive serial connection.
    with serial.Serial(port=None, baudrate=115200, timeout=0.1, write_timeout=1, exclusive=True) as port:
        port.dtr = False
        port.rts = False
        port.port = args.port
        port.open()
        time.sleep(0.15)
        port.reset_input_buffer()
        # Establish readiness before sending a command that must execute just once.
        status = request(port, 'STATUS')
        if args.command == "mode":
            print(request(port, 'MODE ' + args.profile))
            return
        if args.command in ("status", "pair", "wake", "release"):
            print(status if args.command == 'status' else request(port, args.command.upper()))
            return
        mask = getattr(args, "buttons", 0)
        axes = [0.0] * 4
        if args.command == "stick":
            offset = 0 if args.side == "left" else 2
            axes[offset:offset + 2] = [args.x, args.y]
        state = f"STATE {mask:x} " + " ".join(str(v) for v in axes)
        try:
            deadline = time.monotonic() + args.seconds
            while True:
                request(port, state)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.1, remaining))
        finally:
            # Explicit release on exit; firmware timeout also covers cable loss.
            request(port, "RELEASE")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit(str(error)) from error
