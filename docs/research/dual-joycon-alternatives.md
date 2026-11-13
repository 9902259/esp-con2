# One ESP32-S3, two Joy-Con 2 identities

Research and hardware experiment checked 2026-11-08.

## Breakthrough: controller duplicate-peer check

Latest console verification: both halves appeared active in Controllers, and the
button test visibly registered all 16 tested inputs (A/B/X/Y, L/R/ZL/ZR,
minus/plus, both stick clicks, and four D-pad directions). Each was held 100 ms.
A was initially missed immediately after both streams became active; a retry
after a two-second initialization wait appeared. Analog sticks and motion remain
unverified. This supersedes earlier unconfirmed pairing and button results below.

Latest serial-identity experiment: both halves inherited an identical factory
serial. The generator now changes its final digit at 0x1300f to '1' for left and
'2' for right, preserving the existing serial format. This eliminates a concrete
duplicate identity; console-side deduplication by serial remains only a hypothesis.
Build/flash passed, accepted L/R reports were traced on separate handles, and both
controller completion counters advanced. Console outcome remains unconfirmed.
Log: `build/logs/dual-serial-live.log`. A text report of zero/one/two visible Joy-Con
icons is requested before further pairing changes.

Current limitation: the user repeatedly reports no visible connected pair. The
earlier isolated paired-grip confirmation did not reproduce reliably. Packet
tracing now confirms `b2=0x10` for L on connection handle 1 and R on handle 3,
followed by zero-button release packets. Both HCI completion counters advance.
This proves more than encrypted/subscribed flags but still does not prove
console application-level acceptance. A screenshot of the current Change
Grip/Order state is the next diagnostic input. Log:
`build/logs/dual-packet-live.log`.

Latest identity fix: the shared GATT table exposed right-side UUIDs to the left
connection. The generator now patches the pinned GATT declaration reader with a
weak optional hook. The dual firmware maps four UUIDs to their left equivalents
only on the left connection. Runtime trace confirmed `left_uuid_remaps=4`, both
encrypted links, and advancing handoff counts after the user reopened pairing.
A two-second L+R chord was sent. This remains a console-visible validation task.
The dual offset is now 0x60 with fresh `dual3left`/`dual3right` namespaces. Log:
`build/logs/dual-gatt-live.log`.

Latest follow-up: the user reported no connection on the console and requested
fresh pairing. Both emulator bonds were cleared and the board restarted. At the
original report rate, one half's handoffs again fell near 1 Hz. The current build
uses `continuous_stream_divisor=4` on both halves; with 15 ms connection intervals,
the observed counters advanced together at approximately 17 Hz and stayed recent
through the diagnostic window. A two-second L+R chord was sent. Console-side
recognition at this reduced rate remains to be confirmed. Log:
`build/logs/dual-throttle-live.log`. This supersedes the earlier no-rate-change note.

Console confirmation: after the two-second L+R diagnostic, the user reported
"it now works as a pair". This establishes visible paired-grip recognition on
Switch 2. Dual-profile individual buttons and sticks remain untested. During the
same capture, left host handoff counts advanced while right stayed at 107; this
telemetry discrepancy remains unresolved and does not invalidate the user's
observed pairing. No proposed report-rate reduction was applied. Capture:
`build/logs/dual-input-diagnostic.log`.

The controller dispatch table `r_ip_funcs_ro` has a relocation at offset 0x4d8
to `r_llm_is_dev_connected`. A linker wrapper was verified in the final ELF at
that slot. Preserving the original return value yielded 75 calls/74 matches and
one stream. Returning zero while retaining original-result counters allowed a
second connection from the same Switch peer. Both identities completed encryption
and both streams remained active for 60 seconds (60 status checks).

