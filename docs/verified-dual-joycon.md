# Verified ESP32-S3 board dual Joy-Con setup

Verified on 2026-11-08: one ESP32-S3 board presents left and right Joy-Con 2
identities to one Switch 2. The route is Mac USB serial → ESP32-S3 board BLE → Switch 2.

## Observed results

- Both halves were visibly active on the Controllers page.
- The button-test screen registered A/B/X/Y, L/R/ZL/ZR, minus/plus, both stick
  clicks, and all four D-pad directions with 100 ms presses.
- The user separately confirmed Capture, C/GameChat, and HOME work.
- SL/SR were sent through the GL/GR aliases to both halves together; independent
  per-half SL/SR control and recognition have not been verified.
- Analog stick movement, calibration, motion, mouse, and long-term reconnect
  reliability remain unverified for the dual profile.

An initial A press was missed immediately after `streaming=1`; waiting two seconds
before input worked. That wait is an observed workaround, not a guaranteed readiness
signal. Earlier firmware flags reported active streams while the console did not
show a usable pair. Use console feedback when validating behavior.

## Reproduce

Install pinned dependencies using `firmware/scripts/dependencies.sh`, then:

```sh
ESP_CON2_DUAL_PUBLIC=1 python3 firmware/scripts/prepare_dual_joycon2.py
ESP_CON2_PROFILE=joycon2-dual bash firmware/scripts/firmware.sh \
  -B ../build/firmware/joycon2-dual -D SDKCONFIG="$PWD/build/config/sdkconfig-joycon2-dual" \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.dual' build
```

For flashing, use the same arguments with `-p PORT flash` in place of `build`.
Open Switch 2 Controllers → Change Grip/Order, wait for both halves to initialize,
then send L+R together for two seconds. Keep one serial owner: the MCP server and
Python scripts must not open the port concurrently. Opening USB can restart the
board, requiring reconnection and the initialization wait again.

## Implementation constraints

`firmware/main/dual_joycon.hpp` coordinates two independent protocol sessions over
one NimBLE host. Left connects first; right advertises after left is encrypted and
subscribed. The controller's public address is changed between connection setups.
The generator guards the version-specific RAM write against the expected current
address. This depends on the exact pinned S3 controller binary.

The dual-only linker wrapper bypasses `r_llm_is_dev_connected`; observation before
the bypass found positive duplicate-peer results, and the bypass enabled the second
connection. It is experimental controller behavior, not a public SDK capability.

The generator also installs optional weak hooks in the pinned NimBLE sources:
GATT declaration UUIDs and ATT read-by-type lookup use a left-specific view on the
left connection; the HCI hook collects per-connection completion counters. A clean
checkout must run the generator before building this profile. Other builds have
no active hook when the dual callback symbols are absent.

Both halves use distinct serial suffixes, separate `dual3left`/`dual3right` bond
namespaces, and a dual-only MAC offset. Reports use divisor 4 to reduce contention
(about 17 Hz per half at a 15 ms interval). Numeric notification handles select
the destination connection explicitly. Controller completions and host handoffs
are diagnostics; neither proves that the console application accepted a button.

Keep the 500 ms input lease and explicit release on every bounded input operation.
Do not infer that every experimental change was individually necessary: several
identity and timing changes accumulated before the successful console tests.

See [experiment history](dual-joycon-alternatives.md) for earlier failed attempts.
