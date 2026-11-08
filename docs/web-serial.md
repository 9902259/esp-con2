# Web Serial API and example

`host/js/api.js` is a dependency-free strict-mode ES module. It does not
manipulate the DOM, select devices automatically, upload data, or provide video.
`host/js/example/` contains the TypeScript UI, static assets, npm dependencies,
and build script. `host/js/` contains only the reusable API.

```sh
make web-build
make web
# Open http://127.0.0.1:8765/example/ in Chromium.
```

TypeScript emits `build/js/api.js`, declarations, and
`build/js/example/app.js`; HTML/CSS are copied into `build/js/example/`.
You can host `build/js/` on HTTPS with no Python/Go backend. Localhost also works.
Serial permissions require a supporting browser and a user gesture. Do not open
compiled modules directly with `file://`; use the local server or HTTPS.

## Reuse the API

```js
'use strict';
import {EspCon2} from './api.js';
const controller = new EspCon2(line => console.log(line), () => console.log('Disconnected'));

connectButton.addEventListener('click', async () => {
  const port = await navigator.serial.requestPort();
  await controller.connect(port);
  console.log(await controller.command('STATUS'));
});
// After checking streaming readiness and allowing initialization:
await controller.input(['a'], [0, 0, 0, 0], 100);
await controller.stop();
await controller.close();
```

| Method | Contract |
| --- | --- |
| `connect(port)` | Open a browser-selected SerialPort and verify the firmware fingerprint |
| `command(text)` | Serialize a protocol request and match its acknowledgement |
| `input(buttons, axes, durationMs)` | Bounded 20–10000 ms input, lease renewal, automatic release |
| `stop()` | Cancel the current input cycle and request release |
| `close()` | Close streams/port; call stop first for normal shutdown |

Axes are `[lx, ly, rx, ry]` in −1…1. Buttons use the [serial bit names](serial-commands.md).
The constructor callbacks receive serial lines and connection closure respectively.
`ControllerSerial` remains an alias-compatible export. The API rejects overlapping
input cycles, closes on transport timeouts, and invalidates queued requests when
the session changes. Firmware lease expiry handles unplugging or suspended tabs.

Before `MODE pro` / `MODE joycon`, stop input. The board reboots: close the port and
reconnect through the normal chooser. Close MCP/CLI/serial monitors before browser
use. `make web-build` compiles the example and API. This does not validate browser
permissions, device communication, or console UI.

The example was tested on Chromium with a real ESP32-S3 board and reached Ready for
input. Simulated browser tests exercised readiness, inputs, stop, mode switching,
and desktop/mobile layout. Physical console effects still need separate feedback.
