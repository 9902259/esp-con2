# Web Serial API and example

`host/javascript/api.js` is the entry point of a dependency-free strict-mode ES
module. It does not manipulate the DOM, select devices automatically, upload data,
or provide video. `host/javascript/example/` contains the TypeScript UI, static
assets, npm dependencies, and build script.

| File | Contents |
| --- | --- |
| `api.js` | Public exports; import from here |
| `client.js` | `EspCon2`: serial session, request queue, held input and release |
| `protocol.js` | Pure helpers: `BUTTONS`, `stateCommand`, `parseStatus`, `LineSplitter` |

```sh
make web-build
make web
# Open http://127.0.0.1:8765/example/ in Chromium.
```

TypeScript emits `build/js/{api,client,protocol}.js`, declarations, and
`build/js/example/app.js`; HTML/CSS are copied into `build/js/example/`.
You can host `build/js/` on HTTPS with no backend. Localhost also works.
Serial permissions require a supporting browser and a user gesture. Do not open
compiled modules directly with `file://`; use the local server or HTTPS.

## Reuse the API

```js
import {EspCon2} from './api.js';

const controller = new EspCon2({
  onLine: line => console.log(line),          // every serial line, including boot output
  onClose: () => console.log('Disconnected'), // the port was released
});

connectButton.addEventListener('click', async () => {
  const port = await navigator.serial.requestPort();
  await controller.connect(port);  // resolves with the startup STATUS line
});

// After `streaming=1` plus two seconds of initialization:
if ((await controller.status()).streaming) {
  await controller.input(['a'], [0, 0, 0, 0], 100);       // 100 ms A press
  await controller.input(['l', 'r'], [0, 0, 0, 0], 2000); // chord
  await controller.input([], [0, 1, 0, 0], 500);          // left stick up
}
await controller.stop();
await controller.close();
```

| Member | Contract |
| --- | --- |
| `new EspCon2({onLine, onClose, timeoutMs})` | Callbacks are optional; `timeoutMs` defaults to 3000. `new EspCon2(onLine, onClose)` also works |
| `connect(port)` | Open a SerialPort (or compatible adapter), verify the firmware fingerprint, resolve with the STATUS line |
| `command(text)` | Send one protocol request; resolve with `@OK` or the `@STATUS …` line, reject on `@ERR …` |
| `status()` | `command('STATUS')` parsed into `{line, fields, streaming, name}` |
| `input(buttons, axes, durationMs)` | Bounded 20–10000 ms input, lease renewal every 100 ms, automatic release |
| `stop()` | Cancel the current input cycle and request release |
| `close()` | Close streams/port; call stop first for normal shutdown |
| `connected`, `busy`, `inputActive` | Read-only session state, e.g. skip status polling while `busy` |

Axes are `[lx, ly, rx, ry]` in −1…1. Buttons use the [serial bit names](serial-commands.md),
exported in bit order as `BUTTONS`. `stateCommand(buttons, axes)` and `parseStatus(line)`
are pure helpers for callers that build their own transport. Type declarations are
generated from JSDoc into `build/js/*.d.ts` by `make web-build`.

`ControllerSerial` and `buttons` remain as aliases of `EspCon2` and `BUTTONS`.
Session internals such as `pending`, `port` and `writer` are private; use the
getters instead. The API rejects overlapping input cycles, closes on transport
timeouts, and rejects queued requests when the session ends. Only the startup
STATUS probe retries automatically. During a hold, the API reuses the encoded
STATE bytes and times each refresh from the previous send, so a slow acknowledgement
does not widen the gap between lease renewals. Calling stop cancels any queued
refresh and sends RELEASE. Firmware lease expiry handles unplugging or suspended tabs.

Run `make web-bench` for an in-memory throughput and latency benchmark; it never
opens a device. `make web-bench BENCH_API=path/to/other/api.js` measures another build.

Before `MODE pro` / `MODE joycon`, stop input. The board reboots: close the port and
reconnect through the normal chooser. Close MCP/CLI/serial monitors before browser
use. `make web-build` compiles the example and API. This does not validate browser
permissions, device communication, or console UI.

The example was tested on Chromium with a real ESP32-S3 board and reached Ready for
input. Simulated browser tests exercised readiness, inputs, stop, mode switching,
and desktop/mobile layout. Physical console effects still need separate feedback.
