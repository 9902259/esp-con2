"use strict";
import {INPUT_LIMITS, LineSplitter, SERIAL_OPTIONS, STATUS_PREFIX, checkDuration, encodeCommand,
  parseStatus, stateCommand} from './protocol.js';

const RESPONSE_TIMEOUT_MS = 3000;
const STATUS_RETRY_MS = 500;
const NOT_CONNECTED = 'Connect the ESP32-S3 board first.';
const CLOSED = 'Serial connection closed.';

/**
 * The subset of the Web Serial `SerialPort` used by the client. Node adapters must
 * provide the same shape with WHATWG byte streams.
 * @typedef {object} SerialPortLike
 * @property {(options: {baudRate: number, flowControl?: string}) => Promise<void>} open
 * @property {(signals: {dataTerminalReady?: boolean, requestToSend?: boolean}) => Promise<void>} setSignals
 * @property {() => Promise<void>} close
 * @property {ReadableStream<Uint8Array>} readable
 * @property {WritableStream<Uint8Array>} writable
 */

/**
 * @typedef {object} EspCon2Options
 * @property {(line: string) => void} [onLine] receives every trimmed serial line, including boot output
 * @property {() => void} [onClose] called once the port has been released
 * @property {number} [timeoutMs] per-request acknowledgement timeout (default 3000)
 */

/**
 * @typedef {object} Request
 * @property {Uint8Array} bytes
 * @property {boolean} status matches `@STATUS` instead of `@OK`
 * @property {boolean} retry resend every 500 ms until answered (startup probe only)
 * @property {Input | null} input skipped once this input is cancelled
 * @property {(line: string | undefined) => void} resolve
 * @property {(error: Error) => void} reject
 */

/** @typedef {{cancelled: boolean, wake: (() => void) | null, release: Promise<string> | null}} Input */

/**
 * One esp-con2 serial session. Requests are sent strictly one at a time and
 * matched to their acknowledgement; `input()` renews the firmware's 500 ms
 * lease and always ends with RELEASE.
 */
export class EspCon2 {
  /** @type {(line: string) => void} */
  onLine;
  /** @type {() => void} */
  onClose;

  #timeoutMs;
  /** @type {SerialPortLike | null} */
  #port = null;
  /** @type {WritableStreamDefaultWriter<Uint8Array> | null} */
  #writer = null;
  /** @type {ReadableStreamDefaultReader<Uint8Array> | null} */
  #reader = null;
  /** @type {Promise<void> | null} */
  #opening = null;
  /** @type {Promise<void> | null} */
  #readTask = null;
  /** @type {unknown} */
  #readError = null;
  #closing = false;
  /** @type {Promise<void> | null} */
  #closeTask = null;
  /** @type {Request[]} */
  #queue = [];
  /** @type {Request | null} */
  #pending = null;
  /** @type {ReturnType<typeof setTimeout> | undefined} */
  #timer;
  /** @type {ReturnType<typeof setTimeout> | undefined} */
  #retryTimer;
  /** @type {Input | null} */
  #input = null;

  /**
   * @param {EspCon2Options | ((line: string) => void)} [options] options, or the legacy `onLine` callback
   * @param {() => void} [onClose] legacy positional close callback
   */
  constructor(options = {}, onClose) {
    const opts = typeof options === 'function' ? {onLine: options, onClose} : options;
    this.onLine = opts.onLine ?? (() => {});
    this.onClose = opts.onClose ?? (() => {});
    this.#timeoutMs = opts.timeoutMs ?? RESPONSE_TIMEOUT_MS;
  }

  /** True from a successful `connect()` until `close()` begins. */
  get connected() {
    return this.#writer !== null && !this.#closing;
  }

  /** True while a request is awaiting its acknowledgement or queued behind one. */
  get busy() {
    return this.#pending !== null || this.#queue.length > 0;
  }

  /** True while an `input()` hold is running. */
  get inputActive() {
    return this.#input !== null;
  }

