# Managed system services: lifecycle design

Status: partially implemented contract for Japanese X1050/X1060 JP1.11.
SDK0.2.0-alpha.9 development exports the client-only player-managed-client module.
The service core, original manager integration and hardware acceptance remain
incomplete. Frozen alpha.8 bundles and installed applications are unchanged.
No firmware activation or device permission is implied.

The first private implementation lives in runtime/platform/services/session.c
and session.h. It covers four fixed session slots, trusted-provider grants,
generation/serial handles, admission epochs, revoke-before-release, bounded
close steps and retained fault state. It is owner-thread-only and requires fresh
zeroed manager storage; no thread enforcement or authentication is supplied.
Closed-slot reuse invalidates ordinary handle reads. A separate close query
retains four successful close receipts after slot reuse; eviction or restart
returns STALE, never inferred restoration. Faults remain in their original slots.
Receipts are RAM-only and are not durable. The adjacent request.c/request.h add a private per-session
eight-record ledger with192-byte exact payload comparison, monotonically
increasing client IDs, duplicate/conflict refusal, explicit running/completion,
queued cancellation and epoch validation before execution. Evicted IDs below
the high-water mark return UNKNOWN, never new admission. Running cancellation
returns PENDING and does not undo effects. Results use domain codes, not inferred
playback state. Ledger lifetime must cover its session; no crash durability or
authority is supplied. Task integration and original-manager adoption remain incomplete.
This is deliberately not exported by sdk/services.json.
tools/fixtures/service_session.c exercises the core under host ASan/UBSan;
the production core also compiles for ARMv5TE. Neither is hardware acceptance.
tools/fixtures/service_request.c separately checks request replay/conflict,
eviction, cancellation and revoked dispatch under host sanitizers.
Run tools/test_service_lifecycle.py for the maintained fixtures under host sanitizers
and ARM926 QEMU user mode with the pinned original Sony loader/libc. It also
compiles ARM objects and records source, binary and library hashes. Session,
request, event and managed-player tests execute on ARM; native playback remains
modeled and Sony's kernel is not executed.

runtime/platform/player/managed.c is the first private synchronous adapter. It
borrows an existing player backend and checks separate READ/CONTROL/BROWSE grants
before forwarding operations. Simple control requests use explicit canonical
eight-byte operation/value encoding and the session ledger; retained duplicates
return their original result, including UNCERTAIN, without re-execution. Expired
request IDs remain uncertain. PLAY_ITEM is now delegated when advertised by the
backend: canonical payloads retain the item/container IDs and full64-bit expected
revision, ignoring bytes after each ID's NUL. Malformed/non-ASCII/empty item IDs
are rejected before admission. Repeated IDs retain BUSY as well as terminal
results; no duplicate automatically advances validation. Where the backend
documents pre-admission command polling, the client must make a new explicit
command with a new request ID. ACCEPTED/UNCERTAIN never trigger automatic
resubmission, and admission does not fabricate PLAYING. Closing this adapter revokes its session
but does not close the borrowed original player. It owns no background readers;
future per-session asynchronous resources require real drain callbacks before
this release path can be reused. Authentication and original physical ownership
remain external requirements; the adapter is used by the explicit managed
analysis profile, not an installed service.
The service_player fixture checks the real adapter/client/core against a modeled
backend, including no replay and no original-player closure.
`test_source_service.py --managed` connects the real managed request ledger and
client core to production source_service/source_intent. When validation becomes
ready, repeating the earlier BUSY request ID still performs no read/submission;
a new explicit ID admits one submission using the same pending intent generation.
Accepted IDs are retained, full64-bit revision survives, revoked/closed sessions
cannot advance a request, and another session can explicitly replace the target.
Source loss does not submit. Shared backend close waits for validation drain.
Host sanitizers and original-libc ARM execution pass; worker readiness/drain,
GUI and native submission remain models. This does not qualify the actual
stop/install/play transaction or original-owner authority.
`test_source_intent_async.py --managed` extends this through the real validation
worker and metadata_async implementation. A revoked client's blocked read is
replaced by another session's explicit target; releasing the old read does not
submit it. A retained request ID does not advance validation. New explicit owner
calls reach one modeled UNCERTAIN submission only after native-client counts
balance; replay does not resubmit. Backend close remains BUSY while a later read
is blocked, then drains/destroys after release. Host sanitizers and original
Sony LinuxThreads/libc in the generic ARM guest pass. Fixture counters use
mutex-backed operations for the old ARM ABI, not modern atomic-helper assumptions.
Native audio validation, GUI view and source submission remain models; the full
original hardware transaction and manager authority are still unqualified.
Snapshot and browse results are staged internally and committed only after
rechecking the session grant/epoch. Revocation occurring inside a backend callback
therefore discards the read and preserves caller outputs. The dispatch fixture
explicitly revokes during a successful media read and checks refusal/atomicity.
The adapter's poll method now owns a separate existing player-client observer
per session, so one client's reads cannot consume another client's changes.
Failed observations preserve outputs and reset only that observer's history;
recovery forces AVAILABLE/full refresh. This is still polling, not the proposed
sequence-numbered event queue. Each adapter includes the existing client's fixed
scratch buffers, so allocate fresh zeroed adapters in static/heap storage and
account for their memory before choosing a simultaneous-session limit. Closing
one observer does not close the backend or another observer. Two-client tests
cover independent changes, failure/recovery and continued reads after peer close.

services/events.c adds a separate private16-record sequence ring with bounded,
non-destructive page reads. Each consumer supplies its own cursor; overflow,
future cursors or provider-generation mismatch require resynchronization and
leave outputs unchanged. Sequence exhaustion refuses publication rather than
wrapping. The generic ring does not capture snapshots, authenticate consumers
or automatically publish lifecycle changes. The private managed player publishes
sampled changes and one unavailable event per failure episode. Its owner must
call refresh periodically; snapshot_sync captures a fresh snapshot and its
sequence on that owner, establishing the slow consumer's new cursor. Publication
failure refuses subsequent observations instead of silently losing integrity.
This is not an installed notification service. Event kind/value are
provider-defined scalar observations, never a replacement for request outcomes.

player/managed_rpc.c dispatches the existing explicit player frames through one
pre-authorized managed adapter. Snapshot/browse check session grants; command
serials identify deduplicated intents. HELLO advertises only granted control
operations, including PLAY_ITEM only when the backend advertises it. Serial numbers
must not wrap/restart within that session; reconnecting transports must retain
the session's request numbering or acquire a genuinely new authorized session.
The dispatcher does not open a listener, grant authority or accept a client-
supplied session identity. Its framing fixture executes under host sanitizers
and original-libc ARM, including media roundtrip and revoked-read refusal.
Connection authority/original-manager binding remains incomplete. A client-only
managed SDK module is available; the old public RPC endpoint does not gain these semantics.
managed_control.c defines separate fixed40-byte XLC1 local requests for session
status, event pages and explicit close/receipt queries. XLR1 responses explicitly
encode scalars and have bounded payloads. Generation, reserved fields and output
capacity are checked before effects; no grants or native pointers come from the
client. Repeated close queries read the retained receipt. The channel recognizes
these frames alongside unchanged legacy player frames. Control correlation IDs
are not playback intent IDs. Status/close results use session codes; event results
use event codes. SNAPSHOT_SYNC4 now returns the sequence plus a nested complete
legacy snapshot response (nested serial1, outer64-bit correlation authoritative).
It captures both on the same owner through snapshot_sync, requires1024-byte
response capacity and caller-owned response scratch, and reuses the channel's
scratch instead of placing a full media-page union on the original thread stack.
The real inherited-channel fixture decodes the snapshot and sequence before
explicit close. Private managed_codec.c now builds control requests and decodes
status/event responses with exact lengths, correlation, generation, reserved
fields and event sequence checks. Invalid data preserves caller outputs. This
codec has host-sanitizer and original-libc ARM checks, including corrupt sequence
refusal. Its sync decoder additionally checks outer correlation, nested snapshot
kind/serial/result and the shared original player snapshot validity/normalization
rules before committing snapshot and sequence together. Large response scratch
is caller-owned. Tests reject unknown valid bits and wrong correlations without
changing outputs. The alpha.9 client module exports the typed client and its
transport dependencies; the server core remains internal.

managed_remote.c now supplies a private synchronous worker-side exchange on an
already-authorized inherited stream. It validates requests before sending,
checks response lengths/correlations and rejects overlap with response scratch.
One caller-supplied monotonic-clock deadline covers send/receive, with bounded
poll intervals and cancellation checks. Transport failure closes the connection;
sent playback commands return UNCERTAIN, never reconnect/replay. Detach closes
only the client descriptor and does not claim server release. The channel fixture
uses this actual transport for controls, media, sync and explicit close, then
tests missing replies and refusal to reuse a failed connection. Its clock is a
modeled monotonic counter; production must bind the verified stock clock adapter.
The transport is a client-module dependency, caller-serialized and uninstalled.
Trusted manager descriptor delivery remains outstanding.