Working generator: `ESP_CON2_DUAL_PUBLIC=1`, without the hardware-filter flag.
The experimental dual build includes the linker wrapper. Current connection
sequence is left first, right second. Logs:
`build/logs/dual-peer-trace-live.log` and `build/logs/dual-peer-bypass-live.log`.
This supersedes the unsuccessful conclusions below for the previous prototypes.
After reopening USB, one reconnect attempt timed out after 25 seconds. Retrying
with the diagnostic monitor reconnected and encrypted both halves and passed a
further 10-second dual-stream check. Reconnection is therefore demonstrated but
intermittent. No L+R input was sent in the timed-out attempt. Retry log:
`build/logs/dual-peer-reconnect-live.log`.
Motion, visible grip selection, and full controller input behavior remain separate
validation tasks. The working dual firmware is retained on the ESP32-S3 board.

## Sequential public-address experiment result

Hardware-filter experiment: the pinned binary's `btdm_linkbl_filter_init(0)`
clears the upper 16 bits of the register at 0x60031304. An opt-in generator flag,
`ESP_CON2_DUAL_NO_LINK_FILTER=1` together with `ESP_CON2_DUAL_PUBLIC=1`, calls
this before each identity selection. Build and flash succeeded; logs confirmed
execution for both halves. Left connected and encrypted, while right remained
unconnected throughout the 40-second test. This toggle is insufficient. Register
semantics and persistence are not established by the function name/disassembly;
this result does not rule out other controller-level same-peer filtering.
Logs: `build/logs/dual-no-filter-live.log`.

The binary also exports `r_llm_is_dev_connected`, which iterates connection
records and compares peer address/type. Its existence alone does not establish
that it rejects this incoming second connection. Before further bypasses, trace
the caller or capture the over-air connection request. CoreBluetooth advertisement
scanning does not capture raw connection requests, so the Mac scan cannot resolve
whether the console sends one that the S3 rejects.

Reverse-order test: starting left first connected and encrypted successfully;
left streamed while right advertised but did not connect during the 35-second
window. The earlier right-first run produced the inverse result. Both identities
can therefore stream as the first connection. The failure follows connection
order rather than left/right identity. Logs: `build/logs/dual-left-first-live.log`.

Source inspection found no explicit duplicate-peer rejection in NimBLE's incoming
peripheral connection-complete path. This does not rule out controller-level or
Switch-side rejection. NimBLE's LTK retrieval indexes the security store by peer
address; both emulated halves share that peer but have distinct keys. This is a
separate issue to fix before encrypted dual sessions can be considered robust,
although it does not explain the currently absent second connection event.

Follow-up independent Mac scan: `debug/scan_joycon.py` (optional dependency
`bleak==3.1.0`) observed both Nintendo payloads: PID suffix 0x66/right and
0x67/left, names matching their profiles, and two distinct CoreBluetooth UUIDs.
The left advertisement remained visible after right input streaming started.
The scan is recorded in `build/logs/dual-public-scan.jsonl`. macOS exposes UUIDs rather
than raw address bytes/type, so the exact on-air public address remains unverified.

A read-only Mac connection to the left UUID succeeded and discovered two GATT
services. Serial captured this second connection at uptime 34.226 s after the
right link had been streaming; no intervening right disconnect was logged.
This demonstrates second-link acceptance from a different central, but does not
validate two concurrent Nintendo sessions to the same Switch. Investigate
same-central connection handling and Switch selection/pairing behavior next.

The opt-in `ESP_CON2_DUAL_PUBLIC=1` generator variant was built and flashed.
The expected-byte RAM guard passed for both selections. The right half connected
and streamed, then continued streaming after the left identity was selected and
its advertisement started. The left half did not connect during the 45-second
test with the console's pairing screen open. Both-stream verification failed.

This establishes that the attempted RAM change did not immediately break the first
link. It does not establish that the left address was actually transmitted over
the air: independent BLE observation is needed before interpreting this as a
Switch rejection of two public identities. Logs are preserved locally in
`build/logs/dual-public-live.log`. The tested single-left firmware is restored afterwards.

## What the previous tests establish

