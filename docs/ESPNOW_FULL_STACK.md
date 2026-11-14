# Full ESP-NOW stack

The X1000 transport implements standard ESP-NOW datagrams on the Japanese
NW-X1050/NW-X1060's SD8686 platform. It is independent of the original player;
Wireless Remote combines this transport with the separate player service.
The SDK is experimental and is not an ESP-IDF ABI replacement.

For application code, use [ESP-NOW services](sdk/ESPNOW.md). For system mode,
shared ownership and transition rules, use [wireless lifecycle](sdk/WIRELESS.md).
[Status](STATUS.md) distinguishes current source, published packages and
physical acceptance. The current firmware's remote startup, sleep and USB
regressions remain open; earlier working exchanges do not qualify that composition.

## Implementation map

All device implementations are C/C++ with necessary ARM assembly. Python is
PC tooling only. Shared transport code lives in `runtime/platform/espnow/`.

| Files | Responsibility |
| --- | --- |
| `xnow_wire*`, `xnow_peer*`, `xnow_endpoint*` | Standard frames, bounded peers and datagram operations |
| `radio_packet*`, `radio_full_rx*`, `radio_full_tx*`, `radio_tx_completion*` | Radio-side packet ownership, retained RX and correlated completion |
| `xnow_full*`, `xnow_full_guard*`, `xnow_sd8686_full*` | Native transport, bounded radio-memory access and original Linux driver ABI |
| `xnow_ccmp*`, `xnow_security*`, `xnow_endpoint_security*` | Separate CCMP primitives, authenticated endpoint and replay handling |
| `xnow_pn*`, `xnow_pn_file*`, `xnow_keyring*` | Counter reservation, user-storage journals and volatile local key vault |
| `xnow_full_control*`, `xnow_shared_session*` | Explicit controller lifecycle and attachment to an already admitted shared radio |
| `xnow_owner_commands*`, `xnow_owner_stream*`, `xnow_owner_runtime*` | Bounded owner IPC, command dispatch, stop and restoration notification |
| `xnow_managed_process*`, `xnow_launcher_bridge*`, `xnow_owner_gate*` | Explicit managed foreground handoff and cooperative owner exclusion |
| `standard-peer/` | ESP-IDF bench using original Espressif peer/send/receive APIs |
| `xnow_link*`, `xnow_link_counter*`, `xnow_owner_link*` | Opt-in authenticated key epochs, scoped counters and Root endpoint adaptation |

Radio image construction and profile generation are PC-side operations. Neither
an SDK import nor a successful source build loads an image, powers the chip,
grants a lease or modifies the system partition.

The full controller returns STOPPING after shared endpoint drain while retaining
its manager lease. The composing owner closes receive membership and restores
owed sleep state before the next controller step may RELEASE. This call boundary
is tested with the actual Root wrapper and controller; a delay is not retirement.

## Wire and endpoint contract

The [Espressif frame specification](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/network/esp_now.html)
is the interoperability target. The codec handles complete vendor Action bodies
and 24-byte MAC headers, without FCS. It adds no XNOW/chat envelope to a standard
datagram. Binary data and zero-length wire bodies are supported by the codec.
Recorded standard-peer API tests reject zero-length send and do not qualify
empty application delivery.

| Profile | Codec payload limit | Meaning |
| --- | --- | --- |
| Standard v1 | 250 bytes | One vendor element |
| Standard v2 | 1,470 bytes | Validated continuation chain with canonical 250-byte encoding chunks |
| Legacy mailbox | 16 opaque data bytes in a fixed 32-byte XNOW frame | Separate compatibility transport; not the standard endpoint's limit |

The decoder validates version, OUI/type, reserved fields, continuation, lengths
and total capacity before publishing output. It does not truncate a malformed
frame into a successful datagram. Local transmitter identity and channel come
from the admitted adapter; RSSI or channel data is never fabricated.

Peer operations validate destination, version, channel and encryption settings.
One serialized owner controls an endpoint. Request acceptance, original MAC
completion and a peer application response are distinct results. An uncertain
side effect must not be repeated automatically.

