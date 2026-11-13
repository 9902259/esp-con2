import assert from 'node:assert/strict';
import test from 'node:test';
import {ControllerSerial} from './api.js';

function mockPort({booting = false, error = false, beforeReply} = {}) {
  const writes = [];
  let incoming;
  const encoder = new TextEncoder();
  return {
    writes,
    readable: new ReadableStream({start(controller) { incoming = controller; }}),
    writable: new WritableStream({async write(data) {
      const command = new TextDecoder().decode(data).trim();
      writes.push(command);
      // Discard the initial probe as a UART bridge does while the board boots.
      if (booting && writes.length === 1) return;
      if (beforeReply) await beforeReply(command);
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
  const port = mockPort({booting: true});
  const api = new ControllerSerial();
  try {
    await api.connect(port);
    assert.equal(await api.command('RELEASE'), '@OK');
    assert.deepEqual(port.writes, ['STATUS', 'STATUS', 'RELEASE']);
  } finally { await api.close(); }
  assert.equal(port.closed, true);
});

test('initialization errors stop the handshake and close the port', async () => {
  const port = mockPort({booting: true, error: true});
  const api = new ControllerSerial();
  await assert.rejects(api.connect(port), /controller initialization/);
  assert.equal(port.closed, true);
  assert.deepEqual(port.writes, ['STATUS', 'STATUS']);
});

test('stop skips a STATE queued behind another command and releases once', async () => {
  const {promise: resume, resolve} = Promise.withResolvers();
  const port = mockPort({beforeReply: command => command === 'WAKE' ? resume : undefined});
  const api = new ControllerSerial();
  await api.connect(port);
  try {
    const wake = api.command('WAKE');
    const input = api.input(['a'], [0, 0, 0, 0], 1000);
    const stop = api.stop();
    resolve();
    await Promise.all([wake, input, stop]);
    assert.deepEqual(port.writes, ['STATUS', 'WAKE', 'RELEASE']);
  } finally {
    await api.close();
  }
});

test('held chords renew the lease and release at the end', async () => {
  const port = mockPort();
  const api = new ControllerSerial();
  await api.connect(port);
  try {
    await api.input(['l', 'r', 'l'], [0, 0, 0, 0], 250);
    assert.equal(port.writes.at(-1), 'RELEASE');
    const states = port.writes.slice(1, -1);
    assert.ok(states.length >= 2);
    assert.ok(states.every(command => command === 'STATE 30 0 0 0 0'));
  } finally {
    await api.close();
  }
});
