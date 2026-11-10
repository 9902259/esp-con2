# esp-con2 TODO

- [ ] Add amiibo support: research the Switch 2 NFC command/report exchange, define
      a user-supplied data interface, implement it per supported controller mode,
      and verify on physical hardware. No amiibo emulation is implemented yet.
- [ ] Validate analog sticks, calibration, motion, and mouse reports in both modes.
- [ ] Improve dual reconnect reliability and replace timing-based readiness waits.
- [ ] Add independent left/right SL and SR controls.
- [ ] Reduce report latency while preserving fair delivery on both BLE links.
- [ ] Add a separate 1L + 1R Joy-Con 2 mode: use the left and right halves as
      independent controllers, alongside the existing paired L+R mode.
- [ ] Add gyroscope and accelerometer support: expose motion input through the
      serial protocol and host APIs, and verify reports and calibration on Switch 2.
