# Full ESP-NOW implementation requirements

The active objective is a complete, usable ESP-NOW implementation for the
Japanese X1060, interoperating with Espressif devices and exposed through the
user SDK. The older fixed32-byte XNOW chat transport is preserved as a tested
baseline, not the completion criterion. No use-case restriction is imposed.

The protocol reference is Espressif's [ESP-NOW API/frame guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/network/esp_now.html).
Completion requires both v1 and v2 packet interoperability, standard encrypted
unicast behavior, peer/destination selection, independent sending, bounded
queues, public SDK contracts and validated device restoration. Firmware-specific
or hardware-limited capabilities must be identified explicitly, not reported as
implemented through a stub, in-memory model or unrelated application ACK.

## Acceptance matrix

The autonomous test executable is now implemented under runtime/apps/espnow-test.
It detaches from the launching Terminal, records an exclusive bounded user-volume
journal, drives the actual full controller and runs RX capture or ten plaintext
binary v1/v2 TX cases before stock restoration. Its candidate directory is isolated
from legacy chat. Host/original-libc ARM engine tests cover vector bytes, journal
refusal, pending-TX deadline drain and repair retention. A real host launch-group
termination test confirms the detached worker completes and fsyncs its log.
Default/invalid invocations refuse radio activity; help runs under original-libc
ARM. These are implementation/offline results, not qualified image loading,
APF/USB/sleep exclusion, unknown-key RX admission or encrypted interoperability.
See runtime/apps/espnow-test/README.md and work/autonomous-espnow-test reports.

Local chatdev.3 source fixes premature event EOF being treated as owner completion.
The production UI reducer and real client pipe parser now retain repair state for
unexpected/partial/error EOF, while explicit CHAT_FINISHED followed by EOF keeps
its result. The new regression first fails on dev.2 source, then passes host
sanitizers and ARM926/original libc. This does not qualify signal/device-error or
launcher forced-kill handoff by itself; separate integration evidence is below.
Dev.3 now has a local ARM review build, not a deployed/released package; the
identified device app remains dev.2. Report:work/chat-ui-owner-eof/report.json. This is a reproduced code issue,
not proof that it caused the earlier physical Wi-Fi interruption.

The dev.3 candidate adopts the inherited managed-launch capability before RF
startup, explicitly transfers it to the detached owner and drops the UI copy.
Without it, the app refuses RF startup. The worker sends the correlated32-byte
completion record only after legacy control_finished, closing command/event/
lease FDs and leaving user cwd. Pre-radio failures have a separate failure
notification. A single launch permits one owner session; descriptors are not
re-adopted after reuse. Its80-byte launch.contract binds the app hash. Existing
owner real-pipe tests verify success, duplicate-owner startup refusal and exact
cookie+EOF records. ARM compile/CLI/render checks pass. Physical graphical UI,
APF/USB/sleep and network restoration remain unqualified: the
builder reports deployable=false and this candidate must not replace the device
app yet. No driver/image/firmware action was executed by these checks.

The chat client's actual fork/exec and owner path now also passes the host managed
launcher forced-stop test: the UI ignores SIGTERM and is killed by the unchanged
launcher grace path; a6.5-second modeled reconnect delay keeps foreground until
the owner's correlated DONE+EOF (about9.3seconds total). A modeled owner crash
without notification leaves the launcher alive. Only worker pathname, root/user
mount distinction and radio/cnmgr effects are substituted. Missing inherited
capability is explicitly refused before owner fork. See
work/chat-managed-process/report.json. This is not the graphical UI/device/APF
path on a player. The separately built ARM launcher verifies the actual dev.3
candidate, recognizes its managed marker and rejects a wrong app hash; missing
marker is legacy. See work/chat-managed-launcher-dev3-review/chat-check.json.
Device deployment and physical HOME/USB/sleep/network restoration remain pending.

The chat-specific notification helper now executes under host ASan/UBSan and
ARM926/original libc with real pipes and inherited environment adoption. Tests
check CLOEXEC, refusal before controller completion and in repair state, actual
modeled restore retry before cookie+EOF, pre-radio startup-failure notification,
and descriptor replacement refusal without closing the replacement. These use
the actual legacy controller dispatch with modeled platform/cnmgr effects, not
physical RF. Report:work/chat-handoff-arm/report.json. The earlier immutable
work/chat-managed-review-kit snapshot predates this additional report; its
deployable=false restriction remains in force.

| Requirement | Current evidence | Evidence still required |
| --- | --- | --- |
| Arbitrary payloads without XNOW header | Wire codec, compiled full radio/native ABI and private owner IPC cover binary/zero-length v1/v2 and250/1470 boundaries; separate standard ESP-IDF peer builds | Unchanged Espressif send/receive API interoperability over air, including an actual v1 input peer |
| Independent TX | Physical autonomous X1060 run:10 MAC completions, eight nonempty cases matched Cardputer bytes through1470; restored authenticated Terminal | Empty delivery, reverse/plain RX breadth and broader lifecycle/load qualification |
| Peer management | Native table and endpoint implement CRUD/query/enumerate, all-peer dispatch, channel/version/length validation, CCMP attachment and erasure; private owner command tests pass | Physical multi-peer behavior and usable device-owner integration/qualification |
| Security | Physical33-byte S3 v2 frame authenticated:nonce0/legacy AAD/ID3/effective AES(PMK, API LMK); current explicit native primitives recreate it under host/ARM | Encrypted endpoint integrated: eight byte-exact TX payloads through1470, same-key process restart with retained Cardputer peer and durable PN continuation, and twelve authenticated1470-byte RX packets with exact first-payload SHA-256. Wrong-key/replay persistence across broader actual device lifecycles remains open |
| RX/TX queues | Two-slot allocator-backed RX, full native ABI, serial TX completion and drain have instruction/native tests; stock task dispatch now reaches the full RX hook through actual ring-copy | Real scheduling/load tests and physical completion reporting; upstream hardware admission |
| Lifecycle | Legacy chat physically tested; full runtime/managed owner passes host processes plus ARM/old-libc, IPC disconnect, restore-before-notification and journal cleanup tests | Device/platform qualification of new ABI, forced-stop/manager deadlines, sleep/wake, USB handoff and AP coexistence |
| User SDK | SDKalpha.6 includes optional managed-owner services and fixes plaintext wire/IO error collision; public owner ARM and C++ header consumers pass; standalone XNOW archive is dev.11 | Physical/platform consumer qualification and standard encrypted interoperability |

