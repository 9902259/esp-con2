# One firmware, two controller modes

The ESP32-S3 firmware contains both the dual Joy-Con 2 driver and an isolated Pro
Controller 2 driver. One mode is active at a time. Changing mode saves the choice
in NVS and reboots to rebuild GATT and the Bluetooth identity cleanly.

```sh
make firmware
```

Run `bash firmware/scripts/firmware.sh -p PORT flash` to install.
Default mode on a new installation is Joy-Con L+R. The current mode is identified
by the `name=` field in `STATUS`; the `MODE` command replies `@OK` before reboot.

```sh
build/host/python/esp-con2 mode pro
build/host/python/esp-con2 mode joycon
build/host/python/esp-con2 status
```

Raw serial equivalents are `MODE pro` and `MODE joycon`. Existing `STATE`,
`RELEASE`, `STATUS`, `PAIR`, and `WAKE` commands apply to the active mode. `PAIR`
clears only the active mode's bonds. The combined Pro mode uses MAC offset 0xa0
and namespace `unifiedpro`, preserving standalone Pro records. The dual mode
retains its own MAC offset and per-half records. Pair combined Pro once separately.
Allow reconnection and controller initialization after a switch before input.

The Pro protocol is generated from the pinned upstream driver in its own class
and namespace, keeping its original report format, commands, flash data, and
pairing logic. Its advertising adapter uses legacy PDUs through the extended
advertising API so both modes can share one SDK configuration. The duplicate-peer
bypass activates only after dual-mode initialization. Optional host hooks are
linked in this image; the per-connection GATT
hooks are inactive when the dual coordinator has not been initialized.

See [controller mode validation](research/controller-mode-validation.md) for
the hardware observations and what still needs testing.
