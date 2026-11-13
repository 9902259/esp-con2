# Pro Controller 2 motion investigation

## Switch 2 calibration and USB baseline

On 2026-11-10, holding + opened the calibration flow, but the emulator could
not complete the flat-surface check. It emits zero motion data and has no live
IMU source.

A real Pro Controller 2 enumerated over USB as `057e:2069`. A read-only capture
using SDL's documented initialization collected 2,500 stationary, flat
64-byte input reports over roughly 10 seconds. The decoded acceleration
magnitude was about 9.98 m/s². This establishes a USB sensor baseline. The
USB payload and the packed BLE motion block use different formats.

## Direct BLE capture

macOS CoreBluetooth discovered the controller and its GATT services. Reports
started arriving after the controller cycled SYNC. The controller acknowledged
12 initialization commands from a public reference BLE capture, including
motion enable and input format selection. All 1,724 captured input reports
advertised a motion block length of zero. The experiment did not establish
whether encryption, further initialization, or another condition was needed.

## ESP32-S3 BLE host probe

The temporary BLE central at `firmware/debug/pro2_ble_host/` passed an AES
known-answer self-test, connected, and discovered the input, command, and
response characteristic handles (14, 22, and 30). Discovery recorded zero for
the input and response CCCD handles. The run stopped before enabling notifications
or attempting custom pairing, so it yielded no encrypted motion capture.

The original captures were recorded under `build/captures/pro2-flat/` and
`build/captures/pro2-ble/motion-debug/` on the test machine. These paths describe
the experiment artifacts and are outside the published source. A successful
BLE motion capture and console calibration are still open.
