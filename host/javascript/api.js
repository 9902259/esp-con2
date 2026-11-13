"use strict";
// Public entry point for the esp-con2 JavaScript host API.
//   client.js   EspCon2: serial session, request queue, held input and release
//   protocol.js Pure command encoding, STATUS parsing and line splitting
export {EspCon2, EspCon2 as ControllerSerial} from './client.js';
export {BUTTONS, BUTTONS as buttons, INPUT_LIMITS, LineSplitter, SERIAL_OPTIONS, STATUS_PREFIX,
  buttonMask, checkDuration, encodeCommand, parseStatus, stateCommand} from './protocol.js';

/** @typedef {import('./client.js').EspCon2Options} EspCon2Options */
/** @typedef {import('./client.js').SerialPortLike} SerialPortLike */
/** @typedef {import('./protocol.js').Status} Status */
