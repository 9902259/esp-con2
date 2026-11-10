"use strict";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
export const buttons = 'a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c'.split(' ');

export class ControllerSerial {
  /** @param {(line: string) => void} onLine @param {() => void} onClose */
  constructor(onLine = () => {}, onClose = () => {}) {
    this.onLine = onLine; this.onClose = onClose; this.tail = Promise.resolve(); this.generation = 0; this.session = 0;
  }
  async connect(port) {
    if (this.port) throw new Error('Disconnect the current device first.');
    this.port = port;
    ++this.session;
    try {
      await port.open({baudRate: 115200, flowControl: 'none'});
      await port.setSignals({dataTerminalReady: false, requestToSend: false});
      this.writer = port.writable.getWriter(); this.reader = port.readable.getReader();
      this.readTask = this.read();
      await this.command('STATUS');
    } catch (error) { await this.close(); throw error; }
  }
  async read() {
    const decoder = new TextDecoder(); let buffer = '';
    try {
      while (true) {
        const {value, done} = await this.reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let end;
        while ((end = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, end).trim(); buffer = buffer.slice(end + 1);
          this.onLine(line);
          const pending = this.pending;
          // Boot/debug output and stale status lines must never acknowledge another command.
          if (pending && (line.startsWith('@ERR') || (pending.status
            ? /^@STATUS device=esp-con2 protocol=1 /.test(line)
            : line === '@OK'))) {
            this.pending = null; clearTimeout(pending.timer); clearInterval(pending.retryTimer);
            if (line.startsWith('@ERR')) pending.reject(new Error(line)); else pending.resolve(line);
          }
        }
        if (buffer.length > 8192) buffer = '';
      }
    } catch (error) { this.readError = error; }
    finally {
      this.reader.releaseLock(); this.reader = null;
      // Defer teardown so it never waits on its own read task.
      if (!this.closing) setTimeout(() => this.close(), 0);
    }
  }
  command(text) {
    const session = this.session;
    const run = this.tail.catch(() => {}).then(() => new Promise((resolve, reject) => {
      if (!this.writer || this.closing || this.session !== session) { reject(new Error('Connect the ESP32-S3 board first.')); return; }
      const timer = setTimeout(() => {
        clearInterval(this.pending?.retryTimer);
        this.pending = null; reject(new Error('Device response timed out. Reconnect and check the selected port.'));
        // Closing prevents a late reply from being mistaken for the next request.
        void this.close();
      }, 3000);
      const pending = {resolve, reject, timer, status: text === 'STATUS'};
      const send = () => {
        if (this.pending !== pending) return;
        this.writer.write(new TextEncoder().encode(text + '\n')).catch(error => {
          clearTimeout(timer); clearInterval(pending.retryTimer);
          this.pending = null; reject(error); void this.close();
        });
      };
      // Re-probe readiness if opening a UART bridge rebooted the board; inputs never repeat here.
      if (pending.status) pending.retryTimer = setInterval(send, 500);
      this.pending = pending;
      send();
    }));
    this.tail = run; return run;
  }
  /** @param {string[]} names @param {number[]} axes @param {number} duration */
  async input(names, axes, duration) {
    if (!Number.isInteger(duration) || duration < 20 || duration > 10000) throw new Error('Duration must be 20–10000 ms.');
    if (axes.length !== 4 || axes.some(v => !Number.isFinite(v) || Math.abs(v) > 1)) throw new Error('Axes must be between −1 and 1.');
    if (names.some(name => !buttons.includes(name))) throw new Error('Unknown button.');
    if (this.inputActive) throw new Error('An input is already running. Release it first.');
    this.inputActive = true;
    const mask = [...new Set(names)].reduce((value, name) => value | (1 << buttons.indexOf(name)), 0);
    const generation = ++this.generation;
    const end = performance.now() + duration;
    try {
      do {
        if (generation !== this.generation) break;
        await this.command(`STATE ${mask.toString(16)} ${axes.join(' ')}`);
        await sleep(Math.max(0, Math.min(100, end - performance.now())));
      } while (performance.now() < end);
    } finally {
      try { if (this.writer && !this.closing) await this.command('RELEASE'); }
      finally { this.inputActive = false; }
    }
  }
  async stop() { ++this.generation; if (this.writer && !this.closing) await this.command('RELEASE'); }
  async close() {
    if (this.closing) return this.closeTask;
    this.closing = true; ++this.generation; ++this.session;
    this.closeTask = (async () => {
      if (this.pending) {
        clearTimeout(this.pending.timer); clearInterval(this.pending.retryTimer);
        this.pending.reject(this.readError || new Error('Serial connection closed.')); this.pending = null;
      }
      try {
        await this.reader?.cancel(); await this.readTask;
      } catch { /* Unplugging can make close fail after the OS already removed the port. */ }
      finally {
        try { this.writer?.releaseLock(); } catch { /* Writer may already be detached. */ }
        try { await this.port?.close(); } catch { /* A removed device is already closed. */ }
        this.writer = null; this.port = null; this.readTask = null; this.readError = null;
        this.closing = false; this.onClose();
      }
    })();
    return this.closeTask;
  }
}

// Public project name; the original class export remains available to existing consumers.
export { ControllerSerial as EspCon2 };