The public-address half streamed; the static-random half did not connect. Swapping
roles and pre-pairing the second address as public did not fix this. This does not
prove that one radio cannot serve both halves, or that the Switch rejects every
random-address peripheral. A standalone random-address control test and independent
observation of the advertisements are still missing.

## Best new experiment: sequential public-address setup

Connect the first half, stop advertising, change the controller's public identity
without resetting its active connection, then advertise and connect the other half.
The intended result is two concurrent links after sequential connection setup.
Disconnecting and alternating between halves would not meet the requirement.

Concrete evidence from the pinned ESP-IDF S3 `libbtdm_app.a`:

- `hci_rd_bd_addr_cmd_handler` copies six bytes from `(*p_llm_env) + 12` into
  its HCI response. This identifies the controller's public-address storage for
  this exact binary, not a supported API or a portable offset.
- The existing dual build resolves `p_llm_env` and `r_lld_adv_start_hook`.
- `r_lld_adv_start`, `r_lld_adv_start_init_evt_param`, and
  `r_lld_adv_start_set_cs` exist in the archive. These are investigation points,
  not yet validated interception APIs.
- NimBLE's `ble_hs_id_set_pub()` only copies the host's cached address. Calling
  it alone does not change the address transmitted by the controller.

Remaining work before a hardware claim: trace how advertising consumes the public
address; synchronize a change with the controller task; validate existing bytes
against HCI Read BD_ADDR before any version-specific RAM write; keep the host's
identity bookkeeping consistent. Route sessions by advertising instance or saved
connection handles, since both addresses would now be public. The current
`our_ota_addr.type` dispatcher would incorrectly route both to the right half.

Success requires two distinct connection handles, independent completed Nintendo
pairing/encryption, both streams running together for at least 60 seconds, and
visible left/right inputs on Switch 2. Test reconnection afterwards. HCI address
readback or a successful build alone is insufficient.

## Other avenues

1. **Control-test the random identity alone.** Same legacy advertising payload,
   only one active advertiser and no existing connection. Observe advertisements
   independently if possible. If that works, investigate scheduling and simultaneous
   same-peer connection handling before patching controller internals.
2. **Per-advertiser controller patch.** If changing the global identity cannot
   preserve an established link, investigate supplying a public address separately
   to each advertising context. Correct scan responses and incoming connection
   address matching are required too; clearing only an advertising header bit is
   insufficient. This is more involved than the sequential experiment.
3. **Pro Controller profile.** Already tested for ordinary combined controls, but
   does not establish two Joy-Con identities or their per-half features.

Changing from NimBLE to another host alone does not provide two public addresses.
The pinned `NimBLEExtAdvertisement::setAddress()` explicitly chooses random address
type, and `setInstanceData()` uses `ble_gap_ext_adv_set_addr()` for that address.
Two GATT services under one identity also do not establish two Joy-Cons.

## Sources and reproducibility

- Local pinned sources: `firmware/scripts/dependencies.sh`,
  `.deps/espp/components/esp-nimble-cpp/src/NimBLEExtAdvertising.cpp`, and
  `.deps/esp-idf/components/bt/host/nimble/nimble/nimble/host/src/ble_hs_id.c`.
- Controller artifact:
  `.deps/esp-idf/components/bt/controller/lib_esp32c3_family/esp32s3/libbtdm_app.a`;
  inspect with the installed Xtensa `nm -A` and `objdump -dr`.
- [Espressif address types](https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/get-started/case-study/BLE-examples/general-steps.html).
- [espp Switch 2 support](https://esp-cpp.github.io/espp/ble/switch2_pro.html)
  documents the S3's supported 5 ms connection interval; this does not validate two
  simultaneous Switch links.
- [XD2Joy](https://github.com/desktopsetup/XD2Joy) uses two nRF52840 chips. Its
  single-peripheral input forwarding feature is not proof of one-radio L+R emulation.

Conclusion: a controller-level public-address experiment is a concrete remaining
route. One-S3 concurrent L+R remains unverified, not ruled out.
