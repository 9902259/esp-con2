# Automated builds and releases

GitHub Actions tests Python 3.15 on Linux, macOS ARM64 and Windows AMD64.
It builds the TypeScript website and ESP32-S3
firmware using the pinned SDK. Tests use mock transports, not physical consoles.

Push a version tag after pushing the project to GitHub:

```sh
git tag v0.1.0
git push origin v0.1.0
```

Only successful tag builds publish releases. Tags containing a hyphen, such as
`v0.1.0-beta.1`, publish prereleases. Normal pushes, pull requests and manual runs
produce downloadable Actions artifacts without publishing a release.

Release assets contain Python sources (Python 3.15
and requirements installation still required), the compiled website, firmware
images with flash arguments, and `SHA256SUMS`. Extract firmware files together
and follow the included instructions. Release archives never include NVS/bonds,
local SDK installations, caches or backups. Firmware is provided as separate
generic ESP32-S3 and reTerminal Sticky archives; choose the matching board image.

## v0.1.0

- Add native USB and UART command support, configurable UART pins, a 2 MB flash
  layout, conservative DIO/40 MHz defaults, and operation without PSRAM.
- Add a UART-only reTerminal Sticky profile that leaves its microphone pins free.
- Retry read-only startup status probes in Python, Go and browser hosts to handle
  UART bridges that reset the board on connection; default flashing to 115200 baud.
- Use Python 3.15 for firmware tooling and CI, and add repeatable QEMU diagnostics.

Validation includes live Sticky pairing/streaming in both controller modes,
bounded L+R input with release, host regression tests, and eight virtual UART/NVS
configurations. QEMU does not validate Bluetooth, native USB, or physical pin wiring.
Generic images require at least 2 MB flash and compatible USB/UART wiring; octal
flash, unusual pin assignments, and board power/RF controls may need a custom
configuration. Support is broader, but every ESP32-S3 board has not been tested.

The workflow uses the repository's built-in token; no release secret is required.
Allow Actions in repository settings. The release job alone requests contents
write permission. Workflow definitions must be pushed before GitHub can run them.
