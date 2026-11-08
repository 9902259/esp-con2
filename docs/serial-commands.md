# Serial command reference

Native USB Serial/JTAG, nominal 115200 baud, 8 data bits, no parity, one stop bit,
no flow control. Commands are ASCII terminated by LF (`\n`); CR is ignored.
Suppress DTR/RTS when opening where supported. Opening the port can still restart
the board. Only one process/browser may own it.

| Command | Effect | Reply |
| --- | --- | --- |
| `STATUS` | Query active controller mode and BLE state | `@STATUS …` |
| `STATE <mask> <lx> <ly> <rx> <ry>` | Replace all input for a 500 ms lease | `@OK` |
| `RELEASE` | Release all buttons and center sticks | `@OK` |
| `WAKE` | Advertise wake/reconnect using a saved bond | `@OK` or `@ERR …` |
| `PAIR` | Forget active mode pairing records | `@OK` or `@ERR …` |
| `MODE joycon` | Save Joy-Con L+R mode and reboot | `@OK` before reboot |
| `MODE pro` | Save Pro Controller 2 mode and reboot | `@OK` before reboot |

`MODE` requires unified firmware. `PAIR` does not clear the Switch's own controller
list. Reopen Change Grip/Order and reboot/reconnect if fresh pairing does not begin.

## State encoding

`mask` is hexadecimal without `0x`. Bits 0–20, in order:

```text
0 a       1 b       2 x       3 y       4 l       5 r       6 zl
7 zr      8 minus   9 plus   10 lstick 11 rstick 12 up     13 down
14 left  15 right  16 home   17 capture 18 gl    19 gr     20 c
```

Examples: A = `STATE 1 0 0 0 0`; L+R = `STATE 30 0 0 0 0`.
Axes are finite decimal numbers from −1 to 1; zero centers an axis. Unknown button
bits, trailing fields, or out-of-range axes are rejected. `STATE` requires streaming.
In Joy-Con mode GL/GR alias SL/SR on both halves together, not independent rails.

Renew held state about every 100 ms. Send `RELEASE` after the requested duration
and on errors/cancellation. If commands stop, the firmware neutralizes the last
state after 500 ms. Host acknowledgements do not prove console-visible effects.

## Responses and readiness

```text
@READY esp-con2
@STATUS device=esp-con2 protocol=1 paired=1 connected=1 streaming=1 advertising=0 name=Joy-Con 2 (L+R)
@OK
@ERR controller is not streaming
```

The board-neutral identifier is `esp-con2`. Update older firmware before using
the current hosts.
Ignore ordinary boot/debug lines. A client must match `@STATUS` only to `STATUS`
and `@OK` only to other commands; queued status must not acknowledge an input or
mode change. `@ERR` indicates a failed request. Never send overlapping requests.

Status may include `left_tx`, `right_tx`, ages, and an extra `@SIDES` line. Inactive
Joy-Con fields are zero in Pro mode. Connection/streaming flags indicate BLE
state, not a selected player or working buttons. Wait an additional two seconds
after streaming begins, then verify selection on Switch 2. Reconnect after MODE.
