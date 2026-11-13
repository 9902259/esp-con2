# Firmware configuration findings

The ESP32-S3 uses one firmware image with two controller modes. The S3 defaults
include extended advertising, two advertising instances, and two connections.
The combined image uses legacy Nintendo advertising PDUs through the extended
advertising API. The experimental C6 build uses the standalone Pro driver, which
requires extended advertising to be disabled.

The pinned ESP-IDF defaults to 160 MHz on C6. The project sets 240 MHz for S3.
The C6 trial also selects USB-only transport, Newlib, and the opt-in for running
without the official 5 ms timing option. Those settings belong to the C6 target.

The reTerminal Sticky uses the same S3 chip as generic boards, but routes USB-C
through UART0 and uses GPIO19/20 for its microphone. Its board overlay selects
UART-only transport and disables the native USB Serial/JTAG console and driver.

ESP-IDF loads chip-specific defaults alongside `sdkconfig.defaults`. The build
wrapper adds the Sticky overlay when requested. Combining the files would
require another mechanism to apply the chip and board conditions. The generated
configuration under `build/config/` can also retain previously selected values.