RX metadata has BROADCAST and AUTHENTICATED flags. AUTHENTICATED is set only
after MIC verification, replay checking and RX-state commit. A plaintext
broadcast from an encrypted-unicast peer remains receivable and unauthenticated;
that peer's plaintext unicast remains rejected. Membership does not authenticate
a broadcast's claimed source.

XNR1 IPC retains its 32-byte header: RX flags occupy offset 24, and offset 28
remains reserved. Rebuild native consumers after structure/ABI changes. Old
zero flags are not authentication evidence.

## Radio ownership and completion

The original SD8686 packet allocator owns packet storage. Radio queues retain
RX packets until acknowledged and submitted TX packets until original completion
or the verified pre-MAC rejection path. Stop closes RX admission, drains retained
packets and waits for submitted TX. A timeout cannot free an in-flight packet or
manufacture successful MAC completion.

The private JP1.11 Linux adapter uses `eth0`, command 0x86 through ioctl 0x8be4,
the original 32-bit iwreq layout and validated response envelopes. Its generated
profile checks immutable code/layout and the current allocated packet interval.
Startup-only reclaimed scatter metadata is not treated as permanent runtime
identity. Writes are limited to the admitted control/packet fields; arbitrary
radio memory access is not a public SDK capability.

An admitted shared session borrows the existing radio and follows its actual
channel. A channel change starts drain instead of retuning native Wi-Fi. Closing
that consumer does not authorize native power-off. An exclusive owner uses the
separate qualified load/restore path. Both require actual platform identity and
lifecycle evidence; a boolean fixture or cooperative socket alone is insufficient.

Application switching, sleep and permanent USB/exit are separate transitions.
Application handoff preserves a valid native Wi-Fi connection after custom
consumers drain. Sleep and permanent shutdown require their respective retirement
proofs. See [native lifecycle](reference/STOCK_LIFECYCLE.md) and
[native wireless bindings](reference/STOCK_WIRELESS.md).

## Security and persistence

The generic CCMP management profile and the measured Espressif S3/IDF5.5.1
profile are explicit alternatives. The latter uses nonce0, legacy AAD and Key ID3.
Use `xnow_endpoint_security_attach_espnow` for that profile. API peer LMKs are
mapped to the effective wire key with `xnow_ccmp_espnow_wire_key(pmk, api_lmk,
wire_key)`; journal scopes must identify the effective key. MIC verification is
mandatory. Do not select a profile from a Protected bit or disable authentication
to accept a packet.

For reusable keys, TX reservation and RX replay state must survive service/process
restart. Supply verified user-storage ownership, load, reserve and commit
callbacks. Provision missing records only for a proven fresh key. Never reset
counters under an existing key to recover from an error. The opt-in
[link-key protocol](reference/ESPNOW_LINK_KEYS.md) establishes a new authenticated
key epoch and a separately scoped volatile provider; it is not a static-key
RAM fallback. Its Root/Core2 composition still needs physical acceptance.

The PN-file adapter updates two fixed 80-byte V2 slots without rename/truncation.
Both must remain valid once V2 is observed. It uses the highest committed/pending
value and skips uncertain reservations instead of reusing them. Missing/corrupt
V2 data fails closed. Legacy readers must not downgrade or reset those records.
Malicious snapshot rollback/removal is not prevented; key rotation is required
after restoring such data. This is not power-loss FAT qualification.

Keys, journals and application data belong on independently verified exposed
user storage. There is no system-path fallback. The local keyring is a volatile
wrapped-LMK vault, not protected disk storage: saving its PMK alongside wrapped
keys provides no meaningful protection. Active endpoint memory contains usable
key material and must be erased at the appropriate retirement boundary.

Rejected plaintext formats are normalized into the security format-error domain.
Real driver/storage failures retain their IO/uncertainty meaning and request
cleanup; a malformed frame must not masquerade as a driver failure.

## Managed owner lifetime