The owner components described below were introduced as private review code and
are now explicitly selectable through SDK0.2.0-alpha.6 espnow-owner. They remain
experimental: source export does not install the launcher review, supply missing
original platform ownership proof or qualify hardware. The standalone XNOWdev.11
archive intentionally excludes the new owner objects. The installed legacy chat
and root firmware identity are unchanged by this source-SDK update. See
[SDK owner contracts](sdk/ESPNOW.md#experimental-managed-owner).

New physical profile evidence supersedes the earlier unresolved nonce discussion
below. See the RF guide's latest full-radio physical result. The generic codec
still uses management nonce10; explicit xnow_ccmp_espnow_* source now selects
nonce0/legacy AAD without removing MIC verification. One physical v2/33-byte
capture passes native host/ARM authentication and exact recreation. Existing
encrypted endpoints still use the generic path and must be integrated explicitly.

Historical crypto gap: the original codec used generic management nonce prefix10.
There is also a separately reproduced Key-ID barrier: the pinned S3 initial
context writes ID3 and its allocator packs that field into ExtIV, whereas the
native endpoint uses ID0. Exact ID checking rejects a synthetic ID3 frame before
MIC/replay processing. Do not treat solving nonce/AAD alone as sufficient or
silently disable key selection checks. See the RF guide's static Key-ID evidence;
actual RF and warm-context behavior remain to be qualified.
Pinned ESP-IDF5.5.1 ccmp_decrypt has an ESPRESSIF_USE/espnow_pkt branch selecting
prefix00 and software tag length0. Executing the unmodified upstream C through
parameter-recording AES stubs confirms this distinction on host and ARM; native
ciphertext authenticates with prefix10, not00. This is not yet the actual S3 TX
wire profile. Do not disable native MIC verification or assume the software tag0
setting means no RF MIC. Trace hardware/call-site behavior or capture known-LMK
frames before choosing compatible nonce/AAD parameters. Existing generic CCMP
and self-generated encrypted journal tests cannot prove Espressif interoperability.
See work/espressif-ccmp-boundary/report.json and the RF guide.

The pinned S3 vendor TX review now identifies PN/ExtIV insertion, Protected and
key/cipher metadata preparation, post_hmac event5 and lower PP/MAC references.
The descriptor declares8-byte header/trailer and the PP security table adds12
bytes for cipher3, consistent with trailer8 plus FCS4. An official Espressif
PMF/coexistence commit documents backward-compatible hardware ESP-NOW processing.
The event5 callback registration is now statically traced from output_init through
ic_register_net80211_tx_cb and pp_register_net80211_tx_cb to the global callback;
the target is ieee80211_output_process, with a conditional pending_eb call.
This makes the offload boundary the priority: lower-MAC
nonce/AAD/MIC consumption and real known-LMK frames remain unproven. No MIC skip
or speculative default change is introduced. See work/espressif-tx-path/report.json
and sources/espressif-espnow-crypto-sources.json.

The PC known-key capture classifier now requires both MIC8 authentication and
complete v1/v2 body validation before reporting a candidate profile or exporting
payload. Synthetic boundary/negative tests pass, including1470-byte v2. See the
RF guide's authenticated capture section. Actual Espressif encrypted frames are
still required; no native crypto default or installed radio image was changed.

## New wire codec

Current source also appends flags to xnow_full_received: BROADCAST1 and
AUTHENTICATED2. The latter is set only after successful CCMP open, including
MIC/replay checks and RX-state commit. It is never inferred from Protected or
peer membership. Plaintext paths report broadcast status from the validated
radio metadata. Their encrypted-peer broadcast behavior is consistent with the
attached-security path. This changes the native source ABI: rebuild all consumers;
do not mix old compiled consumers with the new structure. Frozen SDKalpha.6
packages are unchanged. XNR1 keeps its32-byte header and payload offset, using
previously reserved offset24 for flags:u32LE; offsets28..31 remain zero. Readers
must not interpret old zero flags as authenticated. Stream output rejects unknown
bits and the impossible broadcast+authenticated combination. Host and original-
libc ARM endpoint/security/partial-pipe tests cover these states. This metadata
does not qualify the unresolved encrypted RF profile or invent RSSI/channel data.

Current source fixes an RX compatibility defect: encrypted peer membership used
to reject that source's plaintext broadcasts as well as plaintext unicast.
ESP-NOW multicast encryption is unsupported, so broadcast is now passed to the
ordinary strict plaintext decoder, while encrypted-peer plaintext unicast remains
rejected. A spoofable plaintext broadcast is not authenticated by peer membership.
The regression first fails on the old source, then passes host ASan/UBSan and
ARM926/original libc with251-byte v2 broadcast, unchanged PN commits and preserved
unicast rejection. Existing replay/MIC/capacity/erasure cases also pass. This is
current-source evidence, not a replacement of the frozen SDKalpha.6 archive or
new physical radio acceptance. Report:work/espnow-secure-endpoint-tests/report.json.

runtime/platform/espnow/xnow_wire.h/.c encode/decode standard plaintext vendor
Action bodies and complete24-byte MAC headers without FCS. They do not prepend
XNOW, allocate memory, use an OS, generate randomness or access a radio.
Caller-provided random values are not a substitute for a proper random source.
Protected frames are identified for the future CCMP layer, not parsed as plain
text. Native information structures are metadata, not serialized wire structs.

v2 encoding emits multiple vendor elements with the continuation flag and
canonical250-byte chunks. Decoding validates complete element chains, lengths,
OUI/type/version/reserved fields and aggregate bounds before writing output.
It does not silently truncate oversized packets or expose partial output after
a malformed chain. Binary zeros/high-bit bytes are accepted. Zero-length frames
still contain the required vendor element. Source/destination MACs and sequence
control are available separately from application payloads.

tools/test_xnow_wire.py runs a fixed v1 vector, v1/v2 length boundaries, v2
continuation failures, MAC-header cases, no-partial-output checks and20000
fixed-seed mutation/truncation cases under host ASan/UBSan and the original
Sony loader/libc on ARM926 QEMU. Report:work/espnow-wire-tests/report.json.
This does not extend the old radio mailbox's32-byte limit. No new packet size
has been qualified on the physical radio by this codec test.

## Host-command doorbell experiment

The original command0x86 branch at0x88d6 performs action1 word STORE and treats
other actions as word LOAD. The experiment replaces its first10 bytes with a
Thumb literal branch into a separately compiled handler. The original command
prologue, admission logic and response entry0x9a46 remain in the replay.

radio_command_hook.S preserves live r4-r7 and the dispatcher's stack, calls
radio_word_command.c to perform the original operation, then returns through
0x82e8. A doorbell callback runs only after a completed STORE. In the fixture it
increments a counter for one synthetic address/value. Ordinary writes and GETs
retain their original behavior. This demonstrates a host-triggered execution
path that does not wait for a management RX callback.

tools/test_radio_command_hook.py compares original/patched paths for actions0,
1 and2, verifies live registers/SP and original memory effects, and confirms no
RX callback executes. Report:work/espnow-command-hook/report.json. The test
counter and scratch addresses are simulated, not approved physical storage.
The experiment emits an ELF only, not a radio download image. It does not call
the real TX queue or qualify combined payload memory ownership.

## Original packet ownership and independent TX prototype

Further original-code replay executes factory initialization0xc0004b6c, the
0xd458/ARM0x1384 allocator chain, header builder0xda00, submit0xd800 and original
release0x1360/0xc0004694. The large descriptor at0xc0014728 is initialized by
original instructions, not invented to return a convenient buffer address.
IRQ, ROM queue/notification, memzero and an absent peer/key lookup are fixture
boundaries. No completion interrupt, real task scheduling or RF ACK is qualified.

The pool stride is1900, but the returned packet pointer is140 bytes after the
slot base:4 pool-header bytes and136 internal-object bytes. Its remaining
capacity is1760. The factory uses the small pool for its348-byte size class;
requesting a variable data length through that threshold is unsafe. The new
prototype deliberately requests the large1900-byte class. A1520-byte v2 body
plus the32-byte internal frame prefix fits. A1536-byte body is also tested as a
capacity bound only; encryption has not thereby been implemented.

Original submit frees a rejected packet itself. A successful submit retains
the allocation for the queue/consumer; callers must not free it immediately.
The allocation factory also leaves the packet's old chain link intact. The
new single-object allocation clears that link, preventing a later chain release
from freeing an unrelated live neighbor. The regression seeds such a stale link
and verifies the neighbor remains allocated after queue rejection.

radio_full_tx.c/.h add an experimental fixed-width control block, independent
of the old chat mailbox: ALLOCATE, SUBMIT and ABORT. Allocation returns a bounded
packet region; native word commands upload the encoded body at packet+32.
SUBMIT builds an original Action header with an explicit destination, invalidates
host ownership and calls original submit. Duplicate allocation, overlength,
abort and original queue rejection are checked. An unreserved four-block
profile is refused before allocation, and exhaustion returns an error without
modifying ownership. The standalone TX prototype consumes902 bytes
of the reserved block, including its control state, with the current compiler.
There are no permanent1470-byte arrays in that code reservation.

tools/test_radio_packet_ownership.py covers counts4/3 and original packet
lifetimes. tools/test_radio_full_tx.py runs the actual standard-body codec,
compiled radio control code and original8078 host dispatcher. It uploads v1
empty/250-byte and v2 251/1470-byte payloads via original word commands and
executes original frame-header/submit code. No Action RX callback is involved.
Reports:work/espnow-packet-ownership/report.json and
work/espnow-full-tx/report.json. Queue acceptance/consumer completion are modeled;
this is not a physical send or MAC-completion report. The probe ELF is not a
download image and is not linked into the existing deployed radio profile.

## Allocator-backed RX queue

radio_packet.c centralizes the verified large-pool allocation and ownership
checks. radio_full_rx.c adds a two-slot single-producer/single-consumer queue.
It accepts only the original singleton RX-work object, validates its pool and
frame bounds before reading, and copies standard Action bodies into separately
owned allocations. No borrowed work pointer survives the callback. Own-address
unicast and broadcast filtering is retained; unsupported traffic falls back to the original handler. Protected Action
frames now have an explicit ciphertext-only path described below. Full vendor-element-chain validation remains
the native wire codec's responsibility.

Original ring reader0x4b9c copies frame_length-16 bytes. The body at frame+32
has frame_length-48 bytes; both v1 and v2 bodies fit the original1700-byte
work slot. Its context/frame pointers and descriptor come from the original
factory instructions, not an invented fixture buffer.

A full queue or exhausted original packet pool records a drop without replacing
unread data. Host acknowledgement tickets release each consumed allocation;
duplicate/stale/empty acknowledgements and32-bit ticket wrap are checked.
The consumer publishes its freed ring slot before releasing a cached old
packet pointer. An instruction replay switches to the producer in that window
and verifies that a new packet in the reused slot survives the old release.
This is manually scheduled context interleaving, not real RTOS qualification.

The combined RX/TX/control ELF without the optional completion module occupies1670 bytes of the1900-byte reservation
with the current compiler. Payloads are allocated separately from the three
remaining original packet blocks. tools/test_radio_full_rx.py runs the original
work factory and ring copy, both250-byte v1 and1470-byte v2 payloads, queue/pool
exhaustion, unsupported traffic, destination filtering and ownership tests.
Report:work/espnow-full-rx/report.json, bound to current source hashes. ROM IRQ,
copy and DMA producer boundaries remain modeled. No new radio download image
has been created or installed. The previously deployed fixed32-byte bridge is
unchanged. RX admission and in-flight-producer stop now have an experimental handshake, described below; native shutdown integration is still missing.

## Original TX task and completion boundary

Task registration at0x673c passes task5 and entry0x9e21 to0xf928. A dedicated
Thumb function symbol at0x9e20 is necessary for reliable REA decompilation:
the earlier analysis ELF incorrectly merged this entry with the host dispatcher.
The corrected symbolized ELF preserves the original low/high section bytes.

The actual task drains queue3 through0xf86c, attaches its packet to internal
metadata+0x3c, sets metadata+0x40 and calls0x68e8 ->0x12c90. A zero return releases
the packet through0xd51c; a nonzero return updates a counter. This proves a
consumer/ownership path, not successful RF transmission. Function0x12c90 can
select0xe840,0xe6f8 or state-dependent pending queues through0x7074. REA also shows0xe840 and0xe6f8 repeatedly calling0xaf34 until it accepts
a descriptor, sleeping through0xf9ac(2) while it refuses. They then return1.
Function0x7074 allocates a pending-list node and likewise returns1 after
list insertion. These return values are acceptance/retention indications;
neither is proof of an acknowledgement from the destination. The real
MAC completion/status path still requires tracing and instruction tests before
exposing an SDK send-complete result. Private REA evidence is kept under
work/espnow-tx-completion-rea/.

Original0xaf34 has now also been replayed by tools/test_radio_tx_ring.py.
Five register configurations cover available/full admission, index progression
and9-bit write-index wrap. Accepted entries write the descriptor pointer;
refused entries preserve the slot/index. This confirms the REA interpretation
using original instructions. MMIO values, IRQ and frame-view helpers are modeled;
there is no hardware consumer, ACK or completion interrupt in that fixture.
Report:work/espnow-tx-ring/report.json.

## Original completion-ring decoder

REA identifies task3 at0x3820 as a completion consumer. It waits for task events,
calls0xe760 with a stack result, performs stock completion/statistics handling,
removes the packet from the outstanding table through0x65e0, and releases
management frames through0xd51c. Action subtype13 follows that management release
branch. The result at stack-result+4 is consulted as zero/nonzero by stock logic;
it is separate from the earlier queue-admission return values.

Original0xe760 reads the completion ring at MMIO base+0xd00 and advances its
9-bit consumer index. It reconstructs the descriptor address from the completion
word, resolves its metadata through the original frame-view accessor, and fills:
metadata pointer+0; completion status+4 (zero when descriptor+2 bit0 is clear,
one otherwise); completion-word bits24..27 at+8; descriptor+10 low nibble at+9;
combined completion-word bits29..31/bit1 at+10; descriptor+28 ushort at+12.
The nibble at+8 participates in stock retry statistics. Other fields retain raw
names until their exact semantics are verified. Empty queues return0 with a
null metadata pointer; nonempty queues return1 even for failed descriptors.

The descriptor address is reconstructed as
`(completion_word & 0x10fffffc) + 0xc0000000` modulo32 bits. These are radio CPU
addresses, not host RAM pointers. Completion words must never be used directly
as host pointers or treated as success codes.

tools/test_radio_tx_completion.py executes original0xe760 for six combinations
of descriptor failure bit and completion fields, plus an empty queue. It checks
metadata/status fields, original bookkeeping branch selection and index advance.
Report:work/espnow-tx-completion/report.json. Completion words/MMIO are synthetic;
frame-view and bookkeeping helpers are modeled. This proves parser behavior,
not physical ACK semantics or the eventual SDK completion callback. Before
hooking task3, correlate an owned submitted packet with its completion, retain
stock release exactly once and confirm successful/failed over-air cases.

## Experimental send/completion correlation

radio_tx_completion.c adds one outstanding send and one retained result. The TX
control arms the packet pointer and request token before original submission;
queue rejection cancels correlation, while original0xd800 remains responsible
for its rejection free. New allocation is refused while a send is pending or
its completion token has not been acknowledged. This is explicit backpressure,
not an unbounded result queue. Optional weak entry points keep the older isolated
TX/RX fixtures available; the combined completion fixture links the real module.

radio_completion_hook.S now intercepts the common management-free wrapper at
0xd51c with an eight-byte Thumb literal jump. The original task3 call site at
0x3a0c remains unchanged. Caller LR0x3a13 identifies task3's parsed MAC completion;
its original stack status/raw fields are captured. A tracked release from the
other original caller, task5's pre-MAC rejection, reports explicit software
status2 (PRE_MAC_REJECTED) with raw_fields0. This is not a hardware ACK result.
Untracked packets are ignored by correlation and still freed normally.

The wrapper calls original ARM0x1360 exactly once, retains its return value and
callee-saved registers, then publishes the completion token after free returns.
The original caller resumes normally; counter loads remain original instructions.
Pending clears last and native consumes only a matching token with pending0.
The prior task3-only hook could miss task5 rejection and leave stop waiting
forever, so review1/2 are not current full-stack candidates.

tools/test_radio_completion_hook.py compiles the combined RX/TX/word-command and
completion modules into1858 bytes of the1900-byte reservation. It checks
success/failure raw status correlation, unrelated completion interleaving,
unread-result backpressure, original release exactly once, rejected submission
and preserved task stack/register/displaced-load behavior. It executes the real
original packet allocator and release. Completion records and scheduling remain
modeled; there is no new radio download image or physical ACK claim.
Report:work/espnow-completion-hook/report.json. The completion control is still
an experimental radio ABI, now exposed through optional SDKalpha.4 full
services; physical device qualification remains separate.

## Experimental RX stop handshake

The radio RX control now appends enabled and producer_active after the existing
two slots. Admission defaults to disabled; native initialization must enable it
explicitly after loading/configuring the combined image. Entry checks enabled
and marks the single producer active under original IRQ save/restore using the
returned token. All accepted paths clear active only after publishing a queued
packet or releasing a private allocation. IRQ exclusion and single-producer task
scheduling remain platform assumptions awaiting physical validation.

Stop ordering is: write enabled=0; wait producer_active=0; read and acknowledge
all published queue entries; wait for outstanding TX completion before teardown.
If stop arrives during allocation/copy, the producer releases that allocation
instead of publishing when it observes disabled. A stop after that check may
still publish one final entry, but active stays set through publication so the
subsequent drain sees it. Stop is not a permission to forcibly free submitted
TX packets or unload code while callbacks can still run. Re-enabling during
stop is forbidden until the native owner completes its serialized lifecycle.

tools/test_radio_full_rx.py additionally stops with two unread packets, verifies
closed admission and acknowledgement drain, suspends actual compiled producer
instructions after allocation, disables reception and resumes. The private
packet is freed before active clears; head stays unchanged; later re-enable
works. MMIO/IRQ and task preemption remain modeled, not sleep/USB acceptance.

## Experimental native full backend

xnow_full.c/.h implement a serialized, synchronous-word-command backend for the
new control blocks. It is independent of chat and accepts standard binary v1/v2
payloads without an XNOW application header. Open requires disjoint aligned
control regions inside the reserved block, expected magic and clean ownership
state. The adapter must independently attest exact code/layout and bound device
access; these structural checks are not radio-code attestation. This private
experimental API is exported through optional SDKalpha.4 services, without
a physically qualified device profile or permissive ownership guard.

Send encodes the standard body, allocates an original large packet, checks its
exact three-slot pointer/capacity, uploads bounded words and explicitly sets the
destination. Partial upload failure aborts the still-host-owned allocation. A
submission-doorbell error or mismatched acknowledgement poisons the backend:
there is no blind retry after an ambiguous submission. Sequence0 is skipped so
zero remains an unambiguous no-inflight marker across32-bit wrap. Completion
polling returns MAC raw0/1 or explicit pre-MAC software rejection2, never
an application-delivery promise.

Receive reads a retained ring slot, bounds its packet/body, validates the whole
vendor-element chain and copies caller output only after successful queue
acknowledgement. Insufficient caller capacity retains the slot. Malformed bodies
are acknowledged/dropped; ambiguous acknowledgement poisons the backend without
exposing partially committed caller output. Stop steps close RX, wait active,
drain retained entries and await submitted TX completion. Errors/timeouts never
authorize force-free, radio reset or code unload. Whole-task callback quiescence,
stock owner restoration and sleep/USB coordination still require integration.

tools/test_xnow_full.py executes the C backend with a synthetic radio endpoint
under host ASan/UBSan and ARM926 QEMU using the hash-verified original Sony
loader/libc. Tests cover maximum binary payload, v1/empty data, completion,
receive capacity/output preservation, upload abort, uncertain commit/pop,
malformed input, pending stop and sequence wrap. This isolated fixture is supplemented by the combined instruction test below;
neither constitutes physical interoperability. The matching
adapter/platform qualification remains pending; the later sections describe
peer/security and optional SDK integration now implemented.
Report:work/espnow-full-native/report.json.

## Native/radio instruction integration

tools/test_xnow_full_integration.py links the actual native full backend into a
host library and connects its word callbacks to Unicorn execution of original
host dispatcher0x8078 and the combined compiled radio code. Both LOAD and STORE
transactions traverse that dispatcher; callbacks do not replace radio control
state transitions with a synthetic C state machine. Original packet allocation,
RX work factory/ring reader, original release and the compiled completion hook
all execute. Input DMA and completion events, ROM queues and scheduling remain
fixture boundaries. The native side runs host machine code in this particular
test; its separate original-libc ARM test remains necessary.

v1 payloads0/1/250 and v2 payloads251/1470 survive upload, retained RX copy and
native decoding. Submitted packets and received allocations coexist within the
three-block pool and return to it. Upload failure aborts a real allocation;
original queue rejection releases once; stop drains RX then waits TX; ambiguous
submission poisons native state without retry/force-free. The run performed681
read commands and613 write commands with no callback exceptions. These are test
transaction counts, not throughput or radio measurements.
Report:work/espnow-full-integration/report.json.

## Native peer-table implementation

xnow_peer.c/.h add a fixed20-entry volatile peer table with configurable encrypted
capacity0..17, explicit add/modify/delete/get/enumeration and counts. These limits,
channel0=current and unsupported encrypted multicast follow the Espressif
[ESP-NOW guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/network/esp_now.html).
Only individual unicast or all-FF broadcast addresses are accepted. Version is
explicit local policy, not negotiated capability; send validation rejects a
peer-specific channel different from the current channel or data exceeding its
v1/v2 limit. A failed validation leaves caller output unchanged.

LMKs are held in memory only; deletion, replacement and whole-table clear erase
them through volatile stores. Plaintext peers retain no key bytes. This is key
configuration/erasure, not encryption: the table is joined to the experimental endpoint, with optional security
attachment described below; default endpoint instances still refuse encryption. The peer table alone does not implement crypto; subsequent sections document
the optional security context and local key vault. Durable key persistence is not supplied. Public SDK integration must not silently send plaintext for a peer marked encrypted.

tools/test_xnow_peer.py runs table limits, duplicates, CRUD, enumeration,
channel/version validation, broadcast rejection and key-erasure tests under
host ASan/UBSan and original-libc ARM926 QEMU. Report:
work/espnow-peer-tests/report.json. Physical peer exchange remains unverified.

## Experimental peer-aware endpoint

xnow_endpoint.c/.h join the peer table to the native full backend. An explicit
destination queues one registered peer; NULL snapshots all registered peers.
The whole batch is validated for peer existence, channel and version/length
before transmission starts. Application payload is copied before return.
Polling sends one destination at a time and yields one correlated completion
result before advancing. There is no automatic packet retransmission; a fresh
caller-provided RNG output is required for each attempted send. No guessed
clock/counter-based random fallback exists. Peer edits are refused while a
batch is active. Raw completion status remains separately available.

Encrypted peers currently fail with CRYPTO_UNAVAILABLE before any plaintext
send, including an all-peer batch containing one encrypted target. On reception,
plaintext from a registered encrypted peer is consumed but not exposed to the
application; unpaired plaintext reception remains allowed. This avoids treating
key configuration as permission to downgrade security. It does not implement
CCMP or protected-frame RX. Stopping blocks further polls, cancels unsent batch
entries, waits/drains through the full backend, then erases peers, payload and
target snapshots. Whole radio-task quiescence and stock restoration remain
separate owner responsibilities.

tools/test_xnow_endpoint.py runs the endpoint plus actual native full backend
against a synthetic word-command endpoint. Host ASan/UBSan and original-libc
ARM926 tests cover all-peer validation without partial sends, channel/version
mismatch, encrypted refusal, copied payload lifetime, RNG failure, serialized
results, edits while busy, pending stop, key erasure and plaintext downgrade
rejection. Report:work/espnow-endpoint-tests/report.json. The endpoint has not yet been joined to the qualified device platform or physical test apps; optional SDK/security
integration follows below.

## Experimental CCMP-128 frame primitive

xnow_ccmp.c/.h use the already pinned BearSSL0.6 constant-time AES-CT CTR/CBC
backend for AES-CCM, not a custom AES implementation. The primitive supports
nonfragmented unicast Action headers with24-byte MAC headers,8-byte CCMP IV and
8-byte MIC, excluding FCS. It retains the management subtype in authenticated
frame control, masks mutable retry/power/more-data bits, authenticates the three
addresses and fragment number, and uses management nonce flag0x10, transmitter
address and big-endian48-bit PN. IV PN fields use the standard split little-endian
layout. Header/nonce construction follows the Linux mac80211
[CCMP implementation](https://github.com/torvalds/linux/blob/master/net/mac80211/wpa.c).
The CCM construction is documented by [RFC3610](https://www.rfc-editor.org/info/rfc3610/).
No upstream source was copied into this module.

Seal requires an explicit nonzero48-bit PN. Open checks Key ID/reserved bits,
rejects stale/equal PN and authenticates before updating the caller's highest
received PN. Decrypted output remains private until MIC validation succeeds;
failed authentication leaves caller output/length/replay counter untouched.
Temporary plaintext, expanded AES and CCM contexts are erased. Input/output
aliasing is refused. Multicast, fragmented and unrelated frame formats are not
silently accepted as supported security modes.

tools/test_xnow_ccmp.py produces12 independent PyCryptodome AES-CCM reference
vectors spanning body lengths0/15/16/17/265/1520 and two48-bit PN values. The
BearSSL C output matches those encrypted frames byte for byte under host
ASan/UBSan and original-libc ARM926 execution. Tests also cover MIC, ciphertext
and authenticated-header tampering, replay, Key ID, capacity and alias errors.
The reference independently exercises AES-CCM; its manually constructed framing
is a standard-format hypothesis, not an Espressif capture. Radio packet delivery
and actual Espressif management nonce/body conventions still require evidence.
Report:work/espnow-ccmp-tests/report.json; reference vectors are generated locally.
BearSSL source-archive identity and host/ARM archive hashes are retained.

This primitive is not connected to the radio or endpoint yet. The existing
radio RX deliberately falls back on protected frames and TX requires plaintext
body markers. Peer encryption therefore still reports unavailable. Local PMK wrapping is provided separately below; device-qualified
LMK lifecycle, device-qualified cross-restart nonce uniqueness and replay-state restoration
remain unimplemented; experimental TX reservation follows below. A caller-supplied PN is not a safe counter manager; restarting at
PN1 with the same transmitter/key is forbidden. No system/NVP counter writes or
implicit user-storage persistence have been added.

## Durable TX packet-number reservation

xnow_pn.c/.h define a48-bit PN allocator with durable range reservation. Its
namespace is SHA256 of a versioned domain, transmitter MAC and LMK, deliberately
excluding the peer destination and Key ID. The same key/transmitter used for
multiple peers must share one PN namespace because CCMP nonce uniqueness is
not scoped by destination. Keys and temporary hash state are not persisted.
The current opaque namespace is a key-derived fingerprint, not a wrapped LMK.

A reservation callback must atomically advance the durable upper bound before
returning an interval. Core code issues no number until that succeeds, validates
interval bounds/nonreuse, skips the remainder after restart and stops on
exhaustion. An ambiguous/failed reservation faults that allocator; it cannot
continue from a guessed counter. Multiple owners can reserve disjoint intervals,
but the radio owner must still serialize sends: independent intervals do not
promise monotonically ordered delivery to a receiver with replay checks.

xnow_pn_file.c/.h provide an internal POSIX adapter using a preopened directory,
expected device and mandatory ownership/mount guard. No directory is created and
no system-path fallback exists. A scope lock serializes read/update across
processes. Each80-byte record contains format/scope/upper-bound/checksum, not LMK.
Update writes an exclusive no-follow temporary file, synchronizes it, renames it
and synchronizes the directory before confirming the reservation. Symlinks,
hard links, wrong devices and nonregular/truncated/corrupt records are refused.
A missing record is not initialized by reserve. Separate explicit provisioning
is valid only for a proven fresh key; it refuses an existing record.

Failed writes preserve evidence. A stale temporary file blocks later allocation
rather than silently resetting or removing state. Counter records and namespace
must remain outside uninstallable app folders on verified user storage. The
adapter is not yet wired to the production mount/USB guard and has never written
to the player. A checksum detects corruption, not malicious rollback: restoring
an older storage snapshot or deleting PN data requires key rotation. Neither
fsync nor a test can guarantee all flash controllers survive arbitrary power
loss; physical FAT/device qualification remains required.

tools/test_xnow_pn.py executes core restart/skip, ambiguous commit, namespace,
invalid-range, exhaustion and erasure tests under host ASan/UBSan and original
Sony-libc ARM926. A separate host filesystem fixture checks two-process disjoint
reservations, ownership denial, missing/corrupt records, symlinks and injected
file/directory fsync failures. Files remain in ignored work/espnow-pn-tests.
The file adapter also compiles for ARM with stock stat-ABI binding; this is not
an ARM filesystem runtime pass. No physical power-loss test has occurred.
Report:work/espnow-pn-tests/report.json. Integration with CCMP/endpoint and durable
receive replay state is still pending.

## PN/CCMP/replay security context

xnow_security.c/.h join the standard wire codec, PN reservation and CCMP frame
primitive. Initialization binds local/remote unicast addresses, LMK and Key ID,
and requires an existing receive high-watermark via storage callbacks. Sending
encodes a complete standard Action frame, obtains a durably reserved PN and
seals it. PN namespace deliberately remains transmitter/key scoped across
multiple remote peers. A failed later operation consumes that PN rather than
rolling it back. Invalid/too-small requests do not require a reservation.

Receive first enforces local destination and configured remote source, then
verifies CCMP, decodes the full ESP-NOW body and checks output capacity. Before
exposing plaintext, it requires an atomic durable receive-PN commit. Failure
faults the context and leaves caller output untouched; restart must reload the
durable floor. Replay scope includes a separate domain, receiver, transmitter
and LMK. It is distinct from the TX namespace. RX persistence must reject values
not above its current durable floor, including changes by another owner.

Contexts wipe keys/state on explicit clear. Outputs/metadata may not overlap
context memory. Tests in tools/test_xnow_security.py cover bidirectional C
contexts,1470-byte payload, capacity without replay commit, restart replay
rejection, one transmitter/key shared across remote peers, MIC failure without
commit, ambiguous RX commit after durable advance, TX reservation failure,
address mismatch and context erasure. Host ASan/UBSan and original-libc ARM926
execution pass. The storage callback implementation in this fixture is an
in-memory durability model; it does not qualify real RX persistence or power
loss. The earlier independent CCMP vector test remains separate evidence.
Report:work/espnow-security-tests/report.json.

The security context is now linked to an optional endpoint adapter below;
physical radio/owner integration remains unqualified.
REA additionally resolves original0xacf4 descriptor construction and0x36f0 length
classification, but protected-frame submission has offline instruction evidence below, while
avoidance of unwanted hardware re-encryption on real hardware remains unproven. The production encrypted-peer refusal
is retained until those paths and Espressif compatibility are verified. Local key wrapping and RX file integration now have evidence below; physical
key/replay lifecycle remains required, not implied by the new context.

## Experimental pre-encrypted TX submission

tools/test_radio_protected_descriptor.py executes actual task5 preparation at
0x9e68 and original0xe840 descriptor construction for plaintext/Protected Action
pairs at31/281/1536 body bytes and two length-classification thresholds. The
fixture is unassociated, with no peer/key lookup, feature flags clear and modeled
MMIO/time/IRQ. In those cases descriptor controls are equal between plaintext
and Protected, ciphertext body stays unchanged, and only mutable Duration bytes
change in the frame. The original ring-admission instructions execute. This does
not exclude a later hardware operation on the actual radio or qualify AP/key
configured modes. Report:work/espnow-protected-descriptor/report.json.

A separate radio operation4, SUBMIT_PROTECTED, now admits structurally valid
pre-encrypted unicast bodies of31..1536 bytes. It preserves the standard CCMP
IV/ciphertext/MIC, uses the original header builder and sets Protected afterwards
(the builder clears that bit). Existing operation2 still requires plaintext
ESP-NOW markers. Multicast and invalid IV shape are refused. This is not MIC
verification: trusted native code must produce/authenticate the protected body.

xnow_full_send_protected accepts a complete protected Action frame and requires
its transmitter to match the adapter-verified local address. It checks destination,
header/fragment/A3/IV shape, uploads only the body and uses operation4. The radio
supplies that same actual source through the stock header builder. Source
attestation is a necessary device-adapter responsibility, not caller guesswork.
An internal API with a caller-supplied MAC does not itself attest hardware.

The full integration test now independently encrypts250/1470 application bytes
with PyCryptodome AES-CCM, submits through native word commands and compiled
radio code, and verifies FC/address/body preservation plus original release.
Wrong source, multicast and reserved-IV inputs are rejected before allocation.
Actual MAC encryption/transmission remains unmodeled. This operation is not
connected to the public endpoint, whose encrypted-peer refusal is unchanged.
Protected RX now has the offline path below; the real device adapter,
security-context integration and over-air Espressif validation remain required. No new radio download image was generated.

## Protected RX and canonical native Action frames

The experimental radio RX now accepts unicast Protected Action frames with valid
CCMP IV shape, retaining up to1536 body bytes (IV+ciphertext+MIC). Frame length
remains bounded by the original singleton work object; original0x4b9c copies
length-16 bytes. The1584-byte record bound gives1568 copied bytes, inside the
1608-byte frame extent. Plaintext remains limited to1520 body bytes. A3 must be
broadcast, fragment number zero and DS/MoreFragments/Order absent. Broadcast
protected traffic is refused. Source and protected/broadcast flags are published
with the retained slot; ciphertext is not marked as authenticated plaintext.

To fit the reservation, redundant first-element/version inspection was removed
from the radio plaintext filter. Category/OUI/bounds/address checks remain; the
native wire decoder still validates every element and drops malformed bodies
before exposing application data. Protected packets cannot be identified by a
plaintext ESP-NOW OUI; their eventual peer/CCMP/format validation belongs to the
native security owner. Queue bounds/drop counters limit retained allocations,
not adversarial RF airtime or flooding.

xnow_full_receive_action reconstructs a canonical24-byte Action header with
adapter-verified local destination (or broadcast for plaintext), actual retained
source, broadcast A3, normalized Duration/sequence and Protected flag. This is
not an exact RF-header capture. Canonicalization preserves CCMP-authenticated
fields only because radio admission checked A3/fragment/control constraints;
mutable header fields do not enter authenticated AAD. Structural checks are not
MIC verification. The plaintext receive API reports FULL_PROTECTED without
consuming that slot. A plaintext-only endpoint explicitly discards it and
reports crypto unavailable, preserving the no-downgrade policy and queue flow.

The full integration test injects independent AES-CCM frames in reverse direction
through original RX ring reading and compiled radio copying. Native canonical
frames match the expected protected bytes and pass independent authenticated
decryption for250/1470 application bytes. A too-small output preserves the slot.
The radio RX fixture additionally checks protected/broadcast rejection, A3 and
fragment rejection, metadata flags and original packet return. These fixtures
start at a synthetic DMA producer; they do not prove that physical firmware/MAC
admits unknown encrypted peers before the hooked callback.

The later stock-task replay now executes more software before this boundary:
tools/test_radio_rx_task_dispatch.py enters the original MAC task clause at
c000323a after work-node acquisition, performs the original pointer store,
e164 ring poll,4b9c copy, wrapper read, management-type test and ARM veneer
c00026a8 through target wordc00026b0 into the compiled full RX bridge. The actual
task loop performs its empty-ring check and releases the original singleton work.
No RX ring-poll or copy return is substituted in this test. DMA producer/MMIO
indices, ROM IRQ behavior and initial work-node acquisition are fixture inputs.

Plain0/250/1470-byte payloads and Protected31/281/1536-byte bodies reach the queue
unchanged; a data-type frame is not dispatched by the management clause, and
disabled bridge traffic follows original fallback. The clause does not consult
original peer lookup5710 or reject Protected status. REA/Ghidra review of pinned
stock procedures mac_mgmt_task(c0003188),e164 and subtype dispatcha314 agrees:
this clause checks wrapper/length and management type, not an existing peer/key.
An alternate task branch atc00032cc uses the same veneer but is not executed by
this new clause fixture. Reports:work/espnow-rx-task-dispatch/report.json and
work/espnow-rx-dispatch-rea/inputs.json. This closes a software-dispatch gap only;
it still does not prove that hardware supplies unknown-key Protected frames to
these rings, nor whether hardware has modified their ciphertext.

The subsequent original MAC_CONTROL replay identifies upstream register controls,
but does not yet qualify them for device use. Flag80 changes register8000a300
mask0b; flag100 controls mask40; helpers54c0/6b6c select masks4300 at8000200c and200
at8000a300 using different combinations of MAC flags and context bytes. Repeated
promiscuous enable overwrites the original register backup in the fixture, so a
later clear need not restore baseline. See the numeric branches and primary-source
comparison in [RF hardware](RF_HARDWARE.md). No adapter write or mode toggle was
implemented from this evidence. Report:work/espnow-mac-control/report.json.

Original Sony driver defaults are now traced separately: the adapter filter
halfword at13c4 is initialized to0203 and supplied to the post-download0028
command, whose actual builder emits12 bytes. The observed startup command prefix
is0003/0028/0074/0076/001e with transport responses mocked. This does not execute
firmware download or establish hardware key clearing. In particular, preserve
the unknown0200 flag bit rather than reducing stock defaults to generic RX/TX
flags. No new configuration command is sent by the custom adapter based on these
findings. See work/espnow-driver-station-init/report.json and the RF guide.

Original activation resetc5e4 and refresh wrapperc0006144 now have separate
instruction tests. Reset clears selected activation bytes/flag0400 but preserves
other sampled memory and performs no MMIO writes itself. The wrapper retains
context byteP and can therefore select register4300 even after activation reset.
Connection-result code can later repopulate related state. This does not qualify
hardware key clearing on reload, and no reset command/field write is added to
the adapter. See work/espnow-security-reset/report.json and the RF guide.

The private Radio Inspect0.1.0-alpha.1 executable now implements a bounded GET-only
comparison tool for these observations. It checks the known driver string and
partial stock/full code fingerprints, validates context pointers within BSS, and
compares two sequential samples before output. No SET/mode/channel/reload/key/file
write or arbitrary-address CLI is supplied. It is built with original Sony libc;
help/version and mocked-driver inspection execute under ARM926. Fourteen host
observer cases cover both images, mismatch/read failure, absent or invalid pointers
and changing state. The ARM ioctl boundary asserts0086/action0/20-byte requests.
These are modeled reads, not device acceptance or atomic ownership proof. See
[Radio Inspect](../runtime/platform/espnow/inspect/README.md),
work/radio-inspect/0.1.0-alpha.1/build.json and tests.json. No app/SDK deployment or
driver/radio modification was made for this tool.

Combined RX/TX/word-command/completion code now consumes1858 of1900 reserved
bytes with the current toolchain. No new radio image is emitted. Exact-code
attestation, production owner/security integration, physical Protected RX,
Espressif compatibility and stock restoration remain unverified.

## Secure endpoint and receive-counter file integration

xnow_endpoint_security.c/.h supply an optional native security adapter. The base
endpoint retains no BearSSL dependency and explicitly refuses encrypted peers
without the adapter. Attachment requires an idle peer-free endpoint, verified
local MAC and complete storage callbacks. Encrypted batch targets prepare a
source/destination/LMK-bound security context before sending. Polling seals via
PN reservation and CCMP, then uses the pre-encrypted full-radio submit operation.
No error falls back to plaintext. This is native integration, not a qualified
physically qualified installed adapter or hardware acceptance claim.

Protected receive uses the canonical full-radio frame, verifies registered peer
and LMK, authenticates/decrypts and commits receive state before application
output. A too-small caller buffer retains one private ciphertext frame without
committing replay state, permitting a later larger read. Plaintext from an
encrypted peer remains rejected. Key replacement/deletion clears bound contexts
and related cached data; successful stop clears workspace, keys and peer table.
The peer table and adapter workspace retain LMKs only in volatile RAM.

xnow_pn_file_load_rx/commit_rx now share the original guarded locked journal
implementation. Commit requires PN greater than the currently stored durable
floor under the lock and follows file-fsync/rename/directory-fsync before success.
Missing records are not provisioned implicitly. The scope helper exposes a
key-derived namespace for explicit fresh-key setup without resetting old state.
Storage rollback/removal and real FAT/power-loss limits remain unchanged.

tools/test_xnow_endpoint_security.py executes the real endpoint, full backend,
security context and crypto with synthetic radio/storage callbacks under host
ASan/UBSan and original-libc ARM926. It covers Protected submit,1470-byte decrypt,
capacity retry, persisted-floor reload, MIC failure, replacement/deletion and
stop erasure. Report:work/espnow-secure-endpoint-tests/report.json.
The PN host filesystem test also connects actual file callbacks to security
contexts, confirms restart replay rejection and injects a post-rename directory
sync failure: no plaintext is output and reload rejects the advanced PN.
Report:work/espnow-pn-tests/report.json. Neither fixture is whole endpoint-to-radio
instruction integration or physical encrypted interoperability. The radio-only
instruction tests and independent crypto vectors remain separate evidence.

## Whole secure endpoint/journal/radio instruction chain

tools/test_xnow_secure_chain.py adds a test-pipe bridge between the actual C
endpoint and original command dispatcher plus compiled radio ARM code. The C
driver includes CCMP, real POSIX PN/replay journals and the peer/security adapter;
its word I/O is not a synthetic radio state machine. Native radio allocation,
retained RX copy and original completion-release instructions execute in Unicorn.
The driver provisions only known-fresh fixture keys in unique ignored test
directories. Its permissive host-directory guard is test-only, not a device
mount/USB policy implementation and never installed on the player.

The default run executes native C under host ASan/UBSan. With --arm, the same
C driver compiles for ARMv5 and runs on ARM926 QEMU with hash-verified original
Sony loader/libc, stock stat64 bridge, crypto and actual file operations. The
original-libc scanf symbol is bound explicitly to avoid modern header redirects.
Both executions bridge to the same original radio instruction fixture.

Each run covers1470-byte encrypted send, independent PyCryptodome authentication
of transmitted body, Protected RX, capacity retry, durable replay rejection,
MIC failure followed by valid same-PN acceptance and stop erasure. After endpoint
recreation, transmitted PN moves1 ->1025 because the prior1024-number interval
was already reserved. Final queues/allocations return to baseline. Each run uses
1379 LOADs,793 STOREs, two modeled completion events and five synthetic DMA
injections. These are test counts, not throughput measurements.

Reports:work/espnow-secure-chain/report.json and
work/espnow-secure-chain-arm/report.json, bound to current native/radio sources.
This is whole-chain offline evidence. It does not execute the original Linux
kernel, real FAT/controller power-loss behavior, actual MAC/DMA hardware, hardware
ACK or unknown-key protected RX admission. Physical Espressif interoperability,
stock restoration, qualified device platform and physical app integration remain unfinished;
local PMK/LMK wrapping is covered below. No radio download image or device write occurs.

## Local PMK/LMK vault

xnow_keywrap.c/.h implement local RFC3394 AES-128 key wrapping for16/24/32-byte
inputs with BearSSL constant-time AES. xnow_keyring.c/.h maintain a20-entry
volatile vault. Wrapped material includes LMK, peer MAC and format bytes, binding
each blob to its peer; swapping blobs between peer entries fails integrity.
Unwrap returns no unauthenticated key. Delete/clear erase material; a cleared
vault cannot accept keys until explicitly initialized again. PMK rotation first
unwraps and rewraps all entries into a temporary vault and only commits if every
entry validates. Corruption leaves the old PMK/vault unchanged.

This is a project-local packaging format, not a claim about Espressif's private
key storage. Espressif documents PMK-based AES protection of LMKs but does not
specify this local serialization. PMK is explicit; no undocumented Espressif
default is guessed. The active endpoint still requires usable LMKs in RAM.
No vault file, PMK persistence, secure hardware storage or protection against a
privileged process reading memory is implied. Saving PMK next to wrapped blobs
would not provide meaningful at-rest protection.

The implementation follows [RFC3394](https://www.rfc-editor.org/rfc/rfc3394.html).
tools/test_xnow_keyring.py matches its section4.1 known vector and checks tamper
rejection, overlapping-buffer operation, peer binding,20-entry limit, atomic
rotation failure and erasure under host ASan/UBSan and original-libc ARM926.
Report:work/espnow-keyring-tests/report.json. Both whole-chain fixtures now load
peer LMK through the vault, rotate local PMK before endpoint recreation and
verify LMK/PN continuity: PN still moves1 ->1025. Changing local PMK does not
rotate the actual LMK or reset its nonce/replay namespace. This is local key
management evidence, not additional over-air compatibility evidence.

## Combined full-radio research image builder

tools/build_espnow_full_radio.py compiles maintained sources directly and emits a
local radio-only candidate, original radio/helper copies and manifest in a new
work directory. It requires the pinned original radio and helper hashes and
never opens a device, modifies a driver/kernel or invokes Sony's updater.
The output is not a flashable system UPG and has no loader/install script.

The builder validates ARM/Thumb entries, loaded section types/ranges/nonoverlap,
clean disabled control state and exact hook preconditions. It applies six
coordinated edits: three-block packet pool, RX veneer, command0x86 jump,
completion-release jump and two scatter-zero ranges. The two Thumb jump sites
have different literal alignment and are generated separately. Original loaded
bytes outside those ranges remain identical; added memory is exactly the1900-byte
reservation and no unrelated BSS byte is excluded. Container/header/payload CRC
roundtrip is checked. The manifest records control addresses, entry points,
immutable aligned segment hashes, source/compiler/helper and candidate identity.
These hashes enable a future device adapter; their existence is not attestation
of a currently running radio.

Current local candidate:work/espnow-full-radio-review-3/.
Radio SHA256:d4b92b65fa502e2c8c94d241e4a293e28db7e98a3afdba0958d8b4f8aa1a5ed8.
Code/state section bytes total1858, but a two-byte alignment gap makes occupied
span1860 and true tail margin40 bytes. Earlier section-size reports did not
include that gap; capacity claims must use span, not sum of section lengths.
The linker bounds the full span and the generated reservation remains1900 bytes.

```sh
python tools/build_espnow_full_radio.py \
  --original work/targets-jp/sd8686.bin \
  --helper work/targets-jp/helper_sd.bin \
  --output work/espnow-full-radio-review-3
python tools/test_espnow_full_radio.py
python tools/test_xnow_secure_chain.py --candidate work/espnow-full-radio-review-3/candidate/sd8686.bin
python tools/test_xnow_secure_chain.py --arm --candidate work/espnow-full-radio-review-3/candidate/sd8686.bin
```

The output directory must not already exist. Preserve the reviewed candidate
when rebuilding elsewhere; the current audit fixture defaults to review3 (an explicit build-directory argument is also accepted).
tools/test_espnow_full_radio.py independently checks original-byte preservation,
scatter/pool and both literal branches, then rejects eight wrong input/payload
cases plus truncated/trailing container data. Verification:
work/espnow-full-radio-review-3/verification.json.

The whole-chain test's --candidate option loads the actual parsed download
records into Unicorn, verifies manifest/compiled code and uses those bytes for
host and original-libc ARM926 secure-chain runs. Both pass with real host-file
journals and original packet allocation/free. This closes the packaging-to-code
gap in the fixture, not helper boot transfer, original scatter execution on a
physical device, RF/MAC behavior or restoration. No hardware load occurred.

## Exact runtime profile and bounded driver adapter

The builder now separates immutable runtime segments from startup-only scatter
metadata. Original code reclaims the scatter table after initialization; treating
it as permanent identity would falsely reject a valid running image. Review2 corrected manifest classification; review3 additionally replaces the
completion hook with the common-free observer. Older reviews are preserved as
earlier evidence, not compatible current candidates. generate_espnow_full_profile.py derives
a compiled internal C profile from original input, ELF and verified candidate;
its runtime fingerprints deliberately exclude reclaimed startup metadata.

xnow_full_guard.c/.h sit between private original-driver word I/O and the native
full backend. Open hashes the compiled profile's immutable code, then checks
three-block pool and control identities. Control reads are bounded; packet reads
require the current retained RX slot and original node/descriptor ownership.
Packet writes require a live allocated TX pointer/capacity and remain within its
body region. Only required request, operation, length/destination, RX ack/enable
and completion-ack fields can be written. Packet/pointer/header/code fields are
not exposed for arbitrary writes. Submitted TX pointers lose write permission.
Commit-I/O uncertainty or lease invalidation faults the instance; restoring a
boolean later does not reactivate it. Close alone does not drain or restore.

The profile is trusted compiled build output, not caller-supplied untrusted JSON.
Runtime fingerprints are not full RAM attestation. The lease callback is a
mandatory platform contract: it must actually invalidate on USB/sleep/reset or
exclusive-owner loss. The test's boolean lease is not a production ownership
implementation. Runtime code is not rehashed before every packet word.

xnow_sd8686_full.c/.h add the original JP1.11 Linux transport:32-bit iwreq,
eth0 command0x86 on ioctl0x8be4, strict20-byte response/status checks, driver
version string, bounded profile/ownership adapter and actual source-MAC read.
The MAC pointer must remain within original BSS, then pass unicast validation.
Only after identity/MAC checks does native open enable RX. It does not load a
radio image, disconnect/set channel, write files or restore original firmware.
The existing fixed32-byte adapter remains unchanged. Integration with a real
exclusive owner and platform lifecycle is still pending.

The whole-chain test now supports --guard and --arm --driver, requiring a real
built --candidate path. It deliberately reclaims startup scatter bytes, injects
an immutable-code mismatch, refuses arbitrary/control-pointer writes and writes
to submitted packets, then verifies permanent invalidation after lease loss.
The ARM driver variant mocks proc-info/socket/ioctl while retaining actual iwreq
layout, envelope validation, guard and native code. Mock ioctl dispatches into
original radio instructions; no real socket/device command occurs.

```sh
python tools/test_xnow_secure_chain.py --guard --candidate work/espnow-full-radio-review-3/candidate/sd8686.bin
python tools/test_xnow_secure_chain.py --arm --driver --candidate work/espnow-full-radio-review-3/candidate/sd8686.bin
```

Host ASan/UBSan and original-libc ARM926 runs pass the full encrypted/file-journal
chain with the actual parsed image. The guarded ARM run performs22186 model LOADs
and793 STOREs, substantially more than the unguarded fixture due to per-word
ownership/identity checks. This is not a latency/throughput qualification; real
ioctl cost and safe batching must be measured before deployment. Reports remain
work/espnow-secure-chain/report.json and work/espnow-secure-chain-arm/report.json.
No physical adapter open, candidate load or stock restoration has been attempted.

## Pre-MAC rejection and stop regression

Original task5 can release an accepted software-queue packet through0xd51c when
its0x68e8 submission returns0, before any hardware completion event exists. The
new common-free hook covers that path as well as task3 MAC completion. It leaves
original ARM0x1360 ownership/free behavior intact and reports software status2
instead of mislabeling the event as MAC failure/success.

The radio fixture verifies status2, one release and terminal token. Both whole
secure-chain variants additionally execute original task5 instructions starting
at0x9eb4, including its BL to the hooked common wrapper; no hardware completion
is injected for that packet. Native endpoint receives status2 and stop finishes
with full pool return. The rejected packet's PN1026 remains consumed; successful
transmissions before/after endpoint recreation still use PN1 and1025. This is a
new covered failure path, not a physical MAC-completion qualification.
Review3 uses full-radio-experimental-v2, retains1860-byte occupied span and keeps
all earlier local images. Host guard and ARM driver-mock secure chains pass with
the parsed review3 candidate. No physical candidate load or restore occurred.

## Full owner controller and delayed endpoint startup

xnow_full_control.c/.h reuse original xnow_session, xnow_manager and
xnow_loader_job actions for the full-radio profile. The older fixed32 controller
is unchanged. A fresh full owner requires the compiled profile, explicit radio/
IPC/exclusive-lease guards and RNG. Guards have no permissive production default;
actual USB/mount/epoch exclusion is still a platform integration requirement.
The original loader's candidate path and unchanged Sony scripts are retained.

Candidate verification uses xnow_sd8686_full_probe, which checks code/pool/MAC
and opens its socket without enabling RX. Original RF INITIALIZE completes
before CONFIGURE sets and reads back the channel through the original48-byte
command. Only then does xnow_full_open enable RX and endpoint_init expose the
native endpoint. This prevents receiving into custom queues before original RF
initialization/channel setup. Security attachment remains an explicit caller
operation on the returned idle endpoint, with existing journal/key policies.

Stop immediately marks the endpoint stopping and withdraws the public accessor.
The socket remains open while endpoint_stop_step closes RX, drains retained
packets and waits submitted TX. Session stays READY during this drain, but it
is not accepting new app work. After successful drain, the controller closes its
adapter and advances original restore-unload, stock-load, wake/verify/initialize,
optional reconnect and release. Worker cancellation never substitutes for a
completed/drained worker. Failed restore retains the manager client and repair
state for explicit retry; lost workers, uncertain drain or invalid ownership
latch uncertainty without forced unload/release. This policy is not a guarantee
that real hardware restoration always succeeds.

tools/test_xnow_full_control.py executes actual full controller/session/manager
logic with substituted cnmgr, worker/radio/endpoint effects. Host ASan/UBSan and
original-libc ARM926 runs check probe-before-RF, endpoint-open-after-configure,
drain-before-close/restore, cancellation during a load, denied disconnection,
startup failures, restored-network config erasure, repair retry, lost worker and
lease loss. Report:work/espnow-full-control-tests/report.json. This is a policy
fixture, not the real original loader/kernel or physical restoration test.
The separate ARM secure-chain driver fixture now also checks probe leaves RX
disabled and validates explicit channel SET/GET response before opening RX.
Its ioctl RF response remains mocked, not actual channel change evidence.

## SDKalpha.4 and XNOWdev.10 source integration

SDK0.2.0-alpha.4 adds optional espnow-full, espnow-security and
espnow-full-device native services. The first provides wire/backend/peer/endpoint
and PN interfaces; security adds CCMP, journals and local key packaging through
a separate crypto-aes dependency rather than HTTP/chat. Full-device reuses the
existing original-driver services and adds the bounded full adapter/controller.
All modules retain no-use-case restrictions. Linking/consumer tests do not open
a device, disconnect Wi-Fi or load a radio image. The generated profile and real
exclusive/mount/USB/epoch guards remain explicit integration requirements.

Public forwarding headers reside under sdk/include/x1000/services. XNOW archive
version advances to0.1.0-dev.10 and compiles implementations for the complete
header set it packages; crypto objects need separately acquired BearSSL0.6 when
linked. Whole-archive original-libc ARM linking and no-device execution pass.
SDK contracts advance together; installed apps/firmware remain untouched.
Native-services builds include the BearSSL notice for crypto-only selections.

The SDK consumer test builds full, security and full-device independently through
public headers and the declarative compiler, executing on ARM926/original libc
without radio/filesystem access. Existing core/message/device consumers also
pass, and public full headers compile as host C++11. See tools/test_sdk_espnow_full.py
and docs/sdk/ESPNOW.md. A clean extracted source-bundle validation passed: source manifest, fresh
pinned dependencies, three templates, all existing native services and both
old/full ESP-NOW public consumers. Original work inputs were not copied. This is not a public
GitHub release or evidence of complete physical ESP-NOW interoperability.

## Cooperative owner gate and separate data revocation

Private prototype xnow_owner_gate.c/.h reuse the existing abstract Unix socket
namespace x1000-xnow-chat-owner-v1 so legacy chat and future full owners cannot
cooperatively bind simultaneously. This socket is RAM-only and creates no FAT
lock file. It does not exclude Sony daemons or establish USB/kernel ownership.
Radio validity checks the owning PID, actual socket dev/inode and abstract name,
not merely a boolean. Inherited FDs are close-on-exec; original loader children
also close their inherited descriptors. Unrelated forks must not retain them.

The gate duplicates a verified read-only inherited command FIFO without consuming
protocol bytes. HUP/error, an external stop token or failed external storage
permission latches data revocation, including HUP with queued commands still
present. The owner loop must run gate_step before accepting commands; it requests
full-controller stop and lets the endpoint drain. New PN/journal writes use the
separate storage guard and are denied after revocation. Cooperative radio
exclusion remains held for original unload/restore/reconnect until the real
controller reports finished. Failed repair/uncertainty does not authorize lease
release. FD identity changes latch invalidity; release never closes a foreign
file that reused the old descriptor number.

The external storage callback must prove actual user-volume/USB permission. The
socket/FIFO/stop token cannot prove it. Likewise radio validity must be composed
with qualified hardware/driver epoch policy, not used alone as a production
USB/sleep lease. Original proxy callbacks4/6 request SIGTERM of the direct child;
their numeric identities alone are not labeled USB/suspend here. The known
launcher can eventually kill its app group, whereas the old radio owner is
separate and observes command-pipe EOF. Neither that topology nor the new gate
proves original APF waits for the radio owner's storage/restoration completion.
Real APF/USB/suspend ordering still requires analysis and device tests.

tools/test_xnow_owner_gate.py uses actual local abstract sockets, pipes, poll,
fork and FD reuse under host ASan/UBSan and original-libc ARM926. It checks raw
legacy-style bind exclusion, PID refusal in a fork, HUP with unread data,
stop/storage-revocation retaining the radio lease, step/drain behavior, release
refusal before controller finish and protection against closing reused FDs.
Original connection-manager/loader effects remain the controller fixture's
substitutes. A separate test namespace avoids binding the production name.
Report:work/espnow-owner-gate-tests/report.json. No player or RF access occurs.

This prototype is not yet part of SDKalpha.4 or its source bundle. The standalone
library builder now exports only headers used by compiled archive sources plus
the public umbrella, removing stale generated headers. This prevents private
research headers advertising absent archive functions. Existing SDK/API versions
and reviewed source archives are not relabeled to include this prototype.

## Original proxy exit boundary and detached radio owner gap

Fresh REA analysis of pinned original appproxy confirms function0x94e8 repeatedly
calls waitpid(-1,status,WNOHANG) and writes8-byte PID/status records to its pipe.
Function0x96a0 reads one complete record and proceeds to proxy receiver cleanup;
it does not inspect a radio restoration token. The0x95c0/0x969c branch-stub REA
lookups resolved ambiguous procedures and are not used as decompilation evidence.
Private evidence:work/espnow-proxy-order-rea/verified-procedures.json.

tools/test_xnow_proxy_owner_boundary.py replays the existing original monitor/
SIGCHLD harness without overwriting its standard reports. It checks both stop
events4/6 with supplied waitpid return PID321 and433 while the stored stop target
stays321. Original monitor returns after either exit record, demonstrating no PID
match or radio-restored filter at this boundary. This is a supplied direct-child
fixture; it does not claim the detached radio worker is a child of proxy.
Report:work/espnow-proxy-owner-boundary/report.json.

The8-byte[8,3] message captured during cleanup goes to proxy's own event address,
not manager55; it is receiver shutdown/wakeup, not a storage/radio-restored ACK.
Existing manager reaper/Responder handoff evidence is a separate downstream
boundary. The2.6-era proxy cannot be assumed to reap an unregistered detached
radio descendant. Keeping the radio owner alive through launcher/app teardown
therefore does not itself make APF wait for its restore or PN-file closure.

A qualified handoff needs a foreground launcher/supervisor completion dependency
on the managed radio worker before that registered native child exits. It must
include explicit restoration success and failure handling, not just worker EOF,
PID presence or busy-file unmount refusal. The production launcher/proxy remains
unchanged in this work. Original manager timeouts, actual USB export order and
sleep remain unqualified; no new USB access/prohibit ioctl was introduced.

A read-only availability probe found COM17 and TCP2323 reachable, but saved
Terminal authentication did not establish a shell. No remote command, radio
reload or configuration was performed. The current connection code is requested
for later read-only device inspection; prior physical chat acceptance does not
qualify this full encrypted path or the handoff boundary.

## Foreground handoff prototype across UI termination

Private xnow_handoff.c/.h add a foreground-supervisor/managed-owner completion
pipe. The supervisor creates a correlated launch cookie, intentionally passes
only the writer into the app-launch child and drops its own writer after fork.
The owner can emit the fixed32-byte DONE record only after full_control_finished
confirms quiescent original-action cleanup. The supervisor requires a complete
matching record plus writer EOF; empty/partial/wrong-cookie/extra EOF is uncertain,
not success. A valid record without EOF remains pending. Cookie correlation is
not cryptographic authentication of arbitrary privileged code.

Caller integration must keep the registered foreground child alive while handoff
is pending/uncertain and must explicitly close user-storage descriptors/cwd before
owner notification. The primitive does not inspect arbitrary application FDs,
register APF callbacks, force a launcher to stay alive, or prove real radio restore.
It installs no signal handler, kills no worker and changes no manager/USB state.
Its writer must be transferred without accidental inherited duplicates; callers
handle SIGPIPE. A supervisor must not reset a pending object to bypass failure.
The production launcher and already shipped SDK remain unchanged.

tools/test_xnow_handoff.py runs actual fork/pipe behavior under host ASan/UBSan
and original-libc ARM926, with original-action hardware effects substituted. It
covers controller-not-finished refusal, correct DONE, short record, wrong cookie,
extra bytes, empty EOF and record-without-EOF. Report:
work/espnow-handoff-tests/report.json.

tools/test_xnow_supervised_handoff.py exercises the unmodified actual
hb_process_run_observed and POSIX backend using real host processes/signals.
The UI forks a setsid owner, closes its handoff writer and, after SIGTERM, closes
the command writer but remains alive. The existing launcher kills that UI after
its normal100 wait ticks. The foreground test supervisor then waits the completion
pipe rather than returning immediately. In the normal case, simulated original
radio cleanup lasts6.5 seconds and the UI is already reaped with status9; release
is permitted only after owner cleanup, user-cwd release and DONE/EOF. In the crash
case, owner exits before restore with status76; EOF yields uncertainty and no
release permission. The bounded failure fixture exits after checking this refusal;
it is not a production APF release. Reports:
work/espnow-supervised-handoff/report.json.

Only the outer PC test harness enables subreaper mode to reap its own orphaned
test children. Launcher/owner runtime code does not require a modern subreaper
kernel facility. Cleanup verifies waitpid parentage before signaling any known
fixture PID. Radio/cnmgr/loader effects remain mocked; original APF, USB export,
manager deadlines and actual firmware recovery are not exercised. No device
program, launcher artifact, SDK version or radio image was deployed or changed.

## Explicit managed-launch wrapper without manifest changes

Private xnow_managed_process.c/.h turn the handoff pipe prototype into an opt-in
foreground call path. Existing app_catalog rejects unknown app.ini keys, so no
new manifest flag or default launcher behavior is introduced. The wrapper calls
the unchanged hb_process_run_observed with composed callbacks, deliberately
inherits the writer and appends bounded XNOW_HANDOFF_FD/COOKIE launch variables.
Existing reserved variables, oversized environments and invalid inputs are
refused. Parent polling drops its writer and still forwards original stop/
child-detach callbacks during UI execution. Cookie is launch correlation only.

After UI reap, the wrapper returns PENDING with raw app status retained. The
caller must keep the registered foreground process alive and poll until explicit
owner DONE+EOF. Close refuses pending/uncertain state; worker crash cannot become
success. A known pre-fork failure with no armed pipe closes its unused pipe and
returns IO; uncertain wait/reap stays latched instead. The app-side capability
adopter validates decimal FD, FIFO/writer type and32-hex nonzero cookie, then
reinstates CLOEXEC. Verified owner transfer must explicitly preserve the FD; it
must not overwrite existing IPC descriptors or leak it into unrelated children.

The production platform_arm run_app, app_process behavior, catalog schema and
installed apps remain unchanged. Managed calls must be selected explicitly by a
future launcher integration. Merely calling begin/poll does not force original
APF to wait, prove USB ownership, or replace the requirement to handle repair
without returning the foreground process. Parent resources/events during the
post-UI wait remain caller responsibilities.

tools/test_xnow_managed_process.py uses the wrapper with actual host launcher,
UI fork/exec, detached owner, pipes and signals. It verifies original callbacks,
inherited FD/cookie adoption and reserved-variable refusal. The normal6.5-second
cleanup outlives the UI SIGKILL/reap and only then permits completion. The owner
crash case is uncertain and refuses release. Real radio/APF effects are mocked;
outer subreaper remains PC cleanup only. Report:
work/espnow-managed-process/report.json.

tools/test_xnow_managed_environment.py covers capability parsing, CLOEXEC,
malformed FD/cookie, bounded/reserved environment checks and known pre-fork
failure cleanup under host ASan/UBSan and original-libc ARM926. It does not exec
an ARM app. Whole real-process wrapper testing is host-only at this stage.
Report:work/espnow-managed-environment-tests/report.json. These private APIs are
not added to SDKalpha.4, exported by its archive or deployed on the player.

## Compile-time opt-in launcher review integration

platform_arm.c now has an HB_MANAGED_RADIO_REVIEW-only run_app branch. Ordinary
builds retain the existing hb_process_run_observed path, catalog schema and
launcher version. No existing installed application is marked or changed.
The opt-in bridge checks an80-byte launch.contract sidecar:15-byte
XNOW-MANAGED-1 newline prefix, the already catalog-verified lowercase SHA256 and
one newline. Absent means legacy; malformed, wrong-hash, nonregular or linked
markers fail closed before launching. This marker is not a signature/USB grant.
Old launchers ignore it, so a managed-aware app must refuse RF activity unless
it actually adopts the inherited capability.

xnow_launcher_bridge.c invokes the managed process wrapper with fresh correlation
bytes from /dev/urandom and keeps servicing the original stop observer while
waiting. Only a confirmed handoff returns the UI status; uncertainty retains the
foreground and emits one diagnostic instead of returning to Sony. Original APF
can still impose deadlines/kill; real behavior remains unqualified. Do not add a
marker to an old unaware chat app: it cannot send the required completion record.
No automatic package metadata/installer migration is introduced.

Parent handoff logic is split from xnow_handoff_owner.c, so the lightweight
launcher links no radio controller, cnmgr or BearSSL implementation. The review
builder enables the branch only with --managed-radio-review and requires a
separate output. Its review SemVer is0.1.0-alpha.1+managed-radio-review; the base
native/firmware/SDK versions remain unchanged. Stock-libc compilation disables
modern fortify imports for the added bounded helpers. A failed earlier compile
was retained separately; no unchecked __read_chk alias was introduced.

```sh
python tools/build_libc_frontend.py --managed-radio-review --review-output work/managed-launcher-review-3
python tools/test_xnow_managed_launcher.py
```

The current local ARM ELF is work/managed-launcher-review-3/launcher.elf,50600
bytes versus44592 for the matching ordinary build, an observed6008-byte increase.
It is an external user-storage launcher candidate, not a system firmware image.
Readelf/nm checks require only original libc and exclude radio/controller crypto
imports. Selftest/catalog/check and managed marker classification execute under
ARM926/original libc. Contract tests cover legacy absence, valid binding, wrong
hash, truncated/prefix errors, symlink/hardlink refusal and legacy restoration.
FIFO creation is skipped explicitly because the workspace filesystem does not
support FIFO nodes; no FIFO runtime classification claim is made. No app/device
execution occurs in those ARM CLI tests.

A real host-process test invokes the actual bridge function, not just the pipe
primitive. Its normal case returns only after6.5-second simulated restore despite
UI SIGKILL; crash case keeps the foreground alive after owner exit until the PC
test deliberately cleans up its own process. All real RF/manager/APF effects are
mocked. Ordinary launcher regression and16 original app-process cases pass.
Reports:work/managed-launcher-review-3/contract-tests.json and
work/espnow-launcher-bridge/report.json. Build/source hashes bind the reviewed
artifacts. No SDK export, app install, radio reload or player update occurred.

## Next implementation boundary

### Full-owner application command boundary

The existing chat worker still consumes fixed32-byte mailbox packets and its
private96-byte chat commands. It cannot adopt the full radio merely by replacing
an image. xnow_owner_commands.c/.h adds a separate private, versioned binary
request boundary for ADD/MODIFY/DELETE/SEND/STOP. SEND carries up to1470 arbitrary
binary bytes, with single-peer or all-peer dispatch, without chat fragmentation.
Per-peer completions retain the initiating request token through the whole batch.
Receive returns native full metadata and binary bytes. No PMK/LMK is included in
replies; input buffers containing configured LMKs remain the caller's erasure
responsibility. Encrypted use requires the existing security adapter and already
provisioned durable PN scopes; it never falls back to plaintext.

The input header is16 bytes and the command body is at most1476 bytes. Exact
length, magic, token, reserved fields, opcode and flags are checked before effects.
An unavailable16-byte response buffer prevents mutation. STOP acknowledges only
a request to drain/restore, not successful restoration. Phase/lease revocation
refuses new data. xnow_owner_commands_control.c binds the provider and STOP to
the actual full controller accessor/stop functions, without a retained endpoint
pointer bypass. The binding now executes with the actual controller/endpoint/
backend in the combined IPC fixture below; original device actions are mocked.
Managed-owner process handoff, security provisioning and original platform
ownership remain required before this boundary can be installed in a device app.
It is not exported in SDKalpha4.

tools/test_xnow_owner_commands.py runs real command/endpoint/full-backend code
under host sanitizers and ARM926 with original Sony libc. Its synthetic radio
tests1470 binary snapshot/correlation/completion/RX, all-peer selection, refusal
after revocation/STOP, encrypted refusal, in-place replies, response backpressure
and malformed requests. It does not execute radio ARM code or the device driver;
the stronger secure-chain instruction tests remain separate. Report:
work/espnow-owner-command-tests/report.json. No device installation occurred.

### Full-owner pipe framing and combined cancellation

xnow_owner_stream.c/.h adds inherited nonblocking FIFO transport, independent
of the legacy fixed chat IPC. It duplicates descriptors CLOEXEC, verifies FIFO
access mode/device/inode on each step, and does not change caller flags. One
bounded command buffer and one bounded output buffer handle partial reads and
writes. Pending replies prevent another command from executing. Responses are
fixed16-byte XNA1 acknowledgments,32-byte XNT1 completions, or32+payload XNR1
receive frames. The private header documents layouts. All buffers are RAM-only;
no candidate, journal or system file is opened by this transport.

EOF/HUP, including HUP with unread commands, malformed/oversize framing, pipe
replacement and broken output wipe staged requests/responses and request STOP.
No transport error releases radio ownership or publishes restoration DONE. The
worker must ignore SIGPIPE and continue the actual controller/gate drain/restore
loop while its managed foreground remains held. Closing transport duplicates is
not permission to return from the owner. This is not standalone APF/USB proof.

tools/test_xnow_owner_stream.py uses real anonymous pipes under host sanitizers
and ARM926/original libc. Link wrappers limit real reads to3 bytes and writes
to5 bytes. Cases include1470-byte TX/RX, saturated output with queued commands,
partial key-bearing request disconnect/erasure, HUP-with-data, oversize header,
lost reader and reused-FD refusal without closing the replacement. ARM filesystem
queries use the existing Sony stat bridge and original fcntl symbol.
Report:work/espnow-owner-stream-tests/report.json.

tools/test_full_owner_ipc.py connects real pipe/command code through the actual
full-controller binding to real endpoint/full-backend code. After a1470-byte TX
is submitted, closing the command writer triggers actual controller STOP. While
completion is pending, manager/radio handles remain held and no unload job starts.
After modeled completion, original-action reload/reconnect reaches DONE and
peer/current-network memory is erased. Host sanitizers and ARM926/original libc
pass. Driver/probe/image-loader/stock-manager effects and radio memory are mocked;
no physical scheduling, APF deadlines, USB behavior or RF delivery is proved.
Report:work/espnow-full-owner-ipc/report.json. Managed process integration and
physical platform qualification remain pending; nothing was deployed.

### Managed full-owner runtime composition

xnow_owner_runtime.c/.h now composes the actual gate, full controller, command
binding, pipe stream and owner restoration notifier. Construction requires a
fresh controller before RF startup, the exact cooperative gate as its lease
provider, matching command-pipe identity, and a separate inherited restoration
pipe/cookie. A response-pipe alias is rejected even if it is a different FD for
the same FIFO. This constructor does not invent original APF/USB ownership;
the platform guard/storage callbacks still require independent qualification.

Each step handles gate stop/revocation and controller work before app commands.
Before first command, an explicit prepare callback attaches security/storage;
encrypted capability without that callback is refused before RF startup. No
default PN provisioning, key reset, system path or file write is supplied.
UI EOF requests controller stop. An in-flight send remains owned until backend
drain finishes; restoration continues even after command transport disappears.
Known authentication/replay/format rejects are counted without forwarding data.
Other backend failures request stop; uncertainty never fabricates completion.

Only after full_control_finished does the runtime invoke the required data-close
callback. That callback must close user-volume/journal FDs and move cwd off that
mount. Then stream/gate descriptions close, the matching restoration record is
written, and its writer closes. A cleanup/notification error latches uncertainty
without a successful DONE indication. The caller must retain its managed owner
and foreground on pending/uncertain. Callback success is a caller contract, not
proof obtained by scanning all process descriptors; actual worker construction
must supply and qualify those callbacks. SIGPIPE handling remains explicit.

tools/test_full_owner_runtime.py runs this composition with real anonymous pipes
and an actual cooperative abstract socket, real controller/endpoint/backend, and
mocked original driver/manager/loader effects plus synthetic radio words. Host
ASan/UBSan and ARM926/original libc cover in-flight1470-byte UI disconnect,
restore-before-cleanup/token, exactly32-byte DONE followed by EOF, peer/current
configuration erasure, denied security-less encrypted configuration, response
pipe alias refusal, and cleanup-failure retention without notification. Report:
work/espnow-full-owner-runtime/report.json. That ARM test uses a direct constructed
capability; real host managed-launcher adoption is covered separately below.
This component is not exported, installed or device-tested.

### Actual launcher/UI/full-owner process test

tools/test_full_owner_process.py now exercises the actual opt-in launcher bridge,
managed wrapper, unchanged app_process grace, UI fork/exec, inherited capability,
detached full owner, real command/event FIFOs and the full owner runtime. Unlike
the earlier process fixture with mocked endpoint init/stop, this fixture uses the
real full endpoint/backend and submits1470 binary bytes through UI commands before
the observer requests UI stop. It confirms the radio send is in flight before
triggering that observer. Original stock/driver/loader/APF/USB/RF effects remain
mocked and the radio word endpoint remains synthetic.

Normal case: the UI does not finish its original termination grace, so app_process
reaps SIGKILL status9. Its owner remains alive, waits6.5 seconds of injected
completion delay, then the runtime drains/restores, closes user-data references,
notifies and closes its inherited writer. Only then does the launcher bridge
return the UI status. The observed fixture duration was about6.6 seconds; this
is an injected delay, not hardware latency or throughput evidence.

Crash case: the owner intentionally exits76 before injecting completion or
restoring. The bridge diagnoses missing restoration confirmation and remains
alive; no owner-restored marker is written. The PC supervisor then deliberately
kills only its own remaining fixture descendants for cleanup. PC-only subreaper
support is confined to that supervisor, not the runtime, UI or launcher.
Report:work/espnow-full-owner-process/report.json. These are actual host processes,
not ARM process/kernel or original APF timeout/USB qualification. No radio image,
app package or SDK export was deployed by this test.

### Secure runtime with persistent packet numbers

The owner now checks that an encrypted-capable prepare callback actually attaches
all crypto operations and workspace before marking preparation complete. A callback
returning success without an adapter is rejected and restoration is requested.
This checks interface presence; it does not attest a third-party callback's crypto
correctness or storage destination. The qualified native security adapter remains
the intended implementation.

tools/test_full_owner_secure.py connects actual runtime/gate/controller/IPC to
the native endpoint security and POSIX PN-file adapter. Its prepare callback loads
existing TX/RX scopes and attaches the adapter before app commands; provisioning
is a separate explicit PC fixture setup for fixed fresh test keys. It never creates
zero-counter records in prepare. File writes use dedicated preopened work-directory
FDs with the gate storage callback; the underlying ownership guard is still a PC
fixture, not original user-volume/USB proof.

Host ASan/UBSan and ARM926/original libc execute two complete owner lifecycles on
the same records. TX PN is1 then1025 after workspace/FD cleanup and reinitialization;
unused reserved counters are skipped. Each1470-byte protected TX is independently
decrypted/authenticated with PyCryptodome AES-CCM and compared with a separately
constructed complete v2 body. Host/ARM frames match for these deterministic inputs;
this is not a general toolchain reproducibility claim.

The same runtime receives encrypted1470-byte data, rejects modified MIC without
consuming that PN, then accepts the corrected frame. Replay is discarded both
within one lifecycle and after reinitialization with persisted RX state. Missing
records and inert prepare callbacks stop before data submission; missing-directory
checks confirm no .dat files are created. Teardown verifies workspace erasure,
journal FD closure, original-action restoration and notification EOF.
Report:work/espnow-full-owner-secure/report.json. This uses actual file/crypto/
runtime code but synthetic radio words and mocked stock actions; no Espressif
encrypted over-air interoperability, power-loss FAT behavior or malicious storage
rollback protection is established. No player was accessed or written.

SDKalpha.6/XNOWdev.11 fixes a reproduced error-domain collision in this path.
With security attached, a malformed plaintext body from an unregistered sender
returned raw wire-format-1 (or wire-version-4), colliding with backend IO and
uncertainty. The owner stopped despite an unfaulted backend. The adapter now
normalizes plaintext decode failures to SECURITY_FORMAT. Actual full-action
transport failures are returned before that decoder and retain IO semantics.
The runtime regression injects malformed IE/type and unsupported version, then
valid unknown plaintext followed by encrypted1470 traffic; it also injects an
actual read failure and verifies stop/restoration. Host sanitizers and original-
libc ARM pass. Temporary debug instrumentation was removed; no radio code changed.

### Standard Espressif peer candidate

runtime/platform/espnow/standard-peer is a separate C/ESP-IDF5.5.1 bench for
the original ESP32-S3 Cardputer. It uses unmodified Espressif send/receive and
peer/PMK APIs, binary hex commands up to1470 bytes, and bounded callback queues.
There is no XNOW/chat envelope, automatic traffic or router association. Keys
and peers are RAM-only; Wi-Fi NVS is disabled. Reboot requires fresh test keys:
this candidate does not claim durable anti-replay across ESP restarts.

It does not force the transmitted wire version. A separate v1 peer or captured
v1 input remains necessary to qualify v1 reception. The existing physically
tested chat peer remains unchanged. Building this bench is not authorization
to flash it or reload the X1060 radio. See its local README for commands and
the binary-length/encryption acceptance matrix. Physical interoperability of
this candidate, including encrypted admission and1470-byte packets, is pending.

Bench0.1.1 fixes a reproduced diagnostic defect: a saturated eight-entry RX
queue discarded TX completion while releasing the busy flag. Completion now
has an independent protected slot and the command task releases busy only when
consuming it. The real bench translation unit executes under host ASan/UBSan
with mocked IDF/FreeRTOS calls, covering full RX plus completion, binary1470,
oversize and malformed input, immediate failure, encrypted-peer setup and
scratch erasure. Control characters invalidate a whole line through newline;
oversize lines recover at the next newline. Serial reads are batched64 bytes
and RX draining is bounded to eight records per loop. This is test-tool evidence,
not radio/CCMP acceptance. Report:work/espnow-standard-peer-tests/report.json.

The combined radio builder now has offline evidence. The exact-image bounded adapter has offline evidence; qualify its
full owner and original-action sequencing now have offline policy evidence;
qualify actual exclusive ownership, image load/restore and USB/sleep behavior. Connect public SDK and test apps
without bypassing mount/USB ownership or restoration. Physical v1/v2, multi-peer,
Protected admission, successful/failed MAC completion and stock restoration must
be tested with unchanged Espressif APIs. The original kernel/driver scheduling,
real FAT/power loss, sleep and USB transitions remain distinct from QEMU/Unicorn.
Key provisioning, secure persistence and local PMK configuration must not reset
existing LMK counters. No system partition or NVP edits are part of this work.
