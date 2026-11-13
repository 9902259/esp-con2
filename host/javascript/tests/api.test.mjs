import assert from 'node:assert/strict';
import test from 'node:test';
import {ControllerSerial, EspCon2, buttons, BUTTONS} from '../api.js';

const STATUS = '@STATUS device=esp-con2 protocol=1 streaming=0';

/**
 * A firmware double. `reply(command)` returns the lines to send back (default: @STATUS or @OK);
 * `replyDelayMs` defers them; `beforeReply` may hold a reply until a promise settles.
 */
function mockPort({booting = false, error = false, beforeReply, reply, replyDelayMs = 0} = {}) {
  const writes = [];
  const times = [];
  let incoming;
  const encoder = new TextEncoder();
  const port = {
    writes,
    times,
    end: () => incoming.close(),
    readable: new ReadableStream({start(controller) { incoming = controller; }}),
    writable: new WritableStream({async write(data) {
      const command = new TextDecoder().decode(data).trim();
      writes.push(command);
      times.push(performance.now());
      // Discard the initial probe as a UART bridge does while the board boots.
      if (booting && writes.length === 1) return;
      if (beforeReply) await beforeReply(command);
      const lines = reply?.(command) ?? [error ? '@ERR controller initialization' : command === 'STATUS' ? STATUS : '@OK'];
      const send = () => { for (const line of lines) incoming.enqueue(encoder.encode(line + '\n')); };
      if (replyDelayMs) setTimeout(send, replyDelayMs);
      else send();
    }}),
    async open() {},
    async setSignals() {},
    async close() { port.closed = true; },
  };
  return port;
}

test('legacy exports remain aliases', () => {
  assert.equal(ControllerSerial, EspCon2);
  assert.equal(buttons, BUTTONS);
});

test('startup retries STATUS and sends commands only once', async () => {
  const port = mockPort({booting: true});
  const api = new ControllerSerial();
  try {
    assert.equal(await api.connect(port), STATUS);
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

test('options constructor, state getters and parsed status', async () => {
  const lines = [];
  let closed = 0;
  const api = new EspCon2({onLine: line => lines.push(line), onClose: () => closed++});
  assert.equal(api.connected, false);
  await assert.rejects(api.command('STATUS'), /Connect the ESP32-S3 board first/);
  await api.connect(mockPort());
  assert.equal(api.connected, true);
  assert.equal(api.busy, false);
  const pending = api.command('WAKE');
  assert.equal(api.busy, true);
  await pending;
  const status = await api.status();
  assert.equal(status.streaming, false);
  assert.equal(status.fields.device, 'esp-con2');
  await api.close();
  assert.equal(api.connected, false);
  assert.equal(closed, 1);
  assert.deepEqual(lines, [STATUS, '@OK', STATUS]);
});

test('positional callbacks still work', async () => {
  const lines = [];
  let closed = false;
  const api = new EspCon2(line => lines.push(line), () => { closed = true; });
  await api.connect(mockPort());
  await api.close();
  assert.deepEqual(lines, [STATUS]);
  assert.equal(closed, true);
});

test('replies are matched to their request type', async () => {
  // A stray STATUS must not acknowledge MODE, and @OK must not answer STATUS.
  const port = mockPort({reply: command => command === 'MODE pro' ? [STATUS, 'boot noise', '@OK']
    : command === 'STATUS' ? ['@OK', STATUS] : undefined});
  const api = new EspCon2();
  await api.connect(port);
  try {
    assert.equal(await api.command('MODE pro'), '@OK');
    assert.equal(await api.command('STATUS'), STATUS);
  } finally { await api.close(); }
});

test('@ERR rejects one request and keeps the session open', async () => {
  const port = mockPort({reply: command => command === 'WAKE' ? ['@ERR no bond'] : undefined});
  const api = new EspCon2();
  await api.connect(port);
  try {
    await assert.rejects(api.command('WAKE'), /@ERR no bond/);
    assert.equal(api.connected, true);
    assert.equal(await api.command('RELEASE'), '@OK');
  } finally { await api.close(); }
});

test('a timeout closes the session and rejects queued requests', async () => {
  const port = mockPort({reply: command => command === 'WAKE' ? [] : undefined});
  const api = new EspCon2({timeoutMs: 50});
  await api.connect(port);
  const wake = api.command('WAKE');
  const queued = api.command('RELEASE');
  await assert.rejects(wake, /timed out/);
  await assert.rejects(queued, /Connect the ESP32-S3 board first/);
  await api.close();
  assert.equal(port.closed, true);
  assert.deepEqual(port.writes, ['STATUS', 'WAKE']);
});

test('unplugging rejects the pending request and reports closure', async () => {
  let closed = false;
  const port = mockPort({reply: command => command === 'WAKE' ? [] : undefined});
  const api = new EspCon2({onClose: () => { closed = true; }});
  await api.connect(port);
  const wake = api.command('WAKE');
  port.end();
  await assert.rejects(wake, /Serial connection closed/);
  await api.close();
  assert.equal(closed, true);
  assert.equal(port.closed, true);
});

test('invalid input is rejected before anything is written', async () => {
  const port = mockPort();
  const api = new EspCon2();
  await api.connect(port);
  try {
    await assert.rejects(api.input(['a'], [0, 0, 0, 0], 5), /Duration/);
    await assert.rejects(api.input(['a'], [0, 2, 0, 0], 100), /Axes/);
    await assert.rejects(api.input(['turbo'], [0, 0, 0, 0], 100), /Unknown button/);
    assert.deepEqual(port.writes, ['STATUS']);
  } finally { await api.close(); }
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
    assert.equal(api.inputActive, false);
  } finally {
    await api.close();
  }
});

test('overlapping inputs are rejected', async () => {
  const api = new EspCon2();
  await api.connect(mockPort());
  try {
    const first = api.input(['a'], [0, 0, 0, 0], 100);
    assert.equal(api.inputActive, true);
    await assert.rejects(api.input(['b'], [0, 0, 0, 0], 100), /already running/);
    await first;
  } finally { await api.close(); }
});

test('held chords renew the lease and release at the end', async () => {
  const port = mockPort();
  const api = new ControllerSerial();
  await api.connect(port);
  try {
    await api.input(['l', 'r', 'l'], [0, 0, 0, 0], 250);
    assert.equal(port.writes.at(-1), 'RELEASE');
    const states = port.writes.slice(1, -1);
    assert.ok(states.length >= 2 && states.length <= 3, `${states.length} refreshes`);
    assert.ok(states.every(command => command === 'STATE 30 0 0 0 0'));
  } finally {
    await api.close();
  }
});

test('slow acknowledgements do not stretch the refresh interval', async () => {
  const port = mockPort({replyDelayMs: 60});
  const api = new EspCon2();
  await api.connect(port);
  try {
    await api.input(['a'], [0, 0, 0, 0], 450);
    const times = port.times.filter((_, i) => port.writes[i].startsWith('STATE'));
    const gaps = times.slice(1).map((time, i) => time - times[i]);
    // Timing from each acknowledgement would give ≥160 ms gaps here.
    assert.ok(gaps.length >= 3 && gaps.every(gap => gap < 140), gaps.map(Math.round).join(', '));
  } finally { await api.close(); }
});
