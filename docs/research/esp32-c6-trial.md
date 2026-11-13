# ESP32-C6 Pro Controller 2 trial

On 2026-11-10, an ESP32-C6FH4 with 4 MB flash booted the experimental Pro
Controller 2 image and accepted commands over native USB. The Switch 2 showed
a connected Pro Controller 2. The user confirmed face buttons, D-pad, shoulder
buttons and triggers, minus/plus, stick clicks, GL/GR, Capture, C, HOME, and
both analog sticks. One brief L+R attempt failed to select the controller.

The link reported paired, connected, and streaming for about 40 seconds. Later
logs showed `TX WEDGE: ENOMEM`. Negotiated connection timing, reconnect, wake,
and sustained reliability were not verified. The pinned C6 controller lacks the
official 5 ms interval option used on S3. The trial opts into running without
that check and uses USB-only transport. The S3-specific paired Joy-Con
implementation was not ported to C6.

Build instructions are in the [firmware guide](../../firmware/README.md#experimental-esp32-c6-trial).