managed_client.c now provides private typed wrappers on that transport: bind a
fresh player/client to a manager-supplied descriptor and generation, negotiate
granted commands through HELLO, then use the existing player control/snapshot/
browse API. Separate status/sync/events/end methods handle managed lifecycle
responses. end confirms the session receipt; xw_player_close only detaches the
local object. Binding never starts a service or requests additional grants.
Request serial/correlation exhaustion refuses further work rather than wrapping.
The channel fixture's separate client now uses these wrappers for control,
media, synchronization, events and explicit end, under host/original-libc ARM
execution. The bind_stock variant now uses managed_clock.c with the verified
two-word stock monotonic-clock bridge and original librt. The main typed-client
fixture uses this path, including a silent-peer HELLO timeout and failed-bind
cleanup. The raw transport's separate failure test retains its modeled clock.
Host clock fixtures and original ARM libc/librt execution are distinct evidence;
Sony kernel sleep/time behavior remains unqualified. Descriptor authority
delivery and original lifecycle/hardware integration remain outstanding.
Client headers now depend on shared scalar types and wire constants rather than
the server session manager, request ledger or native managed-player object.
services/types.h and player/managed_wire.h define those common contracts. Client,
remote and codec entry points have C++ C-linkage guards. The lifecycle test
compiles a separate C++ consumer, checks unmangled linkage and preprocesses the
client header to reject accidental server-object exposure. This prepares an SDK
source boundary. Alpha.9 exports only the client module; no installed application
is changed. A public-only external consumer builds and executes under original
libc ARM926 and passes C++ syntax checks; the linked source set excludes native
hooks, server/session code and startup installation.
The service_channel fixture additionally exercises real inherited AF_UNIX
socketpair/fork client-server traffic, framed state/media replies, deduplicated
control and session release on EOF while preserving the borrowed backend.
It runs under host sanitizers and original-libc ARM926 user emulation. Authority
is provided only by the fixture's parent-created descriptor pair; no production
listener, manager capability transfer or peer credential policy is implemented.
The client fixture uses blocking bounded frames with an outer process deadline.
Its server now uses private player/managed_channel.c: one trusted transferred
stream FD, nonblocking reads/writes, at most two reads/one dispatch/2048-byte
send per owner tick and a3000ms deadline after a request starts. Partial-frame
timeout, disconnect and clock rollback initiate session release; no original
backend close is performed. A pre-dispatch EOF check refuses abandoned commands.
The channel owns its FD after successful open, and close completion is distinct
from a transport error. The fixture checks partial-frame timeout without control
execution. No idle disconnect timeout, manager integration or peer authentication
is implied. The callback provider must still be bounded; transport budgets cannot
make a blocking native provider safe. This code is not installed or exported.

## Scope and ownership

Authorization delivery remains a distinct integration task. The pinned original
sysmgrd/appproxy direct-import inventory (tools/check_manager_ipc_imports.py)
does not show sendmsg/recvmsg or socketpair. This does not exclude indirect
library implementations and is not proof that descriptor delivery is impossible.
The original child-path instruction check confirms no close/fcntl in the tested
successful post-fork credential/exec segment, not the entire launch sequence.
Consequently a boot-created inheritable FD is not an app-specific capability;
do not leak it into every manager child. A future descriptor-delivery adapter
must target the approved session/launch and close all unintended copies, with
ABI-checked transfer and manager/lifetime evidence before installation.

services/descriptor.c now implements a private nonblocking SCM_RIGHTS transfer
over an already-trusted connected AF_UNIX datagram channel. It accepts exactly
one connected local stream with generation/session/grants metadata, checks
reserved bytes and truncation, closes received extras on rejection, and sets
CLOEXEC before publishing outputs. Metadata is not authentication. Sender copies
remain caller-owned and must be closed according to the broker's acknowledged
handoff; send success alone is not client adoption or session-release evidence.
ARM message/iovec/control sizes are compile-time checked against the32-bit ABI,
and original sendmsg/recvmsg/fcntl symbols are explicitly bound. The descriptor
fixture runs under host sanitizers and original-libc ARM user emulation, checking
data flow, empty-channel refusal, malformed metadata and two-FD rejection without
descriptor-count growth. It does not qualify Sony's kernel, authority selection
or original manager integration. Old-kernel CLOEXEC adoption is not atomic;
the owning process must serialize fork/exec around receipt before using this path.

player/session_offer.c composes session grant, a dedicated stream pair, managed
adapter/channel and descriptor offer for one approved launch. Trusted callers
still supply the authority and private delivery channel; this does not authorize
an app by its requested mask. Local client-FD copy closes after successful send;
queued delivery copies remain the trusted channel owner's cleanup responsibility.
The stream accepts only HELLO as its first request and enforces a fixed3000ms
adoption deadline from creation, not extended by late partial bytes. Failure to
deliver rolls back the session; missing handshake closes it without executing
controls. The offer fixture checks denial, early-command refusal, no receiver,
partial-handshake timeout and delivery failure rollback under host/original-libc
ARM. No original manager hook or installed session broker is implied.

player/managed_host.c now composes these pieces for a trusted original-owner
caller. It accepts caller-owned fresh offer workspaces (up to four), a qualified
SDK broker, a new generation and supported grants. The trusted caller still
supplies authorization and a private descriptor-delivery channel. The host has
no listener, app lookup, authentication or original-manager registration hook.
It samples READ-authorized sessions only after HELLO adoption, pumps independent
bounded channels, and records client errors without closing unrelated clients.
The caller continues to tick the broker separately on its qualified owner.

Closed workspaces are reusable only after locally verified channel/player
release and a CLOSED session result. The host records that proof before clearing
the workspace; a new offer receives a new manager serial, never an old request
ledger/identity. Fault/unknown release is quarantined rather than treated as
capacity. Host stop first disables admission, then uses the production service
drain to close sessions and broker; only complete drain reaches STOPPED. The
original backend remains borrowed. No restart or native lifetime retention is
implied. The module is not selected by an installed host or public SDK module.

The host lifecycle fixture covers separate READ/CONTROL/BROWSE grants, no
sampling before adoption, sampled notifications, control refusal, browse access,
independent client close, silent-client expiry, repeated workspace reuse beyond
receipt-ring capacity, and complete stop without closing the original backend.
Host sanitizers and original-libc ARM execution pass. Backend observations,
browsing, control and broker-close effects are fixture callbacks; this does not
qualify native media, original authority or hardware teardown.
The host's prepare operation now owns the deferred-prepare bridge as well.
It stops admission immediately, and the same host tick closes sessions, drains
the broker and invokes a qualified continuation once. Repeated prepare requests
while STOPPING remain BUSY; no additional offers are admitted. Continuation
failure/context loss reaches FAULT rather than STOPPED. Ordinary stop retains
its separate no-continuation behavior; callers must not manipulate the embedded
drain or prepare objects independently.

The blocked-reader guest fixture now establishes its session through actual
descriptor delivery and HELLO before starting the production broker readers.
It routes prepare through managed_host, rejects another thread's tick, holds
continuation while two modeled native handles are live, and verifies one-shot
continuation only after release. The original-manager SDK-drain profile runs
this same function inside the C Home client after notice4; the app round trip
and Home restart pass. Native media/continuation remain models and SpiderApp
event dispatch is not installed. These are combined SDK/manager tests, not
hardware qualification or authority to use this mechanism for suspend/USB.
`test_sdk_managed_channel.py --managed-host` now builds a consumer using only
public SDK headers/modules and runs its ARM binary with original Sony loader/
libraries against a separate sanitized managed_host server. A trusted fixture
shim receives the offered descriptor and explicitly preserves its approved FD
across exec. The client tests NEXT/PAUSE, all four media views, snapshot sync,
sampled state-change events, session status and confirmed end.
The modeled snapshot also checks track ID, title, UTF-8 artist, album, playback
position/duration and volume fields across the public ABI and serialized channel.
These are synthetic values, not evidence of live original ID3 extraction.
The host closes its broker while preserving the borrowed original backend. Media/state/backend
effects are deterministic callbacks; neither original manager policy nor native
playback/hardware is executed.
The shim must clear CLOEXEC on the designated child descriptor after dup2,
including when source and destination are equal: dup2(fd,fd) leaves CLOEXEC set.
This does not justify clearing flags on arbitrary inherited descriptors or
changing the SDK's CLOEXEC-on-receipt rule.

Expose controlled access to system capabilities, not ownership of Sony hardware.
The system-side provider owns acquisition, native-thread dispatch, revocation,
draining and restoration. An external application owns a client connection and
receives only the capabilities explicitly granted for its session. A library
function succeeding is not evidence of APF, USB, mount or radio ownership.

Use the original manager and verified native callbacks wherever possible. Do not
replace original kernel/initrd, invent power callbacks or bypass foreground
handoff. Service placement (SpiderApp module versus managed resident process)
remains an implementation decision requiring original-runtime evidence. The
contract must not depend on either placement.

Pure codecs, hashes and rendering helpers need no managed session. Hardware,
mutable shared state, native-player access and asynchronous work do. A session
is a cooperative ownership boundary, not a sandbox: existing root applications
cannot be made untrusted-code-safe by a C API or a claimed app ID.

## Three distinct objects

1. Client connection: transient IPC transport. Disconnect does not prove cleanup.
2. Session: granted capabilities, provider generation, lifetime policy and bounded
   outstanding requests. Ordinary sessions end on client loss or revocation.
3. Background task: an explicitly approved system-owned operation. Its lifetime
   is independent of the settings page. Closing the page detaches its connection;
   stopping the task requires a separate operation and completion observation.