The explicit owner runtime requires a constructed controller, cooperative gate,
nonblocking command stream and reviewed inherited restoration capability before
RF startup. Missing authority refuses activation. The 80-byte `launch.contract`
binds opt-in to the application executable hash. These components do not provide
a general installed background-task manager to every SDK application.

The stream verifies FIFO mode/device/inode, bounds staged requests/replies and
supports partial reads/writes. Pending output prevents another command from
executing. EOF/HUP, malformed framing, descriptor replacement or broken output
requests stop and erases staged key-bearing data. Local detach, EOF and a STOP
acknowledgement are not successful restoration receipts.

The runtime handles stop/revocation before admitting more commands. Its prepare
callback must attach the selected security/counter provider before encrypted
work. A negotiated-key transport holds app dispatch until the key and encrypted
peer confirmation are established; sideband TX has separate completion ownership.
After data-channel loss it continues controller drain and restoration.
Only confirmed controller completion permits data cleanup: close user-volume
references, move cwd off that mount, close stream/gate, write the matching
restoration record and close its writer. Cleanup/notification uncertainty retains
ownership; it is not permission to return or kill the owner after a timer.

The managed launcher and UI copies must close unintended owner-only descriptors.
Signal/SIGPIPE handling is explicit. Calls to original manager/driver methods
can block and must stay off the UI rendering/input callback.

## Offline verification

Use the prepared Linux/WSL environment and matching local original inputs.
Reports describe their recorded source hashes and modeled boundaries; an old
pass is not evidence for edited source. Source SDK archive checks are separate
from radio-image and firmware composition checks.

| Check | Scope |
| --- | --- |
| `test_xnow_wire.py` | Fixed vectors, binary/empty v1/v2 boundaries and malformed chains |
| `test_espnow_full_radio.py` | Parsed radio image, hook/pool preservation and invalid inputs |
| `test_xnow_secure_chain.py` | Native security/journal/backend chain using the explicitly selected parsed radio candidate |
| `test_full_owner_ipc.py` | Actual stream/commands/controller drain with modeled original driver actions |
| `test_full_owner_runtime.py` | Restoration-before-cleanup/notification and failure retention |
| `test_full_owner_process.py` | Launcher/UI/owner processes and forced UI termination; modeled platform effects |
| `test_full_owner_secure.py` | Persistent counters, crypto and replay through complete owner lifecycles |
| `test_shared_owner_retirement.py` | Actual Root pre-release cleanup and controller, with native effects modeled |
| `test_xnow_link.py`, `test_xnow_link_counter.py`, `test_core2_owner_bus.py` | Fresh key epochs, replay scope and Root/Core2 owner-IPC integration |
| `test_sdk_espnow.py`, `test_sdk_espnow_full.py`, `test_sdk_espnow_owner.py` | Public C/C++ clients and original-libc ARM source integration |

Host sanitizers, Unicorn, original-libc ARM execution and synthetic radio queues
cover different seams. None independently qualifies original RF scheduling,
installation, audio, power, sleep/wake or physical USB ownership.

## Physical acceptance boundary

Recorded legacy exchanges and selected S3 encrypted sessions demonstrate that
this hardware can exchange ESP-NOW frames. Their exact scope is retained in
[native wireless reference](reference/STOCK_WIRELESS.md#recorded-physical-exchange-scope)
and [original transport validation](../runtime/platform/espnow/VALIDATION.md).
They do not qualify every later shared-radio or Settings-managed composition.

A complete delivery still requires the final image/profile and unchanged peer
APIs to pass both directions, required payload lengths/versions, encrypted peer
admission, wrong-key/replay refusal, failed/successful MAC completion, repeated
stop/restart and native restoration. Multi-peer load, ESP restart counter policy,
screen-off/sleep, Wi-Fi coexistence and USB handoff need separate acceptance.
The [current status table](STATUS.md) records the outstanding regressions.

The standard-peer bench uses RAM-only keys/peers with Wi-Fi NVS disabled. Reboot
requires fresh test keys; it does not establish durable peer-side anti-replay.
A v2-capable peer does not alone prove independent v1 reception. Building that
bench does not authorize flashing a controller or changing the player's radio.
