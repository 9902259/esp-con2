"use strict";
// Pure encoding and parsing for the esp-con2 serial protocol (docs/serial-commands.md).
// Nothing here touches a port, a timer or the DOM.

/** Serial settings expected by the firmware: 115200 8N1, no flow control. */
export const SERIAL_OPTIONS = Object.freeze({baudRate: 115200, flowControl: 'none'});

/** Every compatible firmware begins its STATUS reply with this fingerprint. */
export const STATUS_PREFIX = '@STATUS device=esp-con2 protocol=1 ';

/** Input limits enforced by the firmware's STATE parser and lease. */
export const INPUT_LIMITS = Object.freeze({minDurationMs: 20, maxDurationMs: 10000, refreshMs: 100});

/**
 * Button names in STATE bit order: `BUTTONS[i]` is bit `i` of the hexadecimal mask.
 * @type {readonly string[]}
 */
export const BUTTONS = Object.freeze(
  'a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c'.split(' '));

const buttonBits = new Map(BUTTONS.map((name, index) => [name, 1 << index]));

/**
 * Combine button names into the STATE bit mask. Repeated names are harmless.
 * @param {Iterable<string>} names
 * @returns {number}
 */
export function buttonMask(names) {
  let mask = 0;
  for (const name of names) {
    const bit = buttonBits.get(name);
    if (bit === undefined) throw new Error(`Unknown button: ${name}.`);
    mask |= bit;
  }
  return mask;
}

/**
 * @param {number} durationMs
 * @returns {number} the validated duration
 */
export function checkDuration(durationMs) {
  if (!Number.isInteger(durationMs) || durationMs < INPUT_LIMITS.minDurationMs || durationMs > INPUT_LIMITS.maxDurationMs) {
    throw new Error('Duration must be 20–10000 ms.');
  }
  return durationMs;
}

/**
 * Build a `STATE <mask> <lx> <ly> <rx> <ry>` command (without the line terminator).
 * @param {Iterable<string>} names buttons to hold
 * @param {ArrayLike<number>} axes `[lx, ly, rx, ry]`, each from −1 to 1
 * @returns {string}
 */
export function stateCommand(names, axes) {
  if (axes.length !== 4) throw new Error('Axes must be between −1 and 1.');
  for (let i = 0; i < 4; i++) {
    const value = axes[i];
    if (!Number.isFinite(value) || Math.abs(value) > 1) throw new Error('Axes must be between −1 and 1.');
  }
  return `STATE ${buttonMask(names).toString(16)} ${axes[0]} ${axes[1]} ${axes[2]} ${axes[3]}`;
}

const encoder = new TextEncoder();
const ENCODE_CACHE_SIZE = 64;
/** @type {Map<string, Uint8Array>} */
const encoded = new Map();

/**
 * Encode a command line as ASCII bytes with its LF terminator. Recent commands
 * are cached, so repeated taps reuse their bytes; never mutate the result.
 * @param {string} command
 * @returns {Uint8Array}
 */
export function encodeCommand(command) {
  let bytes = encoded.get(command);
  if (!bytes) {
    if (encoded.size >= ENCODE_CACHE_SIZE) encoded.clear();
    bytes = encoder.encode(command + '\n');
    encoded.set(command, bytes);
  }
  return bytes;
}

/**
 * @typedef {object} Status
 * @property {string} line the raw `@STATUS …` line
 * @property {Record<string, string>} fields every `key=value` pair, e.g. `fields.paired === '1'`
 * @property {boolean} streaming whether the console is accepting input (`streaming=1`)
 * @property {string} name active controller mode, e.g. `Joy-Con 2 (L+R)`
 */

const fieldPattern = /(\w+)=(.*?)(?= \w+=|$)/g;

/**
 * Parse an esp-con2 STATUS line. Values may contain spaces (`name=Joy-Con 2 (L+R)`).
 * @param {string} line
 * @returns {Status | null} null for any other line, including other devices' STATUS
 */
export function parseStatus(line) {
  if (!line.startsWith(STATUS_PREFIX)) return null;
  /** @type {Record<string, string>} */
  const fields = {};
  for (const [, key, value] of line.slice('@STATUS '.length).matchAll(fieldPattern)) fields[key] = value;
  return {line, fields, streaming: fields.streaming === '1', name: fields.name ?? ''};
}

/**
 * Split a serial byte stream into trimmed text lines. Lines may span chunks;
 * an unterminated line longer than `maxLength` characters is discarded.
 */
export class LineSplitter {
  #decoder = new TextDecoder();
  #partial = '';
  #maxLength;

  /** @param {number} [maxLength] */
  constructor(maxLength = 8192) {
    this.#maxLength = maxLength;
  }

  /**
   * @param {Uint8Array} chunk
   * @param {(line: string) => void} onLine
   */
  push(chunk, onLine) {
    const text = this.#decoder.decode(chunk, {stream: true});
    let start = 0;
    let end = text.indexOf('\n');
    if (end === -1) {
      this.#partial += text;
    } else {
      onLine((this.#partial ? this.#partial + text.slice(0, end) : text.slice(0, end)).trim());
      start = end + 1;
      for (end = text.indexOf('\n', start); end !== -1; end = text.indexOf('\n', start)) {
        onLine(text.slice(start, end).trim());
        start = end + 1;
      }
      this.#partial = text.slice(start);
    }
    if (this.#partial.length > this.#maxLength) this.#partial = '';
  }
}