Background task creation is denied unless the provider can demonstrate original
lifecycle integration. Initially allow only explicit user-started, boot-scoped
tasks: no automatic boot start, no persisted enabled flag, no application-defined
infinite lifetime. Reopening a page attaches to the existing task. Duplicate
start returns the same authorized task or CONFLICT; it never starts a second RF
owner. Only one provider owns the wireless mode at a time. Sharing receive data
does not grant another session permission to retune or restore the radio.

Task management requires an authorized control capability. Task identity alone
does not authorize stopping, inspecting private data or attaching another client.
Use an inherited manager capability or another verified local authority path;
do not trust self-reported app names/PIDs as authentication.

## States and results

Session states: OPENING, ACTIVE, REVOKING, CLOSING, CLOSED, FAULT.
Task states: STARTING, RUNNING, SUSPENDING, SUSPENDED, STOPPING, STOPPED, FAULT.
Connection state is separate; a connected client may have no usable capability.
Only ACTIVE/RUNNING permits operations appropriate to that capability. Suspended
does not mean hardware is still receiving or that remote wake works.

Every transition has a reason: CLIENT_CLOSE, CLIENT_LOST, HOME, USB, SLEEP,
PROVIDER_RESTART, SOURCE_LOST, USER_STOP or INTERNAL_ERROR. Provider adapters
derive these from verified original paths; the public enum is not proof that
all those paths are already connected.

Common results: OK, PENDING, BUSY, INVALID, UNSUPPORTED, DENIED, UNAVAILABLE,
STALE, CLOSED, CONFLICT, IO, UNCERTAIN. PENDING includes a request identifier.
BUSY means not admitted, with no queued side effect. UNCERTAIN means an admitted
effect or its final outcome cannot be established. A deadline expiring does not
mean cancellation or restoration succeeded. Never silently replay commands.

Retain domain results where meaningful, including player ACCEPTED: admission
is not audible playback completion. Avoid converting all native failures into a
generic "off" state. FAULT exposes resource ownership/restoration uncertainty.

## Proposed API surface

The names below specify responsibilities, not exported ABI declarations:

| Operation | Responsibility |
| --- | --- |
| service_describe | API range, supported capabilities, sharing/lifetime policies and limits; no hardware acquisition |
| session_open | Explicitly request capabilities and lifetime; return grant or pending request |
| session_snapshot | Current state, provider generation, grants, reason and sequence |
| session_poll_events | Bounded batch of ordered changes after a sequence |
| request_query | Observe admission/progress/terminal outcome by request ID |
| request_cancel | Ask to cancel pending work; already executed effects are not undone |
| session_close | Stop admission and begin release; repeat safely while closing |
| session_close_query | Confirm closed or report pending/fault; not just socket closure |
| task_start / task_attach | Explicit creation or authorized attachment to a background task |
| task_stop / task_snapshot | Stop and observe task lifecycle independently of the page |
| connection_detach | Release client resources without implicitly stopping an approved task |

Use fixed-width scalars, versioned size-tagged public structures, opaque handles
and bounded caller-owned output buffers with C/C++ linkage. No native pointers,
pthread layouts or fixed SpiderApp addresses cross the managed public boundary.
Actual limits and memory sizes must be selected and measured before freezing ABI.
Reject unsupported versions, capabilities and policies explicitly. Existing
low-level APIs remain experimental; do not relabel them managed services.

Domain calls take a valid session plus caller request identity when they can
have side effects. IDs consist of provider generation, session and request scope;
never reuse an old generation after provider restart. Old handles/results return
STALE. Reconnecting does not automatically renew a grant or replay an intent.

Exactly-once execution across crashes is not promised. Within a live generation,
retain bounded request outcomes and reject duplicate IDs with different payloads.
If an outcome has expired, return UNKNOWN/UNCERTAIN as appropriate rather than
executing the old ID again. A new request ID denotes a new user intent.

## Closing, revocation and failure

The private session manager now provides quiesce/drained/resume. Quiesce first
closes admission and revokes every active slot on the owner, preserving the first
reason/epoch across repeated calls. Drained refuses while admission is open and
reports pending/fault until every session slot is empty/closed. Resume requires
that condition and never revives old handles or resets counters. This is only
session-level accounting: borrowed backend workers and global native resources
still need their own verified close/drain. A trusted provider must revalidate
hardware before calling resume. No original USB/sleep/command hook calls these
methods yet. The quiesce fixture checks two-session revocation, denied admission,
partial close, resumed fresh identity and a fault that prevents reopening.

player/service_drain.c now coordinates quiesced sessions/offers before closing
the SDK-owned player broker. Broker close may remain BUSY while shared readers
and queue/selection adapters drain; DONE is published only after broker closure
and verification that the borrowed original player remains initialized. Terminal
errors latch FAULT without retrying or reporting completion. Unknown live
sessions keep the manager pending. The drain fixture uses a modeled broker close
with multiple pending steps and a terminal failure; existing native-worker tests
remain separate. No original pending token, cleanup postponement hook or physical
ownership is installed by this coordinator. Its offers array must remain stable
and cover the sessions it owns; all entry points require the original owner.

tools/test_player_service_drain.py now combines the production broker, managed
adapter/session and drain coordinator with two actual blocked reader threads.
The fixture holds metadata and catalog reads behind a condition gate: sessions
can close while both modeled Moma handles remain live, but service drain stays
BUSY. After the gate opens, workers close their handles and exit; only then can
the broker close and drain reach DONE, with the original player still bound.
Host ASan/UBSan and a generic ARM Linux guest using original Sony LinuxThreads/
libc execute this combined test. Native Moma IO and original playback remain
models; the original pending-token handshake, library teardown and physical
USB/sleep path are not executed. No timing-independent native drain guarantee
is inferred from releasing the fixture's gate.

player/drain_completion.c adds a private one-shot completion bridge. A trusted
platform must first register a qualified native token and provide token/epoch
validation plus completion callbacks. The bridge checks registration before
drain and again after it, then latches CALLING before notification. Reentrant
notification cannot invoke completion twice; an uncertain callback result
latches FAULT and is not retried. It does not invent, allocate or install an
original token/hook. The core fixture checks uncertain-notification refusal
on later steps. Original native registration/completion effects remain models;
the current blocked-worker guest fixture exercises the deferred-prepare
alternative below rather than supplying a modeled native pending token.

player/deferred_prepare.c is a private candidate for postponement before native
preparation. It starts service drain, checks a trusted context/epoch before and
after drain, and invokes a supplied original-prepare continuation exactly once.
It records the calling thread and refuses steps from another thread. Reentry,
repeated begin and repeated completion cannot forward a second continuation.
Context loss or drain failure latches FAULT; an uncertain continuation result is
not retried. No original caller stack pointer, tracker insertion or native token
is stored. The host must still establish original-owner authority, stable native
context lifetime, a safe event deferral point, and any manager timeout contract.
The explicit managed analysis profile selects it; no device installation is implied.

The blocked-worker test now routes actual service drain through this candidate:
two held reader threads prevent continuation, and balanced handle release plus
broker closure permits it once. Host sanitizers and original LinuxThreads/libc
ARM execution pass; the continuation and native context validity remain models.
Core cases also cover context loss before admission, before drain and after
drain, plus uncertain continuation without retry. This does not qualify delaying
USB/suspend, native event ordering or manager acknowledgment.

On close/revoke the provider must:

1. Atomically stop admission for affected capabilities and advance their epoch.
2. Cancel queued work and discard late read results from prior epochs.
3. Drain or account for operations already executing on native owner threads.
4. Release native handles and user-volume descriptors; leave user-volume cwd.
5. Restore the original resource configuration where acquisition changed it.
6. Publish terminal state only after these conditions are established.

Bounded steps may return PENDING. No mutex is held while waiting on native IO,
another service or a client callback. Client crashes must not require cooperation
to initiate cleanup. A provider crash cannot issue its own completion; the
supervisor reports loss/uncertainty and follows verified recovery rules. No timed
kill followed by fabricated CLOSED, DONE or restored ownership is allowed.

Distinguish a closed client session from the global resource being restored: an
approved task or another authorized session may legitimately retain a resource.
Close completion reports the scope released and remaining task ownership.
Bounded terminal receipts belong to the manager; IPC closure alone is not a
receipt. Manager restart invalidates receipts from its prior generation.

## Original lifecycle integration

The original-manager system probe supports `--home-switch-mode 0` and
`--home-switch-mode 1` with `--live-manager-fixture`.
Mode0 exercises deactivation and reactivation of the same C Home client around
launcher/graphics. Mode1 receives quit notification4, exits that C client, runs
the same external test apps, then registers a fresh Home process on return;
the fixture verifies a different PID and that the prior PID no longer exists.
Both use original sysmgrd/appproxy, actual fork/exec/wait and original libc IPC
in an isolated ARM guest, with virtual devices/RAM state. These process-lifecycle
results complement the physical Terminal snapshot but do not qualify actual
SpiderApp playback, inactive-GUI control, Moma lifetime, display or sleep/USB.
Keep ordinary mode1 resource-handoff profiles unchanged; any companion mode0
profile needs separate qualification and must not be enabled for all apps.

