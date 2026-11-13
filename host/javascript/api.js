"use strict";

const BAUD_RATE = 115200;
const RESPONSE_TIMEOUT_MS = 3000;
const STATUS_RETRY_MS = 500;
const INPUT_REFRESH_MS = 100;
const MAX_BUFFER_LENGTH = 8192;
const STATUS_PREFIX = '@STATUS device=esp-con2 protocol=1 ';
const encoder = new TextEncoder();

export const buttons = 'a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c'.split(' ');
const buttonBits = new Map(buttons.map((name, index) => [name, 1 << index]));

function inputCommand(names, axes, duration) {
  if (!Number.isInteger(duration) || duration < 20 || duration > 10000) {
    throw new Error('Duration must be 20–10000 ms.');
  }
  if (axes.length !== 4 || Array.from(axes).some(value => !Number.isFinite(value) || Math.abs(value) > 1)) {
    throw new Error('Axes must be between −1 and 1.');
  }
  let mask = 0;
  for (const name of names) {
    const bit = buttonBits.get(name);
    if (bit === undefined) throw new Error('Unknown button.');
    mask |= bit;
  }
  return `STATE ${mask.toString(16)} ${axes.join(' ')}`;
}

export class ControllerSerial {
  /** @param {(line: string) => void} onLine @param {() => void} onClose */
  constructor(onLine = () => {}, onClose = () => {}) {
    this.onLine = onLine;
    this.onClose = onClose;
    this.tail = Promise.resolve();
  }

  async connect(port) {
    if (this.port || this.closing) throw new Error('Disconnect the current device first.');
    this.port = port;
    try {
      this.opening = (async () => {
        await port.open({baudRate: BAUD_RATE, flowControl: 'none'});
        if (!this.closing) {
          await port.setSignals({dataTerminalReady: false, requestToSend: false});
        }
      })();
      await this.opening;
      if (this.closing || this.port !== port) throw new Error('Serial connection closed.');
      this.writer = port.writable.getWriter();
      this.reader = port.readable.getReader();
      this.readTask = this.#readLines(this.reader);
      await this.#enqueue('STATUS', {retry: true});
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  async #readLines(reader) {
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let start = 0;
        for (let end = buffer.indexOf('\n'); end !== -1; end = buffer.indexOf('\n', start)) {
          this.#receiveLine(buffer.slice(start, end).trim());
          start = end + 1;
        }
        if (start) buffer = buffer.slice(start);
        if (buffer.length > MAX_BUFFER_LENGTH) buffer = '';
      }
    } catch (error) {
      this.readError = error;
    } finally {
      reader.releaseLock();
      this.reader = null;
      // Defer teardown until the read task can finish.
      if (!this.closing) queueMicrotask(() => void this.close());
    }
  }

  #receiveLine(line) {
    this.onLine(line);
    const pending = this.pending;
    if (!pending) return;
    if (line.startsWith('@ERR')) this.#settle(pending, new Error(line));
    else if (pending.status ? line.startsWith(STATUS_PREFIX) : line === '@OK') {
      this.#settle(pending, null, line);
    }
  }

  #settle(pending, error, line) {
    if (!pending || this.pending !== pending) return false;
    this.pending = null;
    clearTimeout(pending.timer);
    clearTimeout(pending.retryTimer);
    if (error) pending.reject(error);
    else pending.resolve(line);
    return true;
  }

  command(text) {
    return this.#enqueue(text);
  }

  #enqueue(text, {retry = false, input, bytes} = {}) {
    const writer = this.writer;
    const run = this.tail.then(() => {
      if (input?.cancelled) return;
      if (!writer || this.writer !== writer || this.closing) {
        throw new Error('Connect the ESP32-S3 board first.');
      }
      return this.#request(writer, bytes ?? encoder.encode(text + '\n'), text === 'STATUS', retry);
    });
    this.tail = run.catch(() => {});
    return run;
  }

  #request(writer, bytes, status, retry) {
    return new Promise((resolve, reject) => {
      const pending = {resolve, reject, status};
      const fail = error => {
        if (this.#settle(pending, error)) void this.close();
      };
      this.pending = pending;
      pending.timer = setTimeout(() => {
        fail(new Error('Device response timed out. Reconnect and check the selected port.'));
      }, RESPONSE_TIMEOUT_MS);

      // Retry the startup probe only after its previous write has drained.
      const send = async () => {
        try {
          await writer.write(bytes);
          if (retry && this.pending === pending) pending.retryTimer = setTimeout(send, STATUS_RETRY_MS);
        } catch (error) {
          fail(error);
        }
      };
      void send();
    });
  }

  /** @param {string[]} names @param {number[]} axes @param {number} duration */
  async input(names, axes, duration) {
    const text = inputCommand(names, axes, duration);
    if (this.activeInput) throw new Error('An input is already running. Release it first.');
    const input = {cancelled: false, wake: null, release: null};
    this.activeInput = input;
    const deadline = performance.now() + duration;
    const bytes = encoder.encode(text + '\n');
    try {
      do {
        await this.#enqueue(text, {input, bytes});
        const delay = Math.min(INPUT_REFRESH_MS, deadline - performance.now());
        if (input.cancelled || delay <= 0) break;
        await new Promise(resolve => {
          const timer = setTimeout(resolve, delay);
          input.wake = () => { clearTimeout(timer); resolve(); };
        });
        input.wake = null;
      } while (!input.cancelled && performance.now() < deadline);
    } finally {
      try {
        if (input.release) await input.release;
        else if (!input.cancelled && this.writer && !this.closing) await this.command('RELEASE');
      } finally {
        this.activeInput = null;
      }
    }
  }

  #cancelInput() {
    const input = this.activeInput;
    if (input) {
      input.cancelled = true;
      input.wake?.();
    }
    return input;
  }

  async stop() {
    const input = this.#cancelInput();
    if (input?.release) return input.release;
    if (this.writer && !this.closing) {
      const release = this.command('RELEASE');
      if (input) input.release = release;
      await release;
    }
  }

  async close() {
    if (this.closing) return this.closeTask;
    if (!this.port) return;
    this.closing = true;
    this.#cancelInput();
    this.#settle(this.pending, this.readError || new Error('Serial connection closed.'));
    this.closeTask = this.#closePort();
    return this.closeTask;
  }

  async #closePort() {
    try { await this.opening; } catch { /* Opening failed before acquiring streams. */ }
    try { await this.reader?.cancel(); } catch { /* The device may be unplugged. */ }
    await this.readTask;
    try { this.writer?.releaseLock(); } catch { /* The writer may be detached. */ }
    try { await this.port.close(); } catch { /* The port may already be closed. */ }
    this.writer = null;
    this.port = null;
    this.opening = null;
    this.readTask = null;
    this.readError = null;
    this.closing = false;
    this.onClose();
  }
}

export {ControllerSerial as EspCon2};
