import assert from 'node:assert/strict';
import test from 'node:test';
import {ControllerSerial} from './api.js';

function bootingPort(error = false) {
  const writes = [];
  let incoming;
  const encoder = new TextEncoder();
  return {
    writes,
    readable: new ReadableStream({start(controller) { incoming = controller; }}),
    writable: new WritableStream({write(data) {
      const command = new TextDecoder().decode(data).trim();
      writes.push(command);
      // Discard the initial probe as a UART bridge does while the board boots.
      if (writes.length === 1) return;
      const reply = error ? '@ERR controller initialization' : command === 'STATUS'
        ? '@STATUS device=esp-con2 protocol=1 streaming=0' : '@OK';
      incoming.enqueue(encoder.encode(reply + '\n'));
    }}),
    async open() {},
    async setSignals() {},
    async close() { this.closed = true; },
  };
}

test('startup retries STATUS and sends commands only once', async () => {
  const port = bootingPort();
  const api = new ControllerSerial();
  try {
    await api.connect(port);
    assert.equal(await api.command('RELEASE'), '@OK');
    assert.deepEqual(port.writes, ['STATUS', 'STATUS', 'RELEASE']);
  } finally { await api.close(); }
  assert.equal(port.closed, true);
});

test('initialization errors stop the handshake and close the port', async () => {
  const port = bootingPort(true);
  const api = new ControllerSerial();
  await assert.rejects(api.connect(port), /controller initialization/);
  assert.equal(port.closed, true);
  assert.deepEqual(port.writes, ['STATUS', 'STATUS']);
});