The maintained `check_gui_command6.py --consume --complete --ack` replay
additionally reaches a supplied Main context's mode2/state2 after native-produced
41000a and an accepted modeled APF acknowledgement; the APF client becomes
inactive1. This is the Main state machine (descriptor0x3ef680), whereas
stock_gui.c binds the Audio state machine (descriptor0x3f11d8 through0x6831dc).
Equal numeric mode/state pairs are not equivalent evidence: Main2/2 does not
establish that the SDK's Audio actor remains available after handoff.
However the replay supplies the initial Main3/4 context and mocks transition,
cleanup and transport helpers. It does not bind that context to the live SDK
actor, execute a post-handoff playback command, or prove that commands cannot
reacquire display resources. A full companion-control integration remains open.

The original-manager guest probe accepts `--home-switch-mode 1` with
`--home-quit-delay-ms 1500` to delay the C Home fixture's actual exit after notice4.
Using unchanged sysmgrd/appproxy and original libraries, the measured guest wait
was1504ms; delay completion preceded launcher start, and the original manager
later relaunched Home with a different PID and completed return. The fixture
uses an explicit original two-word gettimeofday binding to check elapsed time;
this is not a monotonic-clock or real-hardware timing qualification. It proves
that one tested ordinary app switch tolerates that delay, not a universal manager
timeout limit or permission to defer USB/suspend. The C client does not execute
SpiderApp or SDK drain in this probe. Default behavior remains zero delay.
The separate `--home-sdk-drain-fixture` profile now runs the production SDK
deferred/drain/broker/session code and two actual blocked reader threads inside
the C Home client when original manager notice4 arrives. Drain completes before
the client exits and before launcher start; original manager/proxy then perform
the external-app round trip and relaunch Home with a different PID. The guest
uses original Sony LinuxThreads/libc. Native media objects, original-prepare
continuation and hardware remain fixture models: SpiderApp is not this C client.
This combines manager process lifecycle with real SDK worker drain, but does not
qualify an installed SpiderApp hook or USB/sleep event handling. Source hashes
cover linked drain sources, nested fixtures and platform/service headers.

The original-controller replay in tools/test_stock_gui_host.py now captures
registers, controller/options and caller stack at the original Audio handler's
lower calls. Replaying these prepared inputs directly at27d6a0 (play/pause),
27dacc (next), and27db98 (previous) with the Audio UI actor pointer cleared
returns0 and produces an admission ticket in the modeled controller queue,
without traversing the tracked UI entry/exit callbacks. Uninitialized play
options were rejected as0x102 before admission; register values alone are not
a callable ABI. Tests now reconstruct options in fresh memory rather than
reusing the UI globals or stack: play[0,1], pause[1,1], previous[1,1000,1,1],
and nextNULL. Native previous code copies16 bytes, play/pause8 bytes, and
27c434 stores the transition pair inside the owned request. The replay verifies
the copied payload and internal pointer, then changes the input buffer without
changing queued fields. A separate output ticket receives7 while the UI ticket
remains6; no UI ticket is borrowed. This establishes copy behavior only, not a
complete semantic interpretation of every field. `--direct-only` runs the targeted
subset and writes report-direct.json with complete_matrix_run=false.
This is a candidate engine-control path, not a new SDK binding: allocator,
mutex/ticket/wakeup and other boundaries remain modeled, and controller readiness,
lifetime, real post-handoff execution and UI/resource side effects need separate
qualification. No guard is removed and current SDK control behavior is unchanged.

player/stock_engine_control.c is now a separate private experimental binding for
stable loaded-track controls. It checks the pinned engine span, original-owner
affinity, fresh CtrlInfo, unchanged controller handle and its service/session
identity, track identity, zero error
and zero substate before dispatch. Play/pause use independent two-word options;
previous uses four words; each call owns its output ticket and never modifies UI
options/tickets. Already-observed desired state is admitted without toggling.
Any attempted native request with uncertain admission is not retried. Bind owns
an ordinary stock_info reader; the host must still protect native lifetime.
The wrapper address can survive session replacement: a changed service/session
after reading refuses dispatch, while a change after submission returns UNCERTAIN
without retry. ARM fixtures cover both read-time identities and submission-time
session replacement. These checks detect observed replacement; they are not a
native lifetime lock and do not establish safety against arbitrary concurrent
teardown.
tools/test_stock_engine_control.py executes the real ARM binding, image hash and
original request construction with no Audio UI actor, including refusal and
allocation-failure cases. CtrlInfo values, allocation, ticket/mutex/wakeup and
other boundaries are modeled; it does not qualify stopped/unloaded playback,
real engine lifetime or post-handoff sound/display effects. Existing providers
and host builds do not select it; this does not replace their GUI-based path.

player/engine_provider.c is a private opt-in provider adapter for this control
path. It borrows an initialized qualified provider for snapshots, non-transport
commands and optional browsing, and owns a separate engine-control binding.
Play/pause/next/previous use that binding; malformed extra scalar/ID/revision
arguments are refused. No new snapshot state mapping is inferred. Closing the
adapter releases only its binding, leaving the borrowed provider initialized;
the caller must close it before the original provider/native lifetime ends.
`test_stock_engine_control.py --provider` executes the real client core, adapter,
engine binding and original request construction. It verifies direct transport
without base command calls, delegated volume/snapshot/browse, wrong-thread close
refusal and preservation of the borrowed provider. Base callback data, CtrlInfo
and native primitives are models in this profile. Default host construction
remains GUI-based; this adapter is not linked into a firmware or installed host,
and it does not qualify post-handoff ownership or physical playback.
`build_player_host.py --engine-provider` now links an explicitly selected
analysis-only host profile under work/player-host-engine. It first binds the
original provider, then the engine adapter; failed adapter binding closes the
newly owned original-provider binding. Default construction remains GUI-based.
The host-anchor test accepts the same flag and executes the patched original
call, PID routing and real provider bindings for seven acceptance/refusal cases;
the accepted fixtures dispatch201 owner turns. No transport command or physical
AudioC initialization executes in that anchor test. The complete DSO links, but
managed admission and deferred teardown are not installed by this profile.
Compared with the current default analysis build, its logical DSO file adds556
bytes, BSS adds14480 bytes and summed PT_LOAD memory adds16092 bytes; the patched
original ELF adds0 bytes. These figures are build-specific, not peak RAM,
filesystem allocation or firmware-capacity qualification. No firmware package
or installation is produced.
`build_player_host.py --managed-host` replaces the legacy listener service with
host_managed_service.c and may be combined with `--engine-provider`. Separate
work directories preserve default/engine/managed profiles. The managed service
records its original owner through the guarded host dispatch, opens no listener,
and creates its broker/session workspace only on a trusted explicit offer with
caller-supplied authorization and generation. One session workspace is provided
by this analysis wrapper. Stale generations are refused; clock/source loss stops
admission, and explicit prepare routes through the managed host's one-shot drain.
Only ACTIVE service turns tick the broker and attempt native queue/source
attachment. Native manager delivery remains absent; the optional native-prepare
analysis pairing below adds exit routing. Hidden C entry points do not make the
service reachable by an external application.
A resident consumer is now a verified original-manager execution candidate.
The guest probe's `--resident-fixture` adds a test AppList entry `0x00010010` and a
C APF client. Original sysmgrd launches it directly, registration returns that ID,
and `/proc` identifies its parent executable as `/usr/local/bin/sysmgrd`. The
Home test client has the same manager parent. During a mode1 launcher round trip,
Home exits/restarts while the resident registers once and keeps the same live
PID before and after return. No framebuffer/audio/radio resource is acquired.

This supports investigating a headless SDK consumer while Sony's player is
foreground, without changing every graphical app's switch mode. It does not
keep the player provider alive when Home itself exits: a consumer must treat
provider EOF as session loss, not replay old controls. The probe has no SDK grant
or descriptor delivery and is not an authorization implementation; a parent/path
observation is not permission to grant controls. Its RAM PID files are guest-only
test markers, not application persistence or a production identity protocol.
The separate `--missing-resident-fixture` provides a negative result: registering
an absent `/contents/HOMEBREW/apps/missing-resident/app` under `0x00010010`
causes original sysmgrd to panic at `ApfDaemonCore.c:998` with abnormal application
termination, before the Home round trip. The report deliberately retains
`passed: false`; this is failure evidence, not a successful lifecycle test.
Do not register an optional, removable external app as a mandatory boot resident.
A future resident integration needs a separately qualified stable manager client
and explicit optional-consumer lifetime, not a direct AppList path to an app that
users can remove. This observation uses a generic guest kernel and mocked devices;
it does not establish the physical reboot/recovery outcome. Other launch failures,
power/USB and physical residency remain unqualified.

Do not generalize that missing-executable result to every resident exit. In the
separate `--resident-exit-fixture`, the C client receives its successful APF
registration reply and returns zero without a deregistration request. Original
sysmgrd continues, and the Home mode1 launcher round trip completes. The probe
requires both registration and the explicit normal-exit marker as well as the
existing lifecycle checks. This supports further investigation of an optional
consumer that exits normally; it does not prove an on-demand restart API,
abnormal-exit tolerance, repeated registration, SDK resource drain, or physical
sleep/USB behavior. No service should be installed based on this result alone.

