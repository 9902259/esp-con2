import {BUTTONS, EspCon2, parseStatus} from '../api.js';
import type {SerialPortLike} from '../api.js';
// Web Serial is an optional browser API, absent from TypeScript's standard DOM types.
const serialAccess = (navigator as Navigator & {serial: {requestPort(): Promise<SerialPortLike>}}).serial;
// All example DOM lookups are checked once at their point of use.
const $ = (id: string): HTMLElement => {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing element: ${id}`);
  return node;
};
const button = (id: string) => $(id) as HTMLButtonElement;
const field = (id: string) => $(id) as HTMLInputElement;
let connected = false, ready = false, busy = false, readyAt = 0;
let poll: ReturnType<typeof setInterval> | undefined;
const axes = ['lx', 'ly', 'rx', 'ry'];
const labels: Record<string, string> = {minus:'−',plus:'+',lstick:'L stick',rstick:'R stick',gl:'SL / GL',gr:'SR / GR',capture:'Capture',home:'HOME',c:'C / GameChat'};
function render() {
  button('connect').disabled = connected || busy || !('serial' in navigator) || !window.isSecureContext;
  button('disconnect').disabled = !connected;
  button('stop').disabled = !connected;
  document.querySelectorAll<HTMLButtonElement>('[data-input]').forEach(button => button.disabled = !ready || busy);
  document.querySelectorAll<HTMLButtonElement>('[data-device]').forEach(button => button.disabled = !connected || busy);
}
// Keep diagnostics local and bounded even during long sessions.
const logLines: string[] = [];
const client = new EspCon2({
  onLine(line) {
    if (logLines.push(line) > 160) logLines.shift();
    $('log').textContent = logLines.join('\n') + '\n';
    const status = parseStatus(line);
    if (!status) return;
    if (!status.streaming) { readyAt = 0; ready = false; }
    else { if (!readyAt) readyAt = Date.now() + 2000; ready = Date.now() >= readyAt; }
    $('status').textContent = ready ? 'Ready for input' : status.streaming ? 'Finishing initialization…' : 'Waiting for Switch 2';
    $('detail').textContent = status.name || 'ESP32-S3 board connected';
    render();
  },
  onClose() {
    connected = ready = false; readyAt = 0; clearInterval(poll);
    $('status').textContent = 'Disconnected'; render();
  },
});
async function act(fn: () => Promise<unknown>) {
  if (busy) return;
  busy = true; render();
  try { await fn(); }
  catch (error) { $('notice').textContent = (error instanceof Error ? error.message : String(error)); }
  finally { busy = false; render(); }
}
for (const name of BUTTONS) {
  const button = document.createElement('button'); button.textContent = labels[name] || name.toUpperCase();
  button.dataset.input = ''; button.addEventListener('click', () => act(() => client.input([name], [0,0,0,0], Number(field('duration').value))));
  $('buttons').append(button);
}
for (const axis of axes) {
  const label = document.createElement('label'); label.textContent = axis.toUpperCase();
  const slider = document.createElement('input'); slider.type = 'range'; slider.min = '-1'; slider.max = '1'; slider.step = '.05'; slider.value = '0'; slider.id = axis;
  const value = document.createElement('output'); value.textContent = '0.00';
  slider.addEventListener('input', () => value.textContent = Number(slider.value).toFixed(2));
  label.append(slider, value); $('axes').append(label);
}
$('connect').addEventListener('click', () => act(async () => {
  // requestPort must run directly from the user's click, before unrelated asynchronous work.
  const port = await serialAccess.requestPort();
  await client.connect(port); connected = true; render();
  poll = setInterval(() => {
    if (!busy && !client.busy) client.command('STATUS').catch(error => $('notice').textContent = (error instanceof Error ? error.message : String(error)));
  }, 1000);
  $('notice').textContent = 'Connected locally. Open Change Grip/Order on Switch 2 if needed.';
}));
$('disconnect').addEventListener('click', async () => { await client.stop().catch(() => {}); await client.close(); });
$('stop').addEventListener('click', () => client.stop().catch(error => $('notice').textContent = (error instanceof Error ? error.message : String(error))));
$('pair-grip').addEventListener('click', () => act(() => client.input(['l','r'], [0,0,0,0], 2000)));
$('sticks').addEventListener('click', () => act(() => client.input([], axes.map(axis => Number(field(axis).value)), Number(field('duration').value))));
$('center').addEventListener('click', () => axes.forEach(axis => { field(axis).value = '0'; $(axis).dispatchEvent(new Event('input')); }));
for (const mode of ['joycon','pro']) $(mode).addEventListener('click', () => act(async () => {
  await client.stop(); await client.command('MODE ' + mode); await client.close();
  $('notice').textContent = 'Mode saved. ESP32-S3 board is rebooting; click Connect ESP32-S3 board again.';
}));
$('wake').addEventListener('click', () => act(() => client.command('WAKE')));
$('pair').addEventListener('click', () => {
  if (window.confirm('Forget the active controller mode’s saved console pairing?')) act(() => client.command('PAIR'));
});
// Best-effort release on focus loss; the firmware's 500 ms lease also covers tab termination.
document.addEventListener('visibilitychange', () => { if (document.hidden) client.stop().catch(() => {}); });
window.addEventListener('blur', () => client.stop().catch(() => {}));
window.addEventListener('keydown', event => { if (event.key === 'Escape') client.stop().catch(() => {}); });
window.addEventListener('pagehide', () => { client.stop().catch(() => {}); });
if (!('serial' in navigator) || !window.isSecureContext) $('notice').textContent = 'Web Serial is unavailable here. Open this page on localhost or HTTPS in a browser with Web Serial support, such as desktop Chrome.';
render();
