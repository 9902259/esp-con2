import assert from 'node:assert/strict';
import test from 'node:test';
import {BUTTONS, LineSplitter, buttonMask, checkDuration, encodeCommand, parseStatus, stateCommand} from '../api.js';

test('button bits follow the serial reference order', () => {
  assert.equal(BUTTONS.length, 21);
  assert.equal(buttonMask(['a']), 1);
  assert.equal(buttonMask(['l', 'r', 'l']), 0x30);
  assert.equal(buttonMask(['c']), 1 << 20);
  assert.equal(buttonMask([]), 0);
  assert.throws(() => buttonMask(['turbo']), /Unknown button: turbo/);
});

test('STATE commands match the documented wire format', () => {
  assert.equal(stateCommand(['a'], [0, 0, 0, 0]), 'STATE 1 0 0 0 0');
  assert.equal(stateCommand(['l', 'r'], [0, 0, 0, 0]), 'STATE 30 0 0 0 0');
  assert.equal(stateCommand(['home'], [-1, 0.5, 0.25, 1]), 'STATE 10000 -1 0.5 0.25 1');
  assert.equal(stateCommand([], new Float64Array([0, -0, 0, 0])), 'STATE 0 0 0 0 0');
  for (const axes of [[0, 0, 0], [0, 0, 0, 1.5], [0, NaN, 0, 0], [0, Infinity, 0, 0]]) {
    assert.throws(() => stateCommand([], axes), /Axes/);
  }
});

test('durations are integers from 20 to 10000 ms', () => {
  assert.equal(checkDuration(20), 20);
  assert.equal(checkDuration(10000), 10000);
  for (const value of [19, 10001, 100.5, NaN]) assert.throws(() => checkDuration(value), /Duration/);
});

test('encoded commands end in LF and are reused', () => {
  const bytes = encodeCommand('RELEASE');
  assert.equal(new TextDecoder().decode(bytes), 'RELEASE\n');
  assert.equal(encodeCommand('RELEASE'), bytes);
});

test('STATUS parsing keeps values that contain spaces', () => {
  const status = parseStatus('@STATUS device=esp-con2 protocol=1 paired=1 streaming=1 name=Joy-Con 2 (L+R) left_tx=12 right_tx=0');
  assert.equal(status?.streaming, true);
  assert.equal(status?.name, 'Joy-Con 2 (L+R)');
  assert.equal(status?.fields.left_tx, '12');
  assert.equal(status?.fields.paired, '1');
  assert.equal(parseStatus('@STATUS device=esp-con2 protocol=1 streaming=0')?.streaming, false);
  assert.equal(parseStatus('@STATUS device=other protocol=1 streaming=1'), null);
  assert.equal(parseStatus('@OK'), null);
});

test('lines split across chunks, CRLF and UTF-8 boundaries', () => {
  const lines = [];
  const splitter = new LineSplitter(16);
  const bytes = new TextEncoder().encode('@O');
  splitter.push(bytes, line => lines.push(line));
  splitter.push(new TextEncoder().encode('K\r\nboot ±'), line => lines.push(line));
  const tail = new TextEncoder().encode('1\n');
  const plusMinus = new TextEncoder().encode('±');
  splitter.push(plusMinus.subarray(0, 1), line => lines.push(line));
  splitter.push(plusMinus.subarray(1), line => lines.push(line));
  splitter.push(tail, line => lines.push(line));
  assert.deepEqual(lines, ['@OK', 'boot ±±1']);
  // An unterminated line beyond the limit is dropped rather than buffered forever.
  splitter.push(new TextEncoder().encode('x'.repeat(40)), line => lines.push(line));
  splitter.push(new TextEncoder().encode('@OK\n'), line => lines.push(line));
  assert.deepEqual(lines.slice(2), ['@OK']);
});