Exit status matters: `--resident-exit-fixture --resident-exit-code 23` also
registers successfully, but original sysmgrd then reports abnormal termination
at `ApfDaemonCore.c:998`; the Home round trip does not complete and the report
retains `passed: false`. A successful APF registration does not isolate the
manager from subsequent process failure. Keep ordinary SDK request failures
inside the service lifecycle instead of propagating them as process exit codes.
This is not crash containment: a signal, abort, memory corruption or native
manager-required termination still needs separate investigation. A direct
optional resident is not yet an acceptable production integration.

The pinned manager launch inventory (`tools/inspect_manager_launch_calls.py`)
narrows the next investigation to original internal paths: `0x112c4` enumerates
configured IDs and calls `0x110e0` only for class `0x0001xxxx`, with its third
argument zero. Startup calls that enumeration at `0xa380`. The other direct
launch path is a tail call at `0xa4d4`: wrapper `0xa4c4` rejects a zero second
argument with `0x102`, otherwise forwards to `0x110e0`. Its direct callers include
the argument-reordering thunk at `0xbd24` and the state-gated path at `0xcb50`.
These are static ARM branch candidates, not a verified public request number or
an authorized on-demand API. Trace their dispatch tables and runtime state before
exposing an SDK lifecycle operation; do not invoke internal addresses from apps.

Further tracing identifies request-table slot2 as `0xf7cc`, forwarding to the
state-gated launch path `0xcb50`. The guest-only
`--resident-exit-fixture --resident-restart-fixture` sends request2 with a1060-byte
packet, target ID at offset20, and the no-argv-override flag at offset1052. One
run accepted the request, registered a second resident PID and completed the Home
round trip (the old fixed sequence-number check failed after the inserted request).
A fresh run with updated checks accepted request2 but then hit the resident
abnormal-termination panic before a second registration. Do not describe this as
a reliable restart API: acceptance is not completion, and the short guest delay
does not establish prior process reap or manager readiness. The initial failed
reports/logs remain evidence; production integration stays disabled until the
exit/start ordering and child failure are explained.

Instrumented repetition narrows one failure to IPC response timeout: the second
resident starts but `recv` of its registration reply returns -1/EAGAIN(11), while
Home also times out waiting for lookup36. The subsequent manager panic names the
resident's nonzero fixture exit, not an exec failure. Other instrumented runs
register twice and complete; one names Home after its request timeout. Thus the
earlier process-reap hypothesis is unproven. Investigate manager event delivery,
datagram queue backpressure and reply/event servicing before adding delays or
claiming launch failure. The fixture currently sleeps without draining its event
socket during this test, which is a relevant unqualified condition.

The guest test now services both request-reply and notification sockets while
waiting for every synchronous request, using poll and a fixed three-second total
deadline. Informational notices are consumed; other20-byte lifecycle notices are
kept in a bounded16-entry queue and delivered to the main loop, never silently
discarded. Pumping only requests2/36 allowed restart but moved the timeout to the
subsequent switch6. Pumping every request completed four fresh guest builds/runs
(`work/arm-system-resident-event-pump-{2,3,4,5}`), each with two registrations and
the full Home round trip. This supports notification servicing/backpressure as a
fixture defect; it does not prove the exact stock send syscall blocking point,
physical behavior or a generally reliable production service. Earlier failures
remain retained. Do not translate the test-only informational-event policy into
a production APF dispatcher without its complete callback semantics.

`--resident-sdk-fixture` combines the original manager guest with the public SDK
consumer. The registered resident runs the existing managed-host fixture, forks
a separate ARM SDK client and explicitly delivers its stream descriptor through
SCM_RIGHTS before exec. Both processes use Sony's original loader/libc, pthread
and legacy clock adapter in the generic ARM kernel guest. The public client
checks controls, metadata/position/volume, all four media views, state events,
explicit PLAY_ITEM admission polling and close receipt. The resident checks
client exit, session release and broker close while retaining the borrowed model
backend; Home completes its existing launcher round trip. Its event socket is
serviced during host ticks for informational notifications only.

This is integration evidence, not native player service availability: the
provider/media remain deterministic models, the server lives in the test
resident rather than SpiderApp, and the fork/descriptor shim supplies fixture
authority. It neither discovers an original-manager grant mechanism nor verifies
Sony GUI/provider startup, sleep, USB or hardware controls. The profile must not
be installed or used as a production resident implementation.

The managed analysis host now also contains an explicit inherited-delivery
adapter (`host_inherited.c`). A trusted startup may supply a connected Unix
datagram endpoint, nonzero generation and explicit grants1..7 before owner-loop
dispatch. The optional constructor is disabled unless
`X1000_PLAYER_INHERITED=1`, `X1000_PLAYER_DELIVERY_FD`,
`X1000_PLAYER_GENERATION` and `X1000_PLAYER_GRANTS` are all valid. It does not
listen, discover clients, open a path or derive authority from credentials.
These parameters express authority already established by trusted startup;
an environment variable alone is not authentication or an isolation boundary.

Valid adoption transfers ownership of that endpoint and sets CLOEXEC. The first
qualified original-owner dispatch calls the real host offer API exactly once,
then closes its delivery endpoint regardless of admission result. It does not
automatically reconnect, renew grants or retry a failed offer. Native exit
cancels an unconsumed endpoint and prevents later admission. Invalid configuration
does not take ownership of the caller's descriptor. Configure is serialized with
startup/dispatch; it is not a public cross-thread registration API.

`test_player_service_drain.py --host-wrapper --inherited-delivery` exercises the
adapter, actual host wrapper/broker, descriptor receipt, control, catalog reader
threads and deferred drain with host sanitizers and Sony libc/LinuxThreads in the
generic ARM guest. Full managed/engine/native-prepare DSO linking also passes.
Original playback/media remain models in this test. The trusted startup that
arranges the client peer and executes the full Sony GUI is not installed or
physically verified; the new caller path does not establish a working device
service or justify a firmware release.

Live read-only identity checking also matches this unit's current SpiderApp MD5
`cd42bf3c165fb6907bbdc2f9f0c26cf6` to the locally retained process-cache language
image SHA256 `213c4c777ff8f71e400bc1287d1096307b7c3fc48122ca4c0d81a88fcfc712a6`.
Applying the guarded owner, mapped Met and prepare edits to that exact base
reproduces the existing composed candidate SHA256
`227006483d65b7011ffcdc6fd84c8f303e4f1cb77ae443d8a5f417e40d11c688`.
Both are6,457,376 bytes;67 bytes differ. This establishes base/composition
identity without replacing the unit's language version, not runtime acceptance.

The bootstrap guest test now has a sixth case: on a mounted tmpfs it binds the
wrapper over a payload path, executes through that path with original loader,
verifies PID/argv/environment/preload, unmounts and compares the restored target
byte-for-byte with the original payload. The initial attempt to bind a source
from guest initial rootfs failed with EINVAL and is retained under
`work/player-bootstrap-rootfs-bind-failure`. The tmpfs case passes; it is not
Sony ext2/vfat/kernel qualification, a ready device activation script or crash
recovery proof. Device root remained read-only during identity inspection.

`startup_delivery.c` adds a private, single-start Unix-datagram rendezvous for
the proposed temporary bootstrap. Trusted startup supplies a fresh RAM IPC
directory, fresh32-hex nonce, generation and explicit grants. The helper accepts
only `/tmp/x1000-player-<single-component>` names, never unlinks an existing
listener, verifies the exact nonce/generation/grants, connects the two datagram
endpoints and bounds the client wait to at most3seconds. The caller remains
responsible for fresh directory ownership and cleanup; this is not authentication
against root or a production app-manager permission mechanism. Socket files are
transient RAM IPC, not persistent application state.

`test_player_startup_delivery.py` passes host sanitizers and original-libc ARM926
execution for successful handshake followed by real SCM_RIGHTS SDK stream
delivery, nonce rejection, no-accept timeout, existing-endpoint retention and
non-RAM-path refusal. The optional bootstrap compile profile requires explicit
directory, nonce, generation, grants and retained-original fallback paths. On
successful rendezvous it prepares the inherited-host environment and preserves
only that explicitly approved descriptor through exec; otherwise it selects the
retained original payload without adding the SDK preload. The seventh bootstrap
guest case executes that absent-rendezvous fallback successfully. A successful
bootstrap exec with rendezvous plus full Sony GUI/owner dispatch, physical
activation/cleanup and native controls are not yet qualified by these tests.

The actual bounded read-only probe is `runtime/apps/wireless-remote/probe.c`,
built separately from its graphical scaffold. It accepts only READ authority,
waits for startup and a delivered stream, reads one snapshot, requests a close
receipt and releases local state. A model-host integration test runs the ARM
probe through this rendezvous, including cleanup, with zero control calls. Its
help entry also executes on the physical X1060 after user-storage readback
verification; that is loader/entry evidence, not a live-player snapshot.

The startup guest test additionally verifies successful rendezvous through exec
and the full managed DSO constructor: the explicit connected descriptor survives
exec and the constructor marks it CLOEXEC again. A one-shot optional wrapper
profile compares `/proc/self/exe` with its explicitly compiled source, checks
the exact configured target in `/proc/mounts`, then lazily detaches that overlay
before payload exec. Its guest case confirms the original target bytes are
visible after execution. The candidate and retained-original payloads remain
separate user-storage files; the root file is not replaced on disk. Failure to
detach returns126 rather than pretending cleanup succeeded. This profile still
requires Sony-kernel, complete GUI, USB and actual restoration verification.

