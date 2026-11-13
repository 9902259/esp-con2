# ESP32-S3 controller mode validation

On the connected ESP32-S3 board/Switch 2, `MODE pro` rebooted into the combined Pro
identity, completed fresh pairing, and reported paired/connected/streaming = 1.
`MODE joycon` then rebooted into the saved dual profile and both halves reached
encrypted/subscribed state. A one-second L+R chord was accepted and released in
each mode. No reflashing was needed between modes. The board was left in Joy-Con
mode with controls released. This checks transport initialization and mode
persistence; a new console button-test pass for the combined image is separate.

The observations predate the build selector consolidation. See the
[mode guide](../unified-firmware.md) for current commands and the
[Joy-Con button tests](verified-dual-joycon.md) for the earlier console results.
