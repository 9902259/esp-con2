// Host-side micro-benchmark for the serial client. Uses in-memory ports, never a device.
// Usage: node host/javascript/tests/bench.mjs [path/to/api.js]
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const target = process.argv[2]
  ? pathToFileURL(resolve(process.argv[2])).href
  : new URL('../api.js', import.meta.url).href;
const {EspCon2} = await import(target);
const encoder = new TextEncoder();
const decoder = new TextDecoder();
const STATUS = '@STATUS device=esp-con2 protocol=1 paired=1 connected=1 streaming=1 advertising=0 name=Joy-Con 2 (L+R)';
const OK = encoder.encode('@OK\n');
const STATUS_BYTES = encoder.encode(STATUS + '\n');
const replyTo = command => command === 'STATUS' ? STATUS_BYTES : OK;

/** Web Serial-shaped port on real WHATWG streams; replies after `latencyMs` (0 = immediately). */
function streamPort({latencyMs = 0} = {}) {
  const writes = [];
  let incoming;
  return {
    writes,
    push: bytes => incoming.enqueue(bytes),
    readable: new ReadableStream({start(controller) { incoming = controller; }}),
    writable: new WritableStream({write(data) {
      const command = decoder.decode(data).trim();
      writes.push({command, at: performance.now()});
      if (latencyMs) setTimeout(() => incoming.enqueue(replyTo(command)), latencyMs);
      else incoming.enqueue(replyTo(command));
    }}),
    async open() {},
    async setSignals() {},
    async close() {},
  };
}

/** Minimal reader/writer pair so the measurement is dominated by the client, not stream internals. */
function lightPort() {
  const chunks = [];
  let waiting = null;
  const deliver = bytes => {
    if (waiting) { const resolve = waiting; waiting = null; resolve({value: bytes, done: false}); }
    else chunks.push(bytes);
  };
  const done = Promise.resolve();
  return {
    push: deliver,
    readable: {getReader: () => ({
      read: () => chunks.length ? Promise.resolve({value: chunks.shift(), done: false})
        : new Promise(resolve => { waiting = resolve; }),
      cancel() { waiting?.({value: undefined, done: true}); waiting = null; return done; },
      releaseLock() {},
    })},
    writable: {getWriter: () => ({
      write(data) { deliver(data[0] === 0x53 && data[1] === 0x54 && data[2] === 0x41 && data[3] === 0x54 && data[4] === 0x55 ? STATUS_BYTES : OK); return done; },
      releaseLock() {},
    })},
    async open() {},
    async setSignals() {},
    async close() {},
  };
}

const median = values => values.toSorted((a, b) => a - b)[values.length >> 1];
const percentile = (values, p) => values.toSorted((a, b) => a - b)[Math.min(values.length - 1, Math.floor(values.length * p))];
const fmt = (n, digits = 2) => n.toFixed(digits);

async function requestCost(makePort, command, count = 20000, batches = 9) {
  const api = new EspCon2();
  await api.connect(makePort());
  for (let i = 0; i < count; i++) await api.command(command);
  const samples = [];
  for (let b = 0; b < batches; b++) {
    const start = performance.now();
    for (let i = 0; i < count; i++) await api.command(command);
    samples.push((performance.now() - start) * 1000 / count);
  }
  await api.close();
  return median(samples);
}

async function lineIngest(megabytes = 4, batches = 7) {
  // Status lines arrive in 4 KiB chunks that split lines at arbitrary points.
  const lineText = STATUS + ' left_tx=1234 right_tx=1234\r\n';
  const expected = Math.floor(megabytes * 1024 * 1024 / lineText.length);
  const stream = encoder.encode(lineText.repeat(expected));
  let lines = 0;
  const port = lightPort();
  const api = new EspCon2(() => { lines++; });
  await api.connect(port);
  const samples = [];
  for (let b = 0; b < batches; b++) {
    lines = 0;
    const start = performance.now();
    for (let offset = 0; offset < stream.length; offset += 4096) port.push(stream.subarray(offset, offset + 4096));
    while (lines < expected) await new Promise(resolve => setImmediate(resolve));
    samples.push(stream.length / 1024 / 1024 / ((performance.now() - start) / 1000));
  }
  await api.close();
  return median(samples);
}

async function inputLatency(runs = 300) {
  const port = streamPort();
  const api = new EspCon2();
  await api.connect(port);
  const firstWrite = [], release = [];
  for (let i = 0; i < runs; i++) {
    const before = port.writes.length;
    const start = performance.now();
    await api.input(['a'], [0, 0, 0, 0], 20);
    firstWrite.push(port.writes[before].at - start);
    release.push(port.writes.at(-1).at - (start + 20));
  }
  await api.close();
  return {firstUs: median(firstWrite) * 1000, firstP99Us: percentile(firstWrite, .99) * 1000, releaseMs: median(release)};
}

async function holdCadence(latencyMs = 10, durationMs = 2000) {
  const port = streamPort({latencyMs});
  const api = new EspCon2();
  await api.connect(port);
  const before = port.writes.length;
  await api.input(['l', 'r'], [0, 0, 0, 0], durationMs);
  const states = port.writes.slice(before).filter(write => write.command.startsWith('STATE'));
  const gaps = states.slice(1).map((write, i) => write.at - states[i].at);
  await api.close();
  return {frames: states.length, meanMs: gaps.reduce((a, b) => a + b, 0) / gaps.length, maxMs: Math.max(...gaps)};
}

// Latency runs first: the throughput loops leave a warm, GC-heavy heap that skews it.
const input = await inputLatency();
const results = {
  input,
  lightRelease: await requestCost(lightPort, 'RELEASE'),
  lightState: await requestCost(lightPort, 'STATE 30 0.5 -0.25 0 0'),
  streamRelease: await requestCost(streamPort, 'RELEASE'),
  ingest: await lineIngest(),
  cadence: await holdCadence(),
};
console.log(`module: ${target}`);
console.log(`request, light port     RELEASE ${fmt(results.lightRelease)} µs   STATE ${fmt(results.lightState)} µs`);
console.log(`request, WHATWG streams RELEASE ${fmt(results.streamRelease)} µs`);
console.log(`line ingest             ${fmt(results.ingest, 1)} MiB/s`);
console.log(`input() → first STATE   ${fmt(results.input.firstUs, 1)} µs median, ${fmt(results.input.firstP99Us, 1)} µs p99`);
console.log(`RELEASE after deadline  ${fmt(results.input.releaseMs)} ms median`);
console.log(`hold, 10 ms RTT         ${results.cadence.frames} STATE frames in 2 s, gap ${fmt(results.cadence.meanMs)} ms mean / ${fmt(results.cadence.maxMs)} ms max`);
if (process.env.BENCH_JSON) console.log(JSON.stringify(results));