`prepare_player_live_start.py` creates private, per-attempt user-storage paths,
nonce/generation, a READ-only wrapper and all file hashes. It refuses an
unrecognized installed base/composition. It does not mount, deploy or activate
anything. Its output contains proprietary binaries and must remain ignored.

## System radio capability versus remote policy

The compatible driver/module is a system capability, independent of the remote
business. System installation is not a power request. Shared lifecycle ownership
must enforce ordinary Wi-Fi versus ESP-NOW exclusion and expose bounded acquire,
quiesce, release and observed completion to SDK consumers. The remote's Settings
switch requests that capability and closes its work; it must not implement raw
module swaps or hardware writes on its own. Remote-off requests radio power-down
after its work is drained, while permitting a subsequent explicit ordinary-Wi-Fi
request. It is not a permanent wireless master ban. Existing experimental
restore-and-reconnect policy is not the final remote-off policy; a generic stock
restoration mechanism and the caller's desired reconnect/off outcome must remain
distinct. Driver load state, network disconnect and physical powered-off state
are separate observations. Do not claim the off outcome until the original
hardware power path is qualified. Prefer a verified low-power RF setting without
inventing register values; the current stock-style txpower15 command is only a
lead for driver analysis, not evidence for a lower validated operating point.

`test_player_service_drain.py --host-wrapper` executes the actual service
dispatch/offer/prepare API, production broker and real reader threads under host
sanitizers and original Sony LinuxThreads/libc in the generic ARM guest. It checks
lazy startup, descriptor/HELLO, generation refusal, one NEXT, catalog work,
closed admission, balanced reader release and one continuation. Media and queue/
source attachment are models. Combined managed/engine DSO linkage also passes.
Current file/BSS/PT_LOAD memory sizes are recorded in each profile's build.json;
they are not runtime peak memory, filesystem fit or hardware qualification.
The owner-anchor ELF adds0 bytes; the separate standalone Met ELF adds32768
bytes. The source-composed Home/language profile instead uses its checked mapped
Met slot with0 additional growth relative to that composition. Inspect the
manifest for the exact artifact, not the owner-only size as a full-package bound.
The wrapper test's `--clock-failure` variant forces the host clock callback to
fail after session adoption/control/catalog work. Admission then refuses new
offers, real readers finish and close their modeled native handles, the broker
drains to STOPPED, and no original-prepare continuation is invoked. Host
sanitizers and original LinuxThreads/libc ARM execution pass. This models clock
read failure, not a real clock or hardware fault, and does not qualify suspend.
The service now exposes an internal exit decision with only FACTORY/HOLD
outcomes. Before any SDK ownership, or after a completed ordinary no-continuation
stop, FACTORY permits the original path. Active resources, pending prepare,
partial initialization, context fault and repeated handled exits stay HOLD.
HOLD is not completion. The first owned exit starts prepare once; failure
quiesces sessions and retains FAULT instead of permitting native cleanup. The
helper does not read raw native registers. The optional native-prepare analysis
pairing supplies bridge/context checks; original-manager delivery and full event
ordering remain incomplete.

deferred_prepare_adopt can attach a fresh continuation to an already quiesced
SESSIONS/BACKEND drain without restarting it. managed_host_prepare uses this
when exit arrives during an ordinary stop, so completion is not lost. The
blocked-reader fixture first reaches BACKEND with both handles live, then adopts
and continues only after release. Wrapper normal/clock/fault cases pass under
sanitizers and original LinuxThreads/libc ARM: no-resource fallback, one-shot
hold, no continuation for ordinary clock stop, and persistent context-fault hold.
The fault fixture intentionally retains SDK objects; process exit is not a
successful drain. Native context, media and continuation effects remain models.

`tools/test_stock_info.py --engine-control` now links the engine binding to the
real stock_info implementation and executes original controller/session lookup,
CtrlInfo clone/disposal, identity access and retained track/chapter references
before native pause request construction. The combined cases check chapterless
tracks, selecting the matching session after another session, allocation/read
failure, invalid identity, transition/error and handle change during snapshot
release. Snapshot pool allocations/frees and object references balance, and
rejected cases never enter the native control API. Pool/mutex/allocator/preflight
and some primitive effects remain modeled; no real post-handoff controller
lifetime or physical playback is qualified. The original info-only matrix remains
the default and writes a separate report from this combined profile.
The shared stock_info reader also checks wrapper/service/session identity after
snapshot disposal, before committing any output. A detected replacement returns
BUSY with the caller's output intact; reference release still completes. The
info-only matrix exercises all three replacement cases, so this protection also
applies to observation consumers rather than only the experimental command path.
It detects observed replacement, not ABA reuse or arbitrary concurrent teardown;
native owner/lifetime protection remains required.

2026-10-31 physical observation: with WiFi Terminal foreground, repeated process
and executable-link inventories show sysmgrd, appproxy, launcher and Terminal,
but no SpiderApp executable. The root mount is read-only and user storage is
mounted. This snapshot confirms that an in-SpiderApp SDK endpoint cannot serve
foreground Homebrew in that observed launch state. It does not prove the earlier
exit sequence or behavior of other switch modes. A companion launch path or
native-resident integration must be qualified instead of assuming the default
Homebrew path keeps the player alive. Evidence remains private under work;
inspection used existing shell commands only, with no uploads, native diagnostic
binary, playback/RF operations, serial access or firmware changes.

Do not equate foreground loss with SIGSTOP or a stopped process. The maintained
Homebrew adapter requests switch mode1; the stock browser wrapper requests mode0.
Original manager instruction replay maps mode1 to notification4 and mode0 to6.
tools/check_player_switch_callbacks.py verifies registered callback4 at0xea18
queues0x420015, whereas callback6 at0xeb9c queues0x420024. Existing Root dispatch
checks distinguish command3 finalization from queued command6. These bounded
traces do not establish process exit, continued music or continued owner-loop
pumping. A player-session integration must qualify its actual switch/cleanup
path; changing mode1 to0 just to keep a service alive could break the resource
handoff needed by existing applications. No switch flags are changed here.

tools/check_player_finalize_order.py now executes original command3 completion
at0x10ee4 through0x11040 and the0x10d80 finalizer. Its native branch thunks reach
0x288100, MomaLcPluginLib_finalize0x28babc and MomaLib_finalize0x2958a8, followed
by queue/ticket/mutex teardown. Target subsystem effects remain modeled; command
completion and Root readiness are fixtures. This establishes a concrete ordering
hazard for SDK metadata workers, not actual thread destruction or process exit.
No owner-loop tick after that finalizer is a valid substitute for pre-finalize
revocation and proven worker drain. The native broker must close/drain before
these Moma boundaries; a verified pending-completion integration point is still
required. Do not install the experimental host while that coordination is absent.

tools/check_player_pending_finalization.py verifies native48a14 registration,
48a78 removal and11250 completion with a supplied command3 context. Two pending
tokens prevent10ee4 until both complete; an unrelated token does not clear a
nonempty tracker. When PCS supplies a further pending token, native completion
records it and waits before finishing. This suggests an existing coordination
mechanism, not permission to append an arbitrary SDK token: extra capacity,
allocation and token namespace still need qualification. In the retained-context
fixture, replaying completion after the tracker empties reaches completion again.
The real finalizer is intercepted and its post-finalize lifetime is not modeled;
this is not evidence of a stock-device bug. A future SDK adapter must make its
native completion one-shot per registered token/epoch and never auto-retry an
uncertain completion notification.

tools/check_player_pending_capacity.py qualifies the pinned tracker layout:
getter489dc selects132-byte records (count plus32 token words), and initializer
489f0 clears exactly those132 bytes. In emulator scratch, helper48a14 ignores0,
accepts duplicates as separate slots, and a33rd insertion writes the next word
without an internal capacity check. Stock callers may enforce limits elsewhere;
this is not a claim of a stock-device overflow bug. A future SDK registration
must validate count0..31 and absence of its token on the original owner, never
write a33rd token, and account for later stock registrations. Actual stock peak
occupancy, safe spare capacity, unused token allocation and insertion point are
still unqualified. No tracker write or extra token is enabled on a device.