  /**
   * Open a port, suppress DTR/RTS, and wait for the firmware fingerprint.
   * The STATUS probe is resent every 500 ms because opening may reboot the board.
   * @param {SerialPortLike} port e.g. from `navigator.serial.requestPort()`
   * @returns {Promise<string>} the startup STATUS line
   */
  async connect(port) {
    if (this.#port || this.#closing) throw new Error('Disconnect the current device first.');
    this.#port = port;
    try {
      this.#opening = (async () => {
        await port.open(SERIAL_OPTIONS);
        if (!this.#closing) await port.setSignals({dataTerminalReady: false, requestToSend: false});
      })();
      await this.#opening;
      if (this.#closing || this.#port !== port) throw new Error(CLOSED);
      this.#writer = port.writable.getWriter();
      this.#reader = port.readable.getReader();
      this.#readTask = this.#readLines(this.#reader);
      return /** @type {string} */ (await this.#enqueue('STATUS', {retry: true}));
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  /**
   * Send one protocol command and wait for its reply.
   * @param {string} text e.g. `'STATUS'`, `'WAKE'`, `'MODE pro'`
   * @returns {Promise<string>} `@OK`, or the `@STATUS …` line for STATUS
   * @throws on `@ERR …`, timeout (which also closes the session), or no connection
   */
  command(text) {
    return /** @type {Promise<string>} */ (this.#enqueue(text));
  }

  /**
   * Query and parse the controller status.
   * @returns {Promise<import('./protocol.js').Status>}
   */
  async status() {
    return /** @type {import('./protocol.js').Status} */ (parseStatus(await this.command('STATUS')));
  }

  /**
   * Hold buttons and stick positions for `durationMs`, renewing the lease every
   * 100 ms, then RELEASE. Rejects if another input is running.
   * @param {Iterable<string>} buttons names from `BUTTONS`, e.g. `['l', 'r']`
   * @param {ArrayLike<number>} axes `[lx, ly, rx, ry]`, each from −1 to 1
   * @param {number} durationMs integer from 20 to 10000
   * @returns {Promise<void>}
   */
  async input(buttons, axes, durationMs) {
    checkDuration(durationMs);
    const bytes = encodeCommand(stateCommand(buttons, axes));
    if (this.#input) throw new Error('An input is already running. Release it first.');
    /** @type {Input} */
    const input = {cancelled: false, wake: null, release: null};
    this.#input = input;
    const deadline = performance.now() + durationMs;
    try {
      while (true) {
        // Refreshes are timed from each send, so a slow acknowledgement does not stretch the lease gap.
        const refreshAt = performance.now() + INPUT_LIMITS.refreshMs;
        await this.#send(bytes, false, false, input);
        if (input.cancelled) break;
        if (refreshAt >= deadline) {
          // Timers may fire slightly early; never release before the requested duration.
          for (let left = deadline - performance.now(); left > 0 && !input.cancelled; left = deadline - performance.now()) {
            await this.#sleep(left, input);
          }
          break;
        }
        const wait = refreshAt - performance.now();
        if (wait > 0) await this.#sleep(wait, input);
        if (input.cancelled) break;
      }
    } finally {
      try {
        if (input.release) await input.release;
        else if (!input.cancelled && this.connected) await this.command('RELEASE');
      } finally {
        this.#input = null;
      }
    }
  }

  /**
   * Cancel any running input (including a queued refresh) and send RELEASE once.
   * @returns {Promise<void>}
   */
  async stop() {
    const input = this.#cancelInput();
    if (input?.release) {
      await input.release;
      return;
    }
    if (this.connected) {
      const release = this.command('RELEASE');
      if (input) input.release = release;
      await release;
    }
  }

  /**
   * Close the streams and port. Pending and queued requests reject.
   * Call `stop()` first for a normal shutdown.
   * @returns {Promise<void>}
   */
  async close() {
    if (this.#closing) return this.#closeTask ?? undefined;
    if (!this.#port) return;
    this.#closing = true;
    this.#cancelInput();
    const error = this.#readError instanceof Error ? this.#readError : new Error(CLOSED);
    if (this.#pending) this.#settle(error);
    for (const request of this.#queue.splice(0)) request.reject(new Error(NOT_CONNECTED));
    this.#closeTask = this.#closePort();
    return this.#closeTask;
  }

  /**
   * @param {string} text
   * @param {{retry?: boolean}} [options]
   */
  #enqueue(text, {retry = false} = {}) {
    return this.#send(encodeCommand(text), text === 'STATUS', retry, null);
  }

  /**
   * @param {Uint8Array} bytes
   * @param {boolean} status
   * @param {boolean} retry
   * @param {Input | null} input
   * @returns {Promise<string | undefined>}
   */
  #send(bytes, status, retry, input) {
    if (!this.connected) return Promise.reject(new Error(NOT_CONNECTED));
    return new Promise((resolve, reject) => {
      this.#queue.push({bytes, status, retry, input, resolve, reject});
      if (!this.#pending) this.#next();
    });
  }

  #next() {
    while (!this.#pending && this.#queue.length) {
      const request = /** @type {Request} */ (this.#queue.shift());
      if (request.input?.cancelled) {
        request.resolve(undefined);
        continue;
      }
      this.#pending = request;
      this.#timer = setTimeout(this.#onTimeout, this.#timeoutMs);
      this.#write(request);
    }
  }

  /** @param {Request} request */
  #write(request) {
    const writer = /** @type {WritableStreamDefaultWriter<Uint8Array>} */ (this.#writer);
    writer.write(request.bytes).then(() => {
      // Resend the startup probe only after its previous write has drained.
      if (request.retry && this.#pending === request) {
        this.#retryTimer = setTimeout(() => { if (this.#pending === request) this.#write(request); }, STATUS_RETRY_MS);
      }
    }, error => {
      if (this.#pending === request) this.#fail(error);
    });
  }

  #onTimeout = () => {
    this.#fail(new Error('Device response timed out. Reconnect and check the selected port.'));
  };

  /**
   * A transport failure ends the session; queued requests must not be written.
   * @param {Error} error
   */
  #fail(error) {
    if (this.#settle(error, undefined, false)) void this.close();
  }

  /**
   * Resolve or reject the in-flight request, then optionally start the next one.
   * @param {Error | null} error
   * @param {string} [line]
   * @param {boolean} [advance]
   */
  #settle(error, line, advance = true) {
    const request = this.#pending;
    if (!request) return false;
    this.#pending = null;
    clearTimeout(this.#timer);
    clearTimeout(this.#retryTimer);
    if (error) request.reject(error);
    else request.resolve(line);
    if (advance && !this.#closing) this.#next();
    return true;
  }

  /** @param {string} line */
  #receiveLine = line => {
    this.onLine(line);
    const request = this.#pending;
    if (!request) return;
    if (line.startsWith('@ERR')) this.#settle(new Error(line));
    else if (request.status ? line.startsWith(STATUS_PREFIX) : line === '@OK') this.#settle(null, line);
  };

  /** @param {ReadableStreamDefaultReader<Uint8Array>} reader */
  async #readLines(reader) {
    const lines = new LineSplitter();
    try {
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        lines.push(value, this.#receiveLine);
      }
    } catch (error) {
      this.#readError = error;
    } finally {
      reader.releaseLock();
      this.#reader = null;
      // Defer teardown until the read task can finish.
      if (!this.#closing) queueMicrotask(() => void this.close());
    }
  }

  /**
   * @param {number} delay
   * @param {Input} input
   * @returns {Promise<void>}
   */
  #sleep(delay, input) {
    return new Promise(/** @param {(value?: void) => void} resolve */ resolve => {
      const timer = setTimeout(resolve, delay);
      input.wake = () => { clearTimeout(timer); resolve(); };
    }).finally(() => { input.wake = null; });
  }

  #cancelInput() {
    const input = this.#input;
    if (input) {
      input.cancelled = true;
      input.wake?.();
    }
    return input;
  }

  async #closePort() {
    try { await this.#opening; } catch { /* Opening failed before acquiring streams. */ }
    try { await this.#reader?.cancel(); } catch { /* The device may be unplugged. */ }
    await this.#readTask;
    try { this.#writer?.releaseLock(); } catch { /* The writer may be detached. */ }
    try { await this.#port?.close(); } catch { /* The port may already be closed. */ }
    this.#writer = null;
    this.#port = null;
    this.#opening = null;
    this.#readTask = null;
    this.#readError = null;
    this.#closing = false;
    this.#closeTask = null;
    this.onClose();
  }
}