`tools/check_player_prepare_pending.py` executes the original preparation entry
112fc and tracker helpers with modeled component outputs. For command3 it calls
nine component preparation callbacks in order. Nine nonzero fixture tokens are
recorded in that order and defer finalization; synchronous components proceed to
the PCS check, which can add its own pending item. This is a path-specific count,
not a bound on all original registrations or proof of spare capacity.
Crucially, a tracker that is already nonempty at entry skips all nine callbacks
and finalization. Pre-inserting an SDK item before this entry would therefore
skip original preparation in the tested path: do not use that as an integration
strategy. Some pending branches also leave the supplied output word untouched;
callers must follow the original contract rather than infer a universal boolean.
Component cleanup/preflight effects and finalization bodies remain intercepted.
The deferred-action fixture additionally executes original action718c0 while
intercepting its112fc command3 call. The action returns0 with the supplied root
unchanged and without component preparation. A later call to original112fc with
a fresh output word executes all nine modeled component callbacks and normal
completion. This suggests investigating postponement before preparation rather
than pre-seeding its pending tracker. It is only a boundary model: no actual SDK
drain, event ordering, manager timeout, competing command or native root lifetime
is qualified. Never retain the original caller's stack output pointer, and do
not install or treat this candidate as permission to defer suspend/USB events.
The existing PID shim uses original r2 for its caller-address C argument, so it
cannot directly forward the native prepare function's third/output argument.
The optional XW_PLAYER_CAPTURE_ARG2 assembly variant saves original r2 as the
fifth C argument using an8-byte stack frame, retains the caller/list arguments,
and returns the dispatcher result. `test_player_pid_arguments.py` checks aligned
stack restoration, selected callee-saved registers, explicit output-pointer
forwarding and ordinary arbitrary-register calls without pointer reads. The C
dispatcher in that isolated test is a recorder. Default builds retain the old
variant; the explicit native-prepare profile selects argument capture and the
paired guarded dispatcher. Never retain
the caller's stack output pointer beyond the intercepted call.
`player_prepare_bridge.py` generates a44-byte analysis trampoline with an
explicit handled marker. It saves/restores native arguments and LR around the
optional PID observer. Non-marker results tail-call original112fc; the marker
returns0 without entering preparation. `test_player_prepare_bridge.py` runs both
original exit actions718c0/71a3c through it and the argument-capture shim in six
cases. Captured third/output arguments match the native fallback, initialized
outputs remain intact in handled cases, and stack/saved registers are restored.
The dispatcher and original preparation body are models; a scratch page is
mapped only in Unicorn. No on-disk Sony image, mapped-slot proof, ELF loader,
owner/image/context guard or deferred service is installed. Non-marker means
permission to run native cleanup: it is not a generic safe error fallback when
SDK resources are active. A future owning/faulted dispatcher must suppress
cleanup until its lifecycle policy is satisfied; this test does not supply it.
`patch_prepare_bridge` now accepts a pinned source-composed Home/language/owner/
Met analysis profile with an existing executable zero slot at4d7fc0. It compares
original prepare/action/PID spans to the pinned JP image, checks the entire
composition hash, writes44 bridge bytes and changes only BL sites718e0/71aa4.
`test_player_prepare_composition.py` rebuilds the source composition and verifies
all other file bytes plus ELF/program headers and the Met slot remain unchanged.
Occupied slots, modified action/coordinator/other code, repeated patching and an
original image without the mapped slot are refused. The output is analysis-only
and grows0 bytes relative to that composition. The ELF-only output has no DSO
or manager policy; even the paired analysis build is not an installable SDK
service. Updating a source-composition profile requires fresh
review/evidence, not relabeling an older pass or blindly replacing its hash.
player/stock_prepare_view.c now provides a read-only pre-prepare context view.
It requires the patched bridge/actions, PID PLT, tracker and root coordinator/
finalizer spans to match their pinned digests. The supplied native call must be
Root613e60/command3, with a nonzero epoch and an independently qualified original
owner. Root's tracker must be66efe8 and empty; overcount, existing command3 or
pending work refuses capture. It records opaque Root command/auxiliary/state
words and rechecks them plus tracker identity on later owner/epoch checks.
It does not store a caller output pointer, add a token, retain Root or invoke
original prepare. Capturing pthread_self alone is not authority; the caller
supplies the already-qualified owner.

`test_stock_prepare_view.py` executes this ARM view and hash code on a freshly
source-composed bridge image. Thirteen bind/refusal cases plus later epoch,
thread, Root-field and tracker changes pass; native Root/tracker buffers remain
unchanged. dladdr, native data and original-owner identity are fixtures. This is
observed consistency, not ABA detection, prevention of concurrent teardown,
original-loader boot or a live lifecycle binding. The default host omits this
view; the explicit native-prepare analysis profile pairs it with the dispatcher.
host_prepare_bridge.c now supplies the C glue for a separately qualified native
bridge caller. It verifies the code profile, records a bridge-local monotonic
epoch (not an original-manager/session generation), and gives the resource
decision callbacks that lazily bind/check the read-only Root view. Owned prepare
continues through a fresh local output word at112fc only after SDK drain.
The original caller's output value is never dereferenced or retained. Reentry
and wrong/unknown owner hold without replacing context; a held decision is
one-shot. Only explicit FACTORY permits fallback; unknown/error decisions hold.
An exit-event notification prevents later session admission even if no SDK
resources needed drain. It is a native event, not an ordinary phase query.

`test_player_prepare_dispatch.py` combines original exit action/bridge, argument
capture shim, C glue, real hash/Root view and deferred/session/drain core in seven
cases: factory, owned, changed context/code, initially refused code, unknown
decision and wrong owner. Reentrant context replacement is refused. The owned
case reaches original112fc and its nine component boundaries once after modeled
worker readiness; changed/refused cases never enter prepare. The production PID
dispatcher/host resource decision, owner and workers remain fixtures, and native
component/PCS/finalizer effects are intercepted. This does not install a hook or
qualify full manager event ordering/hardware. The composition test also verifies
that all previously recorded native guard spans remain unchanged by the bridge.

`build_player_host.py --native-prepare` now produces a paired analysis DSO and
source-composed ELF in its own prepare profile directory. It implies managed-host
and can combine with engine-provider. The DSO selects the five-argument capture
shim, production PID dispatcher, C bridge/Root view and managed exit policy.
Only bridge caller4d7fc8 enters this path. Before owner binding, no SDK service
can have started: it records the exit and permits ordinary PID/native fallback.
After binding, a different thread is held; the qualified owner enters guarded
interception. Owner/Met/prepare observer work restores caller errno before return;
the factory continuation can still change errno through its own execution.

`test_player_host_anchor.py --native-prepare --engine-provider` passes ten cases,
including native factory fallback, pre-owner fallback, foreign-owner refusal and
ordinary PID behavior. It deliberately changes errno during dladdr to check
observer transparency. The helper uses no-resource decision/notification models
and intercepts the original prepare body; the complete DSO links the production
managed policy but is not booted by this test. Default seven-case coverage also
passes. Descriptor delivery from original manager, complete event ordering,
sleep/USB, loader/hardware acceptance and recovery remain unqualified. No firmware
package is generated. Total ELF growth is relative to original; bridge growth
is separately recorded relative to its existing Home/language/Met composition.
The target source archive `work/downloads/linux-kernel-2.6.10.local.tgz` contains
`include/linux/threads.h`, defining `PID_MAX_DEFAULT` as `0x8000` and
`PID_MAX_LIMIT` as that value for32-bit long (4 million for larger long).
The handled marker `0x58575052` is above either limit, distinct from
a conforming ordinary PID; this is not authority or protection against arbitrary
in-process modification of the dispatcher.
`tools/check_player_prepare_pending.py --sdk-native` links the real ARM
deferred_prepare, service_drain, session and player-client cores into this replay.
Original action718c0 enters the C begin path; admission stops and two pending
steps execute no original preparation. After modeled worker readiness, the real
C continuation calls original112fc with its own live output word. All nine
component callbacks run and continuation remains one-shot. Repeated original
exit actions do not restart the drain, and a lost modeled context refuses native
preparation. Worker readiness, identity validity and native cleanup effects are
models; this replay complements, not replaces, the actual LinuxThreads drain
test. It does not qualify intervening event order, manager deadlines or an
installed patch. SDK and native profiles write distinct reports.
The scheduling question has a separate original-loop replay in
tools/test_stock_owner_idle.py. With an inactive GUI fixture and stock200000us
input-wait setting, ff04 executes10644 ->134ec ->51ae4 ->b4c54 ->e1aa0 and reaches
the existing a6968/ff3c anchor after each of three select returns. No wait policy
is changed. Input decoding, other loop work and select completion are modeled;
no actual200ms sleep or deferred-prepare continuation runs in that profile.
This shows the traced return path can revisit the anchor, not a bound on full
tick latency, an installed wakeup mechanism or qualification of other UI states.
The sdk-owner-loop case of `check_player_prepare_pending.py --sdk-native` now
combines that original ff04/input path with the real C deferred-prepare core.
At a6968 the replay redirects the existing anchor to the C step, preserving the
original return address. Two owner turns remain pending without native cleanup;
on the third, modeled workers become ready and the C continuation executes
original112fc exactly once. The observed sequence is select/SDK-step three times
with200000us timevals. A later step does not repeat preparation. Select return,
other loop stages, identity and worker readiness are still models; this does not
install the redirection, execute complete event dispatch, qualify native cleanup
effects, or prove real timing/USB/sleep behavior.
`tools/inspect_player_pending_calls.py` inventories direct ARM branch candidates
with surrounding instructions; indirect callers and reachability remain outside
that static inventory. Neither tool installs a hook or allocates an SDK token.

player/stock_pending.c now provides a private read-only pre-existing-token view.
It requires the pinned coordinator/tracker instruction digests, command3, the
known Root tracker pointer, count<=32 and exactly one matching token. Bound
thread and supplied epoch/token must match on later checks. Binding itself must
occur on a qualified original owner; recording pthread_self is not proof of
that authority. The platform must provide the epoch and valid token externally.
tools/test_stock_pending_view.py executes the real ARM inspector and image hash
code against the original image, rejecting missing/duplicate tokens, overcount,
wrong command/table, altered instructions, stale epoch and wrong bound thread.
dladdr/thread identity/native data are fixtures. No native state is written and
no token registration, completion notification or lifecycle hook is installed.

tools/check_player_gui_finalize_token.py verifies GUI command3 at143c0 for
active/inactive getter fixtures: both native branches write pending output0,
with cleanup helper bodies modeled. Command6/7's observed GUI tokens206/207 must
not be extrapolated to an already-registered203 or reused for SDK cleanup.
Zero output proves only the tested branch's pending result, not physical or
global synchronous cleanup. A real SDK waiting item still needs an explicit,
qualified registration path rather than borrowing a token from another command.
The deeper inactive-GUI case now executes cleanup coordinator11ec4 and records
its33 nested getter/cleanup/tail boundaries. Original getter27a04 and reset27a68
run without interception and clear four seeded state words before command3
returns its zero pending token. Other leaves remain modeled; those four fields
are not established as the SDK's engine/media dependencies. This nevertheless
rules out treating component preparation as a pure token-registration pass:
native state mutation already occurs there. SDK quiescence must precede relevant
component cleanup, and waiting only at root finalization is insufficient until
every borrowed resource's earlier cleanup boundary is qualified.

tools/check_player_moma_finalize_refs.py refines the library-finalize finding:
both exported functions decrement global library reference counters. With1 they
call the generic reverse-table release boundary; with2 they return after decrementing
to1; with0 they select panic. Native instructions execute with release/panic
effects intercepted. These counters are not established as live-client or worker
counts, and the underlying manager has a separate release earlier in teardown.
Therefore "finalize called" does not always mean immediate destruction, but an
extra SDK initialize reference is not a qualified substitute for pre-teardown
drain. No additional initialize/finalize calls or counter writes are installed.
The same replay now executes the CtrlInfo pool finalizer275dcc: it calls pool
release285f94 with822494 (the pool used by stock_info cloning), then clears
initialization flag822490. Both initially-set and initially-clear flag fixtures
call release; this entry must not be treated as an idempotent SDK cleanup API.
Pool release effects remain intercepted. A literal reference to275dcc occurs at
60f7cc beside initialization-related addresses. Direct branch scanning
alone found no call to this entry, so the inspection tool also inventories
aligned address literals across load segments and direct B tail branches.
Literal matches do not independently prove function-table semantics. This pool
is distinct from the earlier GUI state reset27a68; do not conflate their lifetimes.
The generic routine33d9bc is now executed rather than treated as an opaque
release boundary: r0 is a12-byte-entry callback table and r1 is its entry count,
not a module ID. It invokes each entry's third word from last entry to first.
The manager's table60f940 has8 entries, MomaLib's6101d8 has11, and the plugin
library's60fb2c has8. Original wrappers plus reverse dispatch pass with individual
callbacks intercepted. Manager and plugin tables both include MomaLib_finalize;
its reference counter still determines whether a nested call dispatches.
The CtrlInfo pool callback reference is not in these three immediate tables.
Its separate release chain now executes from secondary input thunk b6b18 through
275c20 (initial reference1), its four-entry table, nested wrapper275cbc and the
15-entry table60f71c. Reverse dispatch reaches275dcc first in that nested table,
invokes the pool release boundary with822494, and clears822490 before continuing.
Other leaf cleanup effects remain intercepted. The root-finalizer order replay
now also executes this nested chain in combined profiles. With root-ready1 and
initial reference1, it reaches pool release after the Moma library boundaries
and before queue finalization. Initial reference2 decrements to1 without pool
release. Root-ready0 skips this secondary input path and leaves its reference
and seeded pool flag unchanged. Both original root-ready branches and both
reference fixtures pass; other cleanup leaves remain intercepted. This is not
a complete concurrent-root or hardware teardown test.
The same completion replay compares commands6 and7 with command3. Command6
queues41000a without entering the tracked Moma/secondary-input/pool/queue
finalizers; command7 queues410009 and reaches command-notify10e68 plus GUI-resume
140b4 boundaries. The seeded Met reference and pool flag remain unchanged in
both completion cases. Preparation is supplied as already complete and resume
effects are intercepted: this does not prove that earlier component preparation
preserves a usable controller. The original-manager mode0 guest round trip also
passes with retained C Home, while mode1 exits/relaunches it. These are distinct
evidence scopes, not authorization to change all app profiles to mode0 or a
post-handoff SDK/hardware qualification.
`check_player_prepare_pending.py --native-basics` now executes command6 root
preparation with original callbacks16b74 and f32c rather than replacing both.
f32c returns a zero pending result without a lower call for this command. With
environment getter f6c0 modeled as1,16b74 follows5433c ->bae24, clears the supplied
object's48c word and reaches17de74 with argument8; getter value2 skips that path.
The power/object/environment getters and17de74 effect are models, as are the
other seven component callbacks, PCS and completion body. These numeric values
do not establish region/model identity or the resource meaning of argument8.
The cases demonstrate conditional state mutation during preparation, not a
usable retained audio controller or a global guarantee for every component.
The deeper `--native-subsystem` profile resolves argument8 through original
17d358 to singleton7dcc84 and executes17de74 ->181294. Its logging literal is
Asv1SegCtrlPlayer.c, identifying a1seg control path rather than establishing a
generic audio/power-resource meaning. With modeled eligible state,181294 sets
flag100 under the original mutex-call boundaries, triggers18c89c, then repeatedly
calls33761c with1 until that flag clears before lower release181bbc.
Immediate and two-wait completion fixtures pass. When the fixture never clears
the flag, observation stops after three waits with preparation still in progress
and no completion: there is no timeout selected in that observed loop. State,
mutex, trigger, wait completion and lower-release effects remain models. This
does not diagnose a physical hang or any prior sleep incident. SDK drain before
native prepare cannot by itself guarantee that every original prepare callback
is bounded; preserve the factory behavior rather than fabricate completion.
SDK snapshot reads/releases must finish before this chain; its exact interaction
with earlier component cleanup and actual live reference counts remains open.
Data addresses in this analysis
are translated through ELF PT_LOAD offsets, not a uniform text-file delta.

HOME normally detaches a background task's settings page, but ordinary foreground
display/touch ownership still ends through the original launcher. This exception
is permitted only for an approved task; it cannot bypass current XNOW handoff.

USB prepare must prevent new user-volume work, drain readers/writers, close
descriptors and account for radio/key-journal dependencies before handoff. Sleep
prepare similarly stops admission and establishes each provider's safe state.
Whether a task pauses or terminates is capability-specific and must be documented.
Do not assume an invented callback can veto USB/suspend; if the original system
offers no safe integration point, do not enable that resident capability.

Wake/reconnect rechecks resources and grants before becoming ACTIVE/RUNNING.
Do not automatically resubmit playback commands. Power loss/reset cannot promise
graceful release; any durable protocol counters retain their separate verified
storage rules. No generic lifecycle journal writes to system partitions.

## Threading, observation and resource bounds

Native player calls execute only on their qualified owner thread. Wireless IO
and potentially blocking database access use separately bounded workers. UI
callbacks enqueue/control without blocking on hardware or a service deadline.
All queues, sessions, pending requests, events and receipts have explicit limits;
return BUSY instead of unbounded allocation. Per-client quotas prevent one app
from monopolizing the original loop. Never invoke application callbacks under a
provider lock. Define lock ordering before integrating multiple services.

Snapshots provide current truth. Events provide sequence-numbered observations,
not an unlimited lossless history. Overflow sets RESYNC_REQUIRED; obtain a new
snapshot plus its sequence and discard older events, then resume after that
sequence. Request terminal results use request_query, not an event queue alone.
Failure leaves caller output unchanged; applications must mark old data stale.
Lifecycle generation/sequence is not a media-catalog revision. Native revision0
remains unknown and cannot promise consistent cross-page media reads.

## Provider adoption

| Capability | Sharing and adapter requirements |
| --- | --- |
| Player state/media reads | Shared read sessions, async epoch cancellation, original identity validation; no cached success after source loss |
| Playback control | Explicit control grant, original-owner execution, bounded admission, no implicit retry or toggle inference |
| ESP-NOW | Exclusive radio owner, verified Wi-Fi transition/restoration, key/counter volume access, original power/USB integration |
| Display/touch | Original foreground ownership; no background display grant |
| User storage | Mount/device/USB revalidation, symlink/space checks and drain-before-unmount; no system-path fallback |

Existing player close/drain and XNOW restoration code are adapter inputs, not
complete implementations of this contract. Current managed XNOW retains the
foreground dependency until restoration; resident operation is not permitted by
merely adding a task flag. Player's current source module has no installed
complete service. Preserve both limitations during migration.

## Implementation and acceptance order

1. Implement an allocation-bounded lifecycle core with fake providers: transitions,
   grants, generations, deduplication, overflow/resync and close receipts.
2. Define bounded local IPC and manager authority transfer. Test client death,
   provider death, slow readers, cancellation races and manager restart.
3. Adapt player read/control paths without changing audio processing. Verify
   native threads and unavailable-source revocation before advertising grants.
4. Find and verify original resident/power/USB hooks; then adapt XNOW ownership.
   Do not weaken existing foreground restoration checks to make a demo work.
5. Build Wireless Remote using task attach/start/stop and real state queries.
   Enable only granted capabilities; default off, boot-scoped, no autostart.
6. Qualify exact builds on hardware: original playback, repeated page open/close,
   HOME, USB, sleep/wake, app kill, task failure and resource restoration.

Host/ARM models establish core/ABI behavior only. Hardware qualification and
firmware installation remain separate, explicitly authorized activities. No
step is complete merely because its public header compiles.
