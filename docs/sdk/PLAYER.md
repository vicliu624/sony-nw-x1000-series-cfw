# Player SDK implementation status

This is work in progress, not an available native player service. The unreleased player-client module exposes its client source API; it does not
change firmware, published SDK archives, application pins, radio protocols or any
player files. No stock-device command transport has been enabled.

## Current development support

| Capability | Source implementation | Verification boundary |
| --- | --- | --- |
| Play/pause, next/previous, volume step | Native original handlers and remote client connected | Original instruction fixtures; no physical acceptance |
| State, current ID and volume changes | Original snapshots, validity masks and polling | Offline native/state cases and cross-process client |
| Title, artist and album | Original Moma reader, background cache and local IPC | Original registry/ABI fixtures; live metadata untested |
| Default songs | Native bounded search -> asynchronous broker -> SDK browse | Native instruction and combined host IPC tests |
| Named lists and members | FORMAT3 hierarchy connected as a development prototype | Classification/SonicStage semantics remain unqualified |
| Current playback queue | Matching-session Met capture, exchange, native reader and broker adapter connected in analysis build | Composite full-runtime/device and grouped ordering remain unqualified |
| Arbitrary track selection | Native descriptor move and source admission mapped; PLAY_ITEM remains unsupported | Complete GUI/error/consumer lifecycle remains unqualified |
| Position/duration | Contract fields only; native valid bits remain clear | Units/observations remain unqualified |
| SDK source module | Public player-client headers and dependency graph | Independent clean source-bundle build/ARM consumer |
| Original-player startup | Owner anchor, wrapper and composed ELF prepared offline | No installation, full GUI boot or device test |

Use PLAYER_CLIENT.md for the public API. Native code remains C/C++ and necessary
ARM assembly. An existing no-device-execution restriction is not lifted by any
of the offline tests below. A complete SDK/platform qualification still needs
the outstanding semantics and runtime/device checks; a green component test is
not a completion claim.

## Required capability

The final SDK must control the existing Sony player (play, pause, previous/next,
volume and track selection), report real state/track metadata and browse the
stock library, named playlists and current playback queue. These are separate
objects; a directory listing or a parsed file tag is not proof of a stock queue.
Current-track metadata should follow the stock player, including non-ID3 formats.

## Implemented core

runtime/platform/player contains a C client/provider contract and implementation.
It is intentionally internal until a real stock provider is established. The player-client source module is now exposed with an explicit absent-service
boundary; no original-player endpoint is installed by SDK setup.

- Control distinguishes completed from accepted; it does not infer a state change
  from a successful send, toggle state speculatively or retry a skip command.
  UNCERTAIN is distinct from rejection when execution/delivery cannot be known;
  it must not cause an automatic next/previous retry.
- Snapshots explicitly identify valid fields. Unknown is distinct from paused,
  empty title and zero volume. Invalid provider output does not change caller data.
- Polling reports state, track, metadata, position, duration, volume and catalog/
  queue revision changes. Loss of observation returns an error; recovery emits a
  full initial notification. It is snapshot comparison, not a lossless event log.
- Separate library, playlist-container, playlist-member and queue views use opaque
  IDs. Pages hold at most16 entries. Revision mismatches return STALE without
  committing partial rows. No paths or UI row numbers are used as track identity.
- Metadata is bounded UTF-8. IDs are bounded printable ASCII. Unsupported controls,
  invalid pages/strings, reentrant calls and uncertain close are explicit errors.
- Fixed caller-owned state, no allocations, threads, persistent writes or sockets
  are introduced by the core. Providers must be trusted; this is not a sandbox.

Caller/provider objects must be zero-initialized before first binding. A provider
runs synchronously and must return promptly; a long native transaction will need
its own bounded worker. The modeled provider in tools/fixtures/sdk_player.c is
only a test. It cannot control a Walkman and must not be substituted for one.

Run tools/test_sdk_player.py for host ASan/UBSan and original-libc ARM926 fixtures.
They check accepted-versus-completed behavior, notification changes, observation
failure/recovery, stale page atomicity, malformed metadata and failed close.

## Original-binary findings

The pinned stock SpiderApp SHA-256 is
80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85.
The rootfs and original libc identities remain in KNOWLEDGE.md.

REA6.5.0/Ghidra analysis locates the AppWrpGetVolume string at0x416060 and its
reference at0xb2660. Disassembly identifies wrapper0xb2630 calling0x32a684.
The latter checks process initialization, uses an internal pthread mutex and
reads process-global state. It is not a standalone interprocess volume getter.
Its adjacent setter validates a30-step limit, but this does not qualify every
output mode or provide authorization to write a mixer or cached state directly.

The original image exports MomaClient_getRootObject/getChildren/searchMediaObject,
MomaMediaObject_getMetadataSet and metadata conversion helpers. Their existence
is an analysis lead, not evidence of a separately linkable library or a live
external-client endpoint. The MetRawPlayer/MetTrackInfo strings point to the
original playback and metadata subsystem inside SpiderApp.

Existing Responder database research establishes a default /contents/MTPDB.dat
path and a conditional /db/MTPDB.dat override. Actual initialization selection and
the music-open chain are not qualified. Do not open SQLite read-write, refresh a
library, recreate an index or assume user-storage ownership from a path string.

## Read-only database ABI probe

The original image contains SQLite3.6.6.2, with sqlite3_open_v2 and authorizer
support (library SHA-25641f58a3490919b88fe6683e20bee818ac4e9e3e9bc17ce4106b917df5309fe4c).
The matching libdl and LinuxThreads dependencies are required; using the modern
cross sysroot's libdl is not an equivalent binding.

tools/test_player_sqlite_ro.py executes the original library with Sony libc under
ARM926 QEMU against a synthetic database. Read-only open refuses creation and
updates; an authorizer separately rejects writes. Ordered reference-row queries
complete, and the database hash remains unchanged with no journal created.
The fixture explicitly uses _exit after sqlite3_close: QEMU user mode rejects the
legacy LinuxThreads manager clone, and normal process teardown otherwise hangs.
This limitation is recorded, not hidden by replacing the original thread library.
It does not qualify live /db access, actual model selection, original metadata
IDs or stock playlist/queue interpretation.

## Private in-process bindings

stock_image.c checks the loaded ELF identity with dladdr and hashes the relevant
original code/table spans before any fixed-address call. It rejects independent
executables and incompatible images. This is a compatibility guard, not a sandbox.
stock_volume.c binds original AudioC getters and relative volume adjustment with
thread affinity. Direction0 increases and1 decreases; the original manual,
preset and AVLS behavior is retained. A downstream apply error can occur after
Sony updates its cached volume, so that outcome is UNCERTAIN and is not retried.
The12 original-instruction cases in tools/test_stock_volume_host.py cover both
directions, limits, preset/AVLS, apply failure and identity/thread rejection.
Hardware output and mutex dependencies are modeled in those cases.

stock_gui.c implements a strict original Audio-component activity query. The
16-byte request has code0x440019 and a pointer to a32-bit output. Missing actors,
unready states and handlers which do not write an output return UNAVAILABLE,
rather than the ambiguous zero returned by Sony's convenience wrapper. This is
component activity, not PLAYING/PAUSED. tools/test_stock_gui_host.py executes the
original dispatcher, FSM and final receiver across all17 original states, plus
filter, identity, affinity and reentry failure cases. The caller still needs an
in-process service running on the original GUI owner thread; none is installed.
tools/test_stock_host_refusal.py uses the actual Sony loader/libdl to verify both
bindings refuse an independent executable without entering original code.

The GUI publisher at0xa57f0 is not a general cross-thread API. Its apparent
lock/unlock/signal helpers at0xa6c9c/0xa6dec/0xa6c18 manipulate software counters;
they do not establish a pthread mutex or kernel wakeup. The synchronous FSM
at0x17c608 changes the actor's transient handler index. An external SDK worker
must not dispatch into it or publish commands assuming these counters provide
thread safety. An actual owner-thread service/pump remains required.

The original GUI main loop at0xff04 polls original events, drains the GUI queue
through0x106c8, runs post-processing/render stages and repeats. The queue drain
calls0xa5914 with a nonblocking argument0, builds the16-byte frame and routes
Audio-family messages through0x155d0. The empty0xa6968 function is called after
the render stages, with only0xff04 reported as a resolved caller. This is a
candidate owner-loop integration point, not an installed hook or proof that all
sleep/USB paths keep pumping. Its no-op body also means there is no imported
usleep at this point to interpose. Preserve this distinction when selecting the
actual service bootstrap; background dispatch is not an equivalent substitute.

## Original command construction

The software Audio requests0x440028/0x440029 select the next/previous handlers
only in mode1/state5 or mode2/state2. In every other state they select NoOp.
The next handler reaches0xadd34 then0x27dacc, whose original logging identifies
nextTrack; the previous handler reaches0xadea4 then0x27db98 (prevTrack).
These request values are not evdev key codes. The handlers discard lower-level
controller return values, so dispatch success cannot confirm command acceptance.

stock_gui_skip now binds these two software requests on the serialized original
owner thread. It refuses transitional states, absent controllers and reentry
before dispatch. It observes the original audio wrapper's ticket at0x6922d8+0x10:
a fresh, non-sentinel ticket returns ACCEPTED; unchanged or sentinel values
return UNCERTAIN. It does not write a ticket, toggle playback, retry, or claim
completion. Even an allocation failure can leave the original GUI FSM in its
next state, which is why an ambiguous result is not a safe retry instruction.
The binding additionally hashes the original wrapper/controller code spans.
The24 skip cases in tools/test_stock_gui_host.py cover both directions in both
stable modes, controller allocation failure, unchanged tickets, filter rejection,
transitional states and absent controllers. Original GUI handlers, request-copy
and controller enqueue instructions execute. UI entry/exit, logging, selector
validation, allocation and synchronization/wakeup dependencies are modeled.
These are offline admission checks, not playback-completion or device tests.

The lower changePlayState interface0x27d6a0 calls0x27c890. Next/previous construct
message types0x15/0x16 through0x27cbdc/0x27ccd0. Payloads are copied into the
allocated controller message; the previous-track options include1,1000,1,1.
The enqueue function0x27c3e8 assigns a sequence and queues the message under the
controller's own synchronization. Its return is an admission ticket, not a
playback-completion notification. Do not map state arguments1/2 to public play
states: they are request selectors, not a current-state observation.

The request consumer0x27b1b8 reads the optional target from the copied options
and publishes it through0x276c78. The original apply routine0x27a5fc reads the
locked data snapshot: target1 enters the pause executor0x278da4, whereas target0
reaches raw play0x277c00 after preparation. Thus the GUI mode1/state5 handler
uses request2/options(1,1) to pause; mode2/state2 uses request1/options(0,1) to
resume. tools/test_stock_playstate.py replays the original consumer and apply
branches for both options. FSM/data operations and raw playback boundaries are
modeled; this does not establish engine completion or an observed play state.

stock_gui_set_playing supplies an explicit desired transport state through the
original0x440027 request. It does not blindly toggle on repeated commands: if
the stable GUI mode already selects the requested target, it returns ACCEPTED
without dispatch. That result means the desired GUI mode is already selected,
not that audio output has been confirmed. Opposite stable modes dispatch once
and use the same admission-ticket check as skip. Transitional states return
BUSY; no implicit retry or inferred snapshot update occurs. Public state
notifications still require the actual engine/acknowledgment path.
The14 transport scenarios in tools/test_stock_gui_host.py execute both original
stable-state transport handlers through request admission, including failures and
already-selected targets. The same modeled dependency limits as skip apply;
transport-selector validation is also modeled. Source-buffer target semantics
are separately checked by tools/test_stock_playstate.py.

tools/test_stock_audio_requests.py executes original validation, payload copies
and enqueue instructions for state arguments1/2 and next/previous, including
invalid options and allocation failure. It checks that source-buffer changes do
not alter queued payloads, validates software-request tables and confirms failed
requests do not enqueue or wake a worker. The allocator, mutex/ticket primitives
and worker wakeup are modeled; playback and notifications are not exercised.

## Private provider composition

stock_provider.c/.h connect the real C client contract to the original GUI,
AudioC and owned CtrlInfo adapters. xw_stock_player_bind binds all three on one
owner thread; an incompatible later adapter unwinds earlier bindings. Failed or wrong-thread
close retains the client so its owner can close it later. The command mask
contains play, pause, next, previous and single-step volume only. Absolute volume
and play-item remain unsupported. No socket, worker, storage write or bootstrap
is introduced by this composition.

Snapshots mark VOLUME valid and add TRACK when a supported current local-media
identity can be copied from owned CtrlInfo. The core reports observed volume
and track-ID changes through xw_player_poll; command admission does not edit the
previous snapshot. Failed CtrlInfo observation or an unsupported/missing identity
clears TRACK validity and the previous ID; recovery produces another track
notification. This reports unknown identity, not a confirmed empty queue.
Stable state is valid only when the owned controller snapshot and original GUI
phase agree as described below. Metadata/position/duration remain invalid.
Library/playlist/queue browsing is unsupported here rather than being
silently replaced with an object-tree scan. The separate catalog reader still
requires its own qualified worker and collection classification.

tools/test_stock_provider.py compiles a C consumer against the actual client
core, stock provider and native adapters. It executes original AudioC and owned
CtrlInfo code and checks volume/track changes, identity loss/recovery, unchanged snapshots after accepted/uncertain
commands, unsupported controls, ownership loss/recovery, close and partial-bind
cleanup. Loader identity, output selection, mutexes, CtrlInfo pool memory/copy,
logging and hardware apply are modeled.
Four additional cases in tools/test_stock_gui_host.py exercise play, pause, next
and previous through this consumer/provider into original GUI request admission.
The provider itself is in-process. The local endpoint below can expose it after
the owner bootstrap is installed; that installation has not been performed.

### Stable original playback state

The provider now combines owned CtrlInfo with xw_stock_gui_read, which observes
the original actor phase and executes its original activity query. The actor
pointer and phase must remain unchanged across that query; reentry, incompatible
phase and changing actors return errors without modifying the caller's view.

CtrlInfo primary0 is not sufficient to report PLAYING: original initializer
0x275df8 writes primary0/substate0 before a track is bound. The provider requires
substate0/error0 plus agreement with the original stable GUI phase. Primary0
with a retained track object and mode1/state5 reports PLAYING. Primary1
with a track object and mode2/state2 reports PAUSED. Primary2 plus an inactive
original component reports STOPPED. The original transport handlers establish
these stable phases: mode1/state5 submits the native pause target, whereas
mode2/state2 submits the native play target; both leave their stable phases
when dispatching a change. Inactive activity alone is not used as STOPPED.

All other combinations keep STATE invalid/UNKNOWN, including controller/GUI
disagreement, pending substate, an error, a missing track object or a busy query.
Volume and a supported current track ID can remain valid independently. The
client core notifies state invalidation and recovery; admission of a command
does not set an observed state. STOPPED does not imply an empty library/queue.

The stock-provider ARM fixture exercises paused/playing/stopped observations,
mismatched phases, pending/error states, the default target without bound objects,
busy handler refusal and recovery notifications. Original CtrlInfo clone/release
and GUI query instructions execute; their input objects/phases and synchronization
dependencies are synthetic. GUI-view cases also inject actor/phase changes during
the original query and check atomic refusal. This qualifies the conservative
mapping offline, not physical audio output, sleep or USB coexistence.

Chapter information is optional and does not gate PLAYING/PAUSED. An earlier
private draft called CtrlInfo+100 a sequence and incorrectly required it for
state validity. The original pool label at0x499068 and source path at0x499078
identify it as MetChapterInfo. That draft condition has been removed; both the
info-reader and state-transition fixtures now cover absent chapter information.

## Owned original status snapshots

stock_info.c/.h bind the original CtrlInfo getter at0x27d4e4 and release at0x275f48
on the serialized original owner thread. The getter resolves the existing audio
controller handle from0x6922d8, finds its session and clones the current CtrlInfo
under the data mutex. This does not register a replacement observer or alter the
original UI callback. The source lookup0x27b5a4 retains the session;0x27b7f8 drops
that reference after the clone. Missing sessions are not created by this path.

The104-byte CtrlInfo clone copies the92-byte scalar record and retains its
track and optional chapter objects. Original release drops both references and returns
the clone to the pool. The reader copies scalars only and releases the owned
object before returning; borrowed original pointers never escape. Its current
view exposes raw primary/substate/error, raw position/length, object presence and
supported local-media identity. The raw reader does not itself assert a play state
or timing unit. The provider combines control fields with the separate GUI
observation above. The raw provider leaves metadata invalid; the broker below
merges values obtained by the separate native-Moma reader thread.

The existing UI callback0xad39c reads CtrlInfo through original accessors:
offset4 is the selected primary target, offset8 the substate, offset12 an error;
offset44/48 feed position/length handling; offset96 is retained TrackInfo and
offset100 is optional MetChapterInfo, unrelated to the playback queue.
internal2subState at0x27b004 maps
native FSM states1/2/0x40 to0, states4/8/0x10/0x20 to1 and0x80 to2. This is why
a primary target alone must not be treated as observed engine playback.

tools/test_stock_info.py executes original session lookup/reference release,
locked CtrlInfo cloning, and track/chapter retain/release. Across1000 reads,
clone allocation/free counts match and all three retained reference counts return
to their original values. Other cases cover absent objects/session, allocation
failure, an unbound controller, wrong thread and incompatible code. Pool memory,
mutexes, memcpy and error logging are modeled; no live controller or metadata
interpretation is qualified. The Sony-loader refusal test covers this reader too.

For the next metadata binding, original0x28066c first checks the retained
TrackInfo's type tag against MetMmTrackInfo, obtains its implementation through
0x27eb58 and returns the implementation's field at offset4. The original UI
clones that result with MomaObjectId_clone before retaining it. This is the
current-object identity lead; it must be copied/formatted while the owned
CtrlInfo is alive. No borrowed TrackInfo/Moma pointer should enter SDK snapshots.
The reader now copies the original local MEDIA serialization into caller-owned
storage before releasing CtrlInfo. It checks the MomaLcObjectId class at0x60fc60,
accepts only domain0/1 and typeMEDIA, and reproduces0x28d64c's lowercase hexadecimal
format. The longest supported ID is60 bytes. Other domains, metadata-key IDs and
other track types remain invalid, without substituting an address or UI index.
The generic constructor0x299274 establishes class/implementation layout; the
local constructor0x28d704 selects that class and the native formatter identifies
DOMAINALL/FOLDERTREE and MEDIA fields. Tests cover zero/max IDs, both domains,
relocated ID objects, unknown classes/types and unchanged reference counts across
1000 reads. Library browsing must still establish how to return the same identity
for its rows; the independent raw catalog reader is not silently treated as that
binding.

local_identity.c/.h centralize the native local MEDIA format and strict parse
rules. Only DOMAINALL/FOLDERTREE, lowercase non-padded hexadecimal and32-bit object
values are accepted. Malformed or different-domain IDs do not change caller
outputs. tools/test_player_local_identity.py runs4014 round trips and malformed
cases under host ASan/UBSan and original-libc ARM, including zero/max values,
leading-zero/uppercase/overflow refusal and an unterminated fixed buffer.

## Native catalog reader and profile evidence

catalog_ro.c/.h now implement actual read-only SQLite object-tree pages, not a
modeled provider. Each page owns and closes its database connection and guard
file. Caller output commits only after query, identity and revision checks and
cleanup succeed. Ownership denial, interruption, stale revisions and incompatible
schemas return errors with no partial caller rows. Strings retain UTF-8 boundaries
and explicitly report truncation. No live queue or automatic music-only view is
claimed by this component.

The code is private to a future dedicated worker process. It must have one owning
thread and no other SQLite connections to the same database. Never load it into
SpiderApp: closing an independent guard descriptor can release same-process POSIX
record locks used by existing SQLite connections. The public SDK must isolate this
reader rather than make app authors manage that constraint. No public SDK service
is registered until that integration and the stock control path are available.

Pinned original table data contains ARTIST key2 / storage tag s and ALBUM key3 / s.
REA identifies the schema initializer at0x29d71c: prop_type1 generates m<id>_id
columns directly from meta_id; prop_type2 generates u<id> user fields. The original
query builder at0x2a7528 uses those m<id>_id references. The reader therefore checks
prop_type1, meta_id2/3 and data_type0x73 before using m2_id/m3_id joins. Unknown
profiles fail instead of interpreting equal numeric keys in a different group.

The original schema uses reference_id plus child_index to store referenced members
and their order. The reader returns both membership and referenced object IDs, and
joins referenced title/artist/album fields. This does not establish that every
container is a playlist or that catalog order equals the current player queue.

tools/test_player_catalog_ro.py exercises original Sony SQLite and libc under ARM:
reference joins, stored order, UTF-8 truncation, malformed metadata, incompatible
key/group/storage types, stale pages, ownership loss and stop. Synthetic database
hashes remain unchanged and database opens are checked for O_RDONLY. Live catalog
selection and all supported content domains still need verification.

### Direct media metadata lookup

xw_catalog_ro_object reads a single raw object with the same transaction,
read-ownership, file-identity, revision, schema, reference join and UTF-8 checks
as pages. The common read path closes all handles before committing output.
Missing rows, corrupt text, stale revisions and ownership loss do not change
the caller's record or revision.

The local MEDIA identity mapping is supported by original-code evidence:
0x28c40c obtains the object value through0x28d750 and passes it through0x28c0dc,
0x2950ec and0x29f9c8 to0x2a417c. That routine builds a field0/uint32 predicate.
The pinned schema row at0x6105a4 names field0 object_id;0x2a6b30 chooses
obj.object_id. tools/test_stock_local_id_query.py replays the predicate and
column-selection instructions for small, high-bit and maximum IDs. Condition
allocation/query execution, table search and formatting are modeled. Object0 is
handled separately as the synthetic root by the native plugin.

xw_catalog_ro_media parses a supported original MEDIA ID and reads its title,
artist and album into an xw_media_item. A reference resolves to a real media row
under the same expected database revision; an orphan, container or corrupt target
fails atomically. The returned ID remains the originally requested canonical ID.
XW_MEDIA_*_PRESENT flags distinguish missing values from empty stored strings;
XW_MEDIA_*_TRUNCATED flags identify bounded UTF-8 truncation. Duration is not
inferred. This component belongs in the dedicated reader process, not SpiderApp.

This direct SQLite component remains private/offline; the runtime below uses
the original Moma API and does not open/close Sony's database files itself.
The original-SQLite ARM fixture covers raw objects, canonical media IDs, reference
metadata, title-only records, orphan refusal, malformed/stale IDs and incompatible
schemas. Database hashes remain unchanged, opens are O_RDONLY and no journal is
created. This is not yet wired to the in-process provider or an external SDK
endpoint; actual device path/schema and read ownership still need qualification.
The eventual asynchronous service must match returned metadata against the
current canonical track ID and catalog revision before merging it. A completed
lookup for an earlier track must not populate a newer track's snapshot. This
reader resolves the requested identity; it does not assert what is now playing.

## Reviewable read-only diagnostic

Run tools/build_player_inspect.py to build
work/player-inspect/player-schema-inspect.arm and its REVIEW.md/build.json. It is
not an SDK backend, installer or firmware package. Safe --help/--version paths do
not inspect databases. The production diagnostic only accepts these explicit
commands:

```sh
./player-schema-inspect.arm --inspect /db/MTPDB.dat
./player-schema-inspect.arm --inspect /contents/MTPDB.dat
```

Each invocation selects one path; it never falls back automatically. SQLite opens
read-only, rejects write SQL through an authorizer and limits query instructions.
Output contains table shape and at most128 property definitions, with bounded
property names; no song content or personal song metadata is queried. It writes
stdout only. The fixture confirms the database remains unchanged and omits a
seeded private test title. Device copying/execution requires separate authorization
under AGENTS.md and has not been performed.

## Native-Moma metadata reader and broker

stock_media.c/.h now implement a read-only original-API path. On the GUI owner,
0xab4f4 supplies the existing connection token used by the original sequence
factory0x283830. A new MomaClient connects through that token. Both readiness checks and client creation reject a nonzero token type or a null manager before allocating a client; readiness alone is not a lifetime guarantee. The background
reader reconstructs a supported local ID, requests TITLE9, ARTIST0x0b and
ALBUM0x0c through original get-object0x295ce8, obtains its metadata set and
copies values before disposing the media object and ID. Closing the per-job
client disconnects/releases its original manager reference. No private SQLite
connection, guard descriptor or filesystem fallback is used by this path.

The metadata-set pointer is borrowed from the owned object and is never disposed
separately. Original ustr/cstr getters run through their own type checks. ustr
lengths are UTF-16 code units excluding NUL: the original UI0xb8c90 copies len*2
bytes, and setValue_ustr_conv stores converted_count-1. media_text.c converts
validated UTF-16/UTF-8 to bounded UTF-8 without splitting codepoints. Missing and
empty attributes remain distinct; malformed text fails the whole item without
committing a partial result. Source getters/profile are private JP1.11 bindings.

metadata_async.c has one request slot and one background reader. The GUI prepares
an original client and transfers exclusive ownership; fetch refuses the GUI
owner thread. The reader always closes that client after the native call, even
on error. GUI cache operations use trylock and never wait for a database result.
Queued clients can be revoked on the owner; an active native call is allowed to
return and clean up its own references. This does not qualify forced cancellation
or original sleep/USB quiescence, which remain physical integration work.

player_broker.c decorates the original provider. It merges metadata only when the
current canonical track ID and observed revision epoch match the returned item.
Track/revision changes and source revocation invalidate previous intent/results.
Known metadata is refreshed periodically (2s); a failed refresh invalidates it.
When no native catalog revision is available, revision0 remains unknown rather
than becoming a fabricated database generation. The cache is latest-observed
per-item data, not a transactionally frozen library. Revocation and failed native
snapshots clear the cache intent. Client close never closes Sony's player.

The worker's pthread storage is aligned and opaque; original library functions
initialize it instead of relying on modern NPTL layouts/static initializers.
tools/test_player_metadata_async.py and tools/test_player_broker.py use real host
threads with modeled native reads to check stale-ID/revision refusal, refresh,
failure, source-off invalidation, nonblocking drain and balanced clients. The
ARM broker smoke initializes/destroys original LinuxThreads primitives without
creating a thread. Actual Sony worker creation is not qualified by that smoke.

tools/test_stock_media.py executes original connection/client/get-object dispatch
and ustr/cstr getter instructions. It covers Unicode, missing/empty attributes,
truncation, malformed/oversized values, failed allocation/query/connection and
repeated balanced cleanup. Pools, manager/provider guards and projected database
values are modeled. Native accessor arguments, owner handoff and conversion are
checked; a live database or power/resource transition is not exercised.

## Analysis-only owner-loop bootstrap

tools/build_player_host.py now builds a private ARM DSO and an analysis ELF under
work/player-host. It requires the pinned stock JP1.11 SpiderApp. The ELF changes
one instruction at0xff3c: the original call to no-op0xa6968 becomes a call to the
existing getpid PLT entry0xda84. The following instruction, every other original
byte, ELF headers and file size remain unchanged. This is not a firmware/UPG
package and must not be treated as a supported installation profile.

host_hook.c interposes getpid through the standard loader. Ordinary calls delegate
to the original implementation resolved with RTLD_NEXT. Only return site0xff40,
the expected call/following-instruction bytes and a supported loaded image can
activate the anchor. The callee is argument-free: without the DSO, the original
getpid function still cannot interpret incoming registers as output pointers.
Its return value is unused at this original void-call site. Constructor-time
fallback uses the pinned OABI getpid syscall20, not a modern r7/svc0 convention.

The first matched call binds the real stock provider on that thread. Later calls
invoke a bounded owner dispatcher only on the same pthread identity; failed
binding or a different thread does not dispatch. The generic hook retains an
inert weak dispatcher for isolated tests; the current DSO builder links the
strong host_service.c local-endpoint dispatcher and metadata broker. No startup
wrapper or preloading configuration is installed by this build. The current
build.json records file, load-segment and BSS sizes. These are
ELF measurements, not filesystem-capacity or flash-safety qualification.

tools/test_player_host_pid.py loads the DSO with the original Sony loader/libc
under ARM QEMU. It verifies constructor resolution, ordinary PID/errno behavior,
the interposed symbol's actual DSO identity and that unrelated calls do not
activate the host. No SpiderApp is executed. tools/test_player_host_anchor.py
executes the patched ARM call and real guarded shim/provider binding, including
wrong-thread refusal, incompatible binding, original/changed images and OABI
fallback. The strong test dispatcher calls the real client snapshot API; stock
AudioC is deliberately uninitialized. Repeated200-tick dispatch cases pass.
Loader identity, RTLD_NEXT, original PLT routing and the kernel PID result are
modeled in that anchor fixture. This does not boot the stock OS or qualify a
live GUI, sleep/wake, USB handoff, firmware capacity or recovery.

## Local client/service transport

rpc_wire.c/.h and rpc_posix.c/.h implement the private local C client and owner
server. The endpoint is a Linux abstract AF_UNIX stream name
sony-x1000.player.v1: no filesystem socket, TCP listener or radio/business
messages are introduced. A connection carries one request and its reply, then
closes. Frames explicitly encode fields in little-endian form; C structure
padding, pointers and enum layout are not transmitted. Strings are bounded and
their bytes after NUL are zeroed. A maximum16-row page fits13504 bytes.

xw_player_remote_bind negotiates a command mask, then binds the existing
xw_player_command/snapshot/poll/media_browse client API to the local service.
One monotonic deadline covers connect, send and receive. Cancellation can stop
an exchange. A lost or malformed command reply after bytes were sent returns
UNCERTAIN; the client never reconnects to retry it. Local close releases the
client context, not the host's original player/provider.

The owner server uses nonblocking descriptors with close-on-exec and MSG_NOSIGNAL,
processes at most one provider operation per tick, and sends at most2048 bytes
per tick. Peer lifetime is bounded; header/body length and sequence checks reject
malformed frames. Reentry and close during dispatch return BUSY. Already-closed
or half-closed peers are checked before dispatch so a complete frame left queued
while the owner was not pumping is not executed later. A disconnect racing with
execution remains an uncertain command result. Clients keep the connection open
through the reply; half-close is not a supported completion signal.

host_service.c connects that server to the tested owner bootstrap and broker
around the real stock provider. It opens the local listener on the first owner
dispatch and pumps bounded IO thereafter. Native metadata reading starts lazily
on a supported snapshot request; that query runs in the background. The raw stock
provider serves controls and its qualified state/track/volume snapshot. The
broker now provides default-track pages through the asynchronous native search
reader when the backend has no browse implementation. The analysis host prototypes playlist views with the FORMAT3 reader; queue
remains UNSUPPORTED; a directory list is never presented as the current queue.

Modern ARM headers redirect scalar fcntl and getsockopt calls through unavailable
time64 adapters. This transport explicitly binds the original symbol names for
F_GETFL/F_SETFL/F_SETFD and SO_ERROR, using no flock/timeval option. Monotonic time
uses the existing two-word original clock bridge. C/C++ linkage guards are
present; this remains private source, not a published SDK module yet.

tools/test_player_rpc.py runs actual separate client/server processes under host
ASan/UBSan (GCC12/O1) and original Sony libc/librt ARM QEMU. It checks explicit wire
fields, UTF-8 metadata payloads, maximum pages, state changes, stale-output
atomicity, cancellation/deadlines, ACK loss without skip retry, abandoned complete
frames, reentry, malformed-peer recovery and cleanup. Its provider is a model,
so those playlist/queue cases qualify transport only. Native-provider and anchor
fixtures qualify their separate original-code paths. No device endpoint is
installed and physical integration has not been tested.

## Remaining work before SDK availability

1. Connect the private owner bootstrap/local endpoint to a reviewed startup
   profile. No endpoint is installed on a device yet.
2. Qualify the already-bound controls/state/metadata/default-track service in the
   actual Sony runtime; the analysis bootstrap alone is not physical acceptance.
3. Decode original stable media identities, playlist/queue ordering and metadata;
   provide bounded read-only browsing with observable collection revisions.
4. Exercise original code paths offline, package a native consumer/example through
   the public SDK and run clean-source bundle checks. Pure provider tests do not
   satisfy this step.
5. Keep physical acceptance separate: original playback plus background service,
   HOME, sleep, USB and radio coexistence require appropriate device verification.

No raw process-memory writes, synthetic key injection, guessed command IDs or
fixed-address calls from an independent executable are enabled by this work.


## Native list ABI under investigation

The pinned image exports MomaClient_getChildren at0x295d38 and
MomaClient_searchMediaObject at0x295de4. The former routes to0x296ca8,
which takes a native object identity, obtains its domain through0x299610,
acquires the existing manager/provider guard through0x29661c, invokes the
provider slot at+0x30, and releases the guard through0x29672c. This is not
an established SDK query signature: the remaining stack arguments and their
semantics must be traced through original callers before use.

MomaMediaObjectList_getNext at0x298328 forwards three registers to provider
slot+0x0c; on a nonzero result it explicitly clears the third argument's
output pointer. MomaMediaObjectList_dispose at0x29829c dispatches slot0 and
accepts a null list without invoking the provider. The original-instruction
fixture tools/test_stock_media_list.py verifies those wrapper properties with
modeled callbacks. An additional replay of the original consumer loop at0x27fe78
reads three modeled rows, calls its consumer with each borrowed identity,
disposes every media object at0x27fe68, and disposes the list at0x27fe34.
The loop maps0x2202 to normal completion at0x27fe1c. The second getNext argument
is the caller context carried in r10 (zero in the replay), not a qualified batch
size. Native provider internals, query argument meanings, playlist classification
and real database pagination remain incomplete. Do not claim this wrapper alone is a hardware-qualified browse backend.


The nine-argument client ABI is now confirmed by REA and an original-instruction
forwarding replay: client, cancellation context, parent identity, predicate,
start index, requested count, projection mask, sort, output list. The manager
adds its provider and admitted-domain value before dispatching slot+0x30.
The fixture checks all register/stack arguments independently and verifies guard
release on success and0x106; error output is cleared. It does not execute the
real database provider.

The local provider path is0x28c538 ->0x28db04. The latter clones its parent
identity/domain and builds a projection, then takes an optimized query path
through0x294bd8 ->0x2954c8 ->0x2a0818 ->0x2a5ad4, or a generic path through
0x295154 ->0x29fcec ->0x2a3e30 ->0x2a39a4. The optimized builder binds
@startIndex=start+1 and @endIndex=start+count. A zero requested count removes
the upper bound; it must never be used as an empty SDK page. The generic
builder passes the same start/count pair to0x2a1b40. SDK calls must retain
the existing positive bounded page limit and check start/count overflow before
calling the native interface. Runtime integration and classification remain
outstanding; these findings alone are not a completed media browse service.


## Private bounded native child reader

stock_media.c now implements xw_stock_media_children using the qualified
nine-argument MomaClient_getChildren call, a null cancellation context, no
predicate/sort override and the existing title/artist/album projection.
The caller supplies an explicit supported local parent identity, start index
and positive count up to16. Values exceeding signed native index arithmetic
are rejected before allocation or native dispatch. The reader adopts the same
exclusive background-thread ownership as current-track metadata fetch.

Each returned native media object is copied to bounded UTF-8 and a canonical
local identity, then disposed immediately. The parent identity and result list
are disposed on every completed/error path. A staged page is committed only
on success.0x2202 marks exhaustion; an exactly full page does not claim that
more rows exist or that the list has ended. Zero count never reaches Sony.
A partial read/cancel/text error preserves the caller's old page.

The original-instruction media fixture now covers empty, partial and full
pages, mid-page cancellation, malformed text, invalid limits and signed-index
overflow, in addition to the metadata cases. The manager admission/list
provider/pools and projected row values remain modeled. Native callbacks,
UTF getters and the new C reader execute. No device database was accessed.
This is a raw local-child primitive; public browse classification, revision
consistency, asynchronous browse scheduling and current queue are not completed.


## Asynchronous native child pages

xw_children_async shares metadata_async.c's existing thread/lifecycle machinery
through a dedicated instance, rather than creating a second implementation of
Sony pthread handling. The owner prepares the client; its worker reads and
closes it. Only copied pages survive. Query parent/start/count, revision epoch,
revocation and monotonic-clock regression invalidate old results. The owner
uses trylock and never waits for a running database request. A running job is
allowed to finish and release its client; it is not force-cancelled.

Successful pages with a caller-qualified revision remain cached for that epoch.
Revision0 is explicitly unknown and expires after two seconds; this refresh is
not a cross-page consistency guarantee. Native errors are returned separately
from pending reads and never commit partial pages. Source-off integration must
revoke intent before cached pages may be used. The worker is not connected to
public browse classification yet and must not claim a real playlist/queue view.

The real-host-thread fixture checks changed-page stale-result rejection,
invalid limits, native error propagation with unchanged output, unknown-revision
cache expiry, revocation, nonblocking shutdown and balanced client lifetimes.
Original Sony pthread primitives and the ARM build are separate ABI evidence;
actual Sony thread creation, sleep/USB handoff and live catalogs remain untested.


## Original default-track predicate

The UI request constructor0xacc9c takes an existing list descriptor and passes
its domain/predicate/sort into the Met sequence factories. The default local
track descriptor at0x3f0d8 uses domain getter0x40eac, predicate-storage getter
0x47b3c plus200 bytes and original sort selector0x471c4(0,1). The predicate
is initialized by0x47cac, not a guessed directory filter. Its five-node tree
combines original scalar predicates (operation1, kind9) on key0/value0,
key1/value1 and key0xfe130001/value1 using operation9 binary nodes.
The numeric keys are preserved without inventing their user-facing semantics.

stock_query.c builds that exact ARM32 predicate in caller-owned storage, with
no allocation and root nodes[4]. tools/test_stock_library_predicate.py executes
the original initializer prefix and its actual predicate helpers, normalizes
pointer addresses recursively, executes the new ARM builder and compares the
whole resulting tree. No helper semantics or database values are substituted.
This qualifies the default predicate, not its domain/sort binding, named
playlists or a completed public track browser. Source predicates must remain
alive through the synchronous native search call and its list lifetime until
ownership/copy behavior is qualified.


The native field registry is an independent semantic check: original table
entries at file offsets0x494bcc/0x494bd8 associate0x0b/0x0c with
MOMA_METADATA_KEY_ARTIST/ALBUM and type11 (USTR).0xfe130002 and0xfe130003
are TITLE_INITIAL and TITLE_SORTSTR, not artist/album. The earlier private draft
used those wrong fields and its modeled row fixture did not detect the mistake.
The reader and fixture are corrected; test_stock_media.py now resolves the
original registry names through ELF mappings and checks the key associations
before exercising any projected rows. This draft was not deployed to hardware.


## Native default-track search

The private child-page query now distinguishes raw children from the default
local-track search (XW_STOCK_TRACKS). Track search obtains its own original
FOLDERTREE domain through MomaClient_getDomainId0x295b48 with the exact original
30-byte domain name, not a borrowed UI-global pointer. It calls original
searchMediaObject0x295de4 with the qualified predicate and ascending default
sort (TITLE_INITIAL0xfe130002, TITLE_SORTSTR0xfe130003, TITLE9). The sort builder
is compared against the original initializer's sort at base+0xa88, alongside
the predicate comparison. The domain is released after disposing the list;
all row copies use corrected ARTIST0x0b and ALBUM0x0c projection fields.

The native fixture covers default-track pages, domain lookup failure, mid-page
cancellation, malformed text and full-page results. Original client/domain
forwarding, manager search dispatch and list wrappers execute; actual domain
registry lookup/disposal and database provider rows remain modeled. The async
request key now includes query kind so a children page cannot satisfy a track
search merely because parent/start/count match. Public browse integration,
qualified catalog revisions, playlists and the actual playback queue remain
unfinished. No firmware or hardware behavior is qualified by these tests.


## Broker and local endpoint track browsing

The broker falls back to the native default-track reader only when the backend
returns UNSUPPORTED, for the TRACKS view with an empty container. Other backend
results are preserved. It checks original source readiness and snapshot revision,
then submits a bounded asynchronous request. Pending reads return BUSY without
changing caller rows/page. Unknown source state returns UNAVAILABLE and revokes
cached intent; owner ticks also revoke on source-off. Close stops and drains
both reader instances before destroying them, leaving the original backend open.

The core/page contract now explicitly accepts revision0 as unknown, matching
snapshot semantics. A nonzero expected_revision cannot match an unknown version
and returns STALE. No refresh timer or request-generation value is presented as
a database revision. Total count stays unknown rather than inventing it from an
empty page beyond the end. Unknown-version pages have a two-second cache lifetime;
separate pages may see library changes, so callers needing a consistent snapshot
must refuse unknown versions. This limitation is explicit, not a consistency claim.

The local endpoint is already wired to this broker in host_service.c. Tests cover
core unknown-revision acceptance/stale refusal, native-search broker paging,
BUSY/error output atomicity, source-off cache invalidation, independent reader
shutdown and unsupported playlist views. Separate-process host/old-libc ARM IPC
fixtures verify unknown-revision pages survive transport and expected versions
still fail. Native reads in the broker fixture and all IPC collections are models;
the real native-reader instructions have separate tests. Nothing is installed on
a device; public SDK source-bundle publication and runtime acceptance remain open.


## Named-playlist boundary and query mapping

Sony's Japanese NW-X1050/X1060 operation guide, page45, identifies its playlist
search as SonicStage-created playlists. This is independent of NWZ playlist
formats and must not be replaced by a filesystem .m3u scan. Primary reference:
https://www.sony.jp/ServiceArea/impdf/pdf/41416090M-JP.pdf (the live URL currently
redirects; Sony's indexed Japanese page45 excerpt retains this description).
The six methods listed there are all songs, album, artist, genre, release year
and playlists. This confirms required behavior, not the binary query selector.

Original list initialization0x470f0 reads per-view records from0x4e5ae8 at a
128-byte stride.0x46d74 selects that view/depth's condition index, then resolves
it as0x66e158 +8 +index*32, with explicit special cases for indices0x28,
0x38 and0x4c. The zero-depth music-view record5 selects index0x27, resolving to
base+0x4e8. Original initializer0x47cac builds that predicate through0xb6bb4:
operation1, key2 (MOMA_METADATA_KEY_FORMAT), kind9, value3. This is not the
GROUP predicate previously considered as a possible playlist discriminator.
tools/test_stock_library_predicate.py now executes the original0x46d74 selector
against the actual initialized global condition storage and original static
view table, confirming view5 selects this exact FORMAT3 predicate and advances
the depth once. No table lookup or condition-selection helper is modeled.
The UI label association and native playlist member ordering are still to be
qualified; do not expose this candidate as a completed PLAYLISTS backend merely
because it is a music-view format filter.


The view5 second-depth mapping and member sort are now original-instruction
verified. Its depth0 condition is FORMAT3; depth1 is OBJECT_TYPE0. The static
sort selector0x471c4(5,1) selects sort0 (the existing title ordering), while
0x471c4(5,2) selects sort13 at initialized base+0xdfc: key0x22 ascending.
The original metadata-name registry explicitly names0x22 CHILDINDEX. This is
member ordering, not alphabetical title order. stock_query.c's private
xw_stock_list_query_build constructs both conditions/sorts in caller storage.
The fixture executes both depths of the original selector, reads the original
sort mapping and initialized sort records, verifies CHILDINDEX's registry key,
and compares the new ARM builder results. It does not model those semantics.
The remaining label association and parent/member query routing are still
explicitly open; no unsupported PLAYLISTS view was enabled from this evidence
alone. Original Japanese STX entries22/64/501/3071 read as the playlist label;
resource index identity alone does not establish a menu/query association.


## Original parent-query routing

The UI's0xaaef8 adapter accepts13 arguments: client, cancellation context,
domain, predicate, aggregation key, start, count, projection, sort, aggregation
flag, child flag, selected parent identity and output list. With child flag set,
it replaces the third argument with the selected parent and calls original
MomaClient_getChildren0x295d38. Without that flag it chooses basic search0x295de4
or aggregation search0x295e90 according to the aggregation flag. The aggregation
key is not a parent identity.0xb8404 derives aggregation behavior from the first
projected property; title9 and filename5 use basic search. These separate routes
must not be conflated when translating the original UI list descriptors.

tools/test_stock_media_list.py now executes0xaaef8 and its original thunks for
all three routes and both success/0x106 returns. It checks domain-versus-parent
selection, predicate, aggregation key, start/count, projection, sort and output
arguments at each actual native entry boundary, and verifies return propagation.
Native query bodies are intercepted only at that boundary; their manager/list
behavior is covered by the separate reader/dispatch fixtures. This qualifies
the generic parent route. It does not yet prove which playlist UI transition
sets the child flag, so it is not a completed playlist-members integration.


## SDK client module

sdk/services.json now exposes player-client, forwarding player.h/provider.h and
player_remote.h/rpc_posix.h through public service headers. The source closure
contains only core client/wire/local IPC plus clock-libc and original pthread;
it excludes stock GUI/media bindings and owner bootstrap. The dedicated external
consumer compiles through sdk_services.compile_native, executes under original
libc ARM926, checks cancellation and closed-state behavior, and passes C++ header
syntax. package_sdk includes this test and the clean-bundle test invokes it.
See PLAYER_CLIENT.md for the native-services contract and honest support matrix.
This is an unreleased source change under the current development SDK identity;
no existing published archive, installed application or firmware is changed.


## Analysis-only PID-preserving startup wrapper

stock_exec.c supplies a standalone C wrapper for a future reviewed startup
profile. Its fixed production paths are SpiderApp.stock and the system player
DSO. It preserves argv/environment and calls execv directly; it never forks,
suspends Sony, starts a daemon or writes storage. A readable player DSO is
prepended to LD_PRELOAD while preserving any existing entries; exact existing
tokens are not duplicated. Missing library or allocation/setenv failure leaves
the original environment and continues to the original executable. An exec
failure returns127 rather than starting a replacement process.

The test compiles against original Sony libc and runs the ARM wrapper under
QEMU, then actually execs a statically linked host observer. The observer's PID
must equal the process originally launched by the test, and argv/environment
must survive. Cases cover absent/readable library, no previous preload, existing
same/different preload and duplicate/colon/space-separated entries. The inert
ARM fixture DSO uses SysV hashes for the original loader. Existing original-loader
PID/anchor tests separately cover the actual service DSO.

This is a wrapper/exec ABI proof, not a SysMgr integration proof: the target is
an observer, not SpiderApp. No source builder installs this wrapper, renames a
player file or changes AppList.conf. Composite language/Homebrew/owner-hook ELF
compatibility, capacity, actual startup and power/USB coexistence still require
review before producing any installation candidate. The SDK client module does
not include this wrapper and cannot install or activate it.


## Source-built existing-firmware composition check

patch_owner_anchor in build_player_host.py now isolates the single-instruction
analysis edit. It checks fixed-address little-endian ARM32 EXEC, original getpid
PLT0xda84, the exact two-instruction owner-loop sequence and unchanged ELF/segment
headers. Its caller must still qualify the complete input composition; this is
not a generic patch-any-firmware operation or a device installer.

tools/test_player_composition.py builds the current Homebrew feedback ELF from
source, applies the maintained release's error descriptor edits, and invokes
only add_language_cache (not firmware build/pack). It then applies the owner
anchor and verifies that every other byte matches that composite baseline.
All17 distinct native provider guard spans, plus the owner-anchor digest, match
the constants compiled into the provider. VA-to-file mapping is derived from
each ELF, including shifted data offsets. No language/Homebrew modification is
replaced with a pristine image. The final anchor edit adds zero ELF bytes.

Output is an analysis-only ELF/report beneath work/player-composition. No UPG,
updater, AppList change, player rename or preload installation is generated.
This establishes source composition/guard compatibility only. Native owner
fixtures and loader tests remain separate; full GUI boot, service lifetime,
RF/music coexistence, capacity, sleep and USB require further qualification.


## Original visible playlist menu resource

The pinned stock rootfs contains swd/ucs2-dev-sid-239-00.swd and239-01.swd.
Both bind tid.5 to tid-0501 and tid.6 to tid-0446. Resolving those indices through
the same rootfs's original Japanese STX yields the playlist and folder labels,
respectively. The zero-padded tid notation matters; searching only tid-501 misses
these bindings. test_stock_library_predicate.py verifies rootfs SHA, both SWD
bindings and actual STX labels, and records resource hashes. No hand-written
translation or assumed menu order is used as label evidence. These SWD templates declare type unused, so their labels alone do not prove
an active screen or event binding. This establishes the resource slot only;
its event-to-native-query-view conversion remains to be traced
before exposing the format-filter candidate as a native playlist service.


## Private FORMAT3 hierarchy reader

The native reader has two additional explicit internal query kinds:
XW_STOCK_FORMAT3_LISTS searches the local domain using the verified FORMAT3
condition/title sort; XW_STOCK_FORMAT3_CHILDREN takes a supported local parent
identity and reads its children using the verified item condition/CHILDINDEX
sort. These numeric views underlie the analysis host playlist prototype; its active
menu event association and real playlist compatibility remain unqualified.

Before reading members, the reader fetches the parent with a one-field FORMAT
projection and reads it with the original typed enum getter0x2988f8 (kind9),
not the int32(kind5) or uint32(kind6) getter. FORMAT is independently verified
as key2 in the original name registry. Missing format returns UNAVAILABLE;
non3 format returns UNSUPPORTED; an incompatible stored type returns PROTOCOL.
The parent media object is released before querying its children. Parent ID,
list, each copied child and any domain handle follow existing cleanup paths;
errors do not commit a partial page.

The original-instruction media fixture adds format-filtered list search,
validated child traversal, wrong parent format, missing format and corrupt text.
It verifies actual search/get-object/get-children/typed-getter dispatch and
correct projection/predicate/sort arguments. Row values and provider storage
remain modeled, so no real SonicStage playlist or live membership is claimed.
The async request key preserves these distinct kinds. No public browse support
mask or firmware installation is changed by adding these internal operations.


## Client/owner stack use

The ARM compiler identified large nested local buffers in the initial source:
media_browse13576 bytes, remote_browse13736, response decoding13600 and broker
browse14552. The core now stages browse rows in caller-owned xw_player scratch;
the remote owns a reusable response; the broker owns its copied native page.
No per-query heap allocation is introduced. Response decoding validates every
rejectable field before its first output write, then decodes directly into the
separate caller response. Overlapping packet/response buffers are explicitly
rejected without modification. Malformed snapshot enum and overlap atomicity
are covered by host/original-libc ARM RPC tests.

With the recorded ARMv5/Os compiler flags, corresponding local frames are now
72,200,56 and1048 bytes. All selected client/wire/transport/broker source frames
are <=2048 bytes (maximum1792); test_player_stack.py enforces this at compile time.
This is not a whole-call-chain or original-library stack bound. The native read
worker's larger page staging is separate and not included in the GUI/client claim.

The memory is explicit rather than eliminated: ARM xw_player is14440 bytes and
remote27160, so application contexts must use static/heap storage rather than
small thread stacks. The host DSO's build report records its increased fixed BSS;
this storage is bounded per context, not an accumulating allocation or system
partition write. This source-only context-layout change requires consumer rebuilds;
wire fields/protocol version and command semantics are unchanged. Physical memory
pressure and original thread behavior remain separate validation requirements.


## Read-only type diagnostic prepared for separate authorization

inspect_main.c0.2.0 retains schema-only inspection and adds --inspect-types,
restricted to the same two explicit original catalog paths. It opens SQLite
READONLY, uses connection-local memory temporary storage, authorizes only reads
and COUNT for aggregate mode, and reports object_type/media_type/format/count.
No title, filepath, object ID, playback command, refresh, radio command, firmware
write or persisted log is requested. NULL is printed explicitly. Progress and
128-row limits fail clearly rather than presenting partial statistics as success.

build_player_inspect.py executes original SQLite/libc ARM fixtures for correct
counts, missing values, excluded private fixture names, absent database refusal
without creation and too-many-groups refusal. Database hashes remain unchanged
and no journal is created. The reviewable executable/REVIEW.md remain only under
work/player-inspect; no player copy or execution is authorized by building them.
Device copy/execution requires explicit authorization for this specific
temporary diagnostic; a completed local build is not such authorization.
The aggregate shape helps validate real object formats; it does not by itself
identify a playlist if the user has none or prove current playback queue order.


## Clean source-bundle client qualification

The SDK source package and test_sdk_bundle.py now support a scoped --player-only
validation. The archive is manifest/hash checked and extracted into a new project;
only the pinned Sony installer is provided as a local input. SDK setup prepares
its own original libraries/public dependencies; no previous work/library/tool
artifact is copied into the extracted project. The archived public player test
then builds via the archived SDK service compiler and executes against original
libc ARM926, including C++ declaration checks.

The recorded source-only review archive passes this clean-input test. Its report
is explicitly player-client-only and does not relabel omitted templates, other
services or the full SDK matrix as passed. Default full-bundle validation retains
all existing checks and includes the new player consumer. This is source-package
usability evidence, not original-player endpoint installation or hardware control.
Review archives and their exact SHA/report remain local under dist/sdk-reviews
and work/sdk-bundle-tests; no GitHub publication is performed by these checks.


## Recoverable owner-service startup

host_service.c no longer permanently disables its endpoint after one transient
broker/listener startup failure. On the serialized owner loop it retries at most
once per second, preserves a broker that already bound successfully, and resets
the retry deadline if the observed clock regresses. Clock-read failure does no
startup/dispatch work. Ready service ticks remain bounded; a peer error does not
cause the whole listener/broker to be recreated. This does not relax the separate
original-image guard, rerun commands, kill a conflicting endpoint or change Sony's
player initialization sequence.

test_player_host_service.py runs the production dispatch code with modeled clock,
broker and listener boundaries under host sanitizers and original-libc ARM926.
It verifies failed early bind, rate-limited retry, busy listener recovery without
double binding, repeated ready ticks, temporary clock failure and pre-ready
clock rollback. Real local IPC/original provider paths have separate fixtures;
these startup tests do not claim actual SysMgr or power/USB acceptance.


## Development playlist facade

The analysis broker now connects the existing PLAYLISTS and PLAYLIST_TRACKS
contract views to the FORMAT3 list and validated-child readers. This is an
experimental implementation, not a newly proven active-menu association or
SonicStage compatibility claim. The assumption is explicit: the original view5
FORMAT3 hierarchy is used as the playlist prototype pending real-object evidence.
The caller supplies the opaque list identity returned by the root page; member
reads reject a parent whose original typed FORMAT is not3. Both views retain
bounded asynchronous paging, original metadata projection/CHILDINDEX sorting,
source-off revocation, unknown revision semantics and error output atomicity.
QUEUE is still UNSUPPORTED. Backend implementations that already support a view
retain priority over this fallback.

The broker fixture now traverses list discovery -> returned identity -> member
page, rejects a different parent without modifying output, and preserves
unsupported queue behavior. Its native rows are modeled; original native search,
parent FORMAT getter, list wrappers and query builders have separate instruction
tests. This deliberately completes the source connection needed for a future
focused validation instead of leaving an unwired implementation; it does not
remove remaining semantic/runtime/device gates or mark the overall SDK complete.


## Combined public-client/service verification

tools/test_player_broker_rpc.py joins an independent consumer using public SDK
headers to the actual local IPC server, broker and two background readers.
The server and client run as separate host processes with ASan/UBSan. Tests
exercise play/pause, next/previous, both volume directions, observed change masks,
asynchronous current metadata, default songs, list IDs reused for members,
unknown-revision/stale output atomicity and explicit unsupported queue behavior.
The server closes its listener, drains workers and leaves the underlying player
open until explicit test cleanup. Client code cannot call the server's modeled
original player functions directly across this process boundary.

Original playback observations and database rows are still supplied by modeled
native boundaries. This test proves the production SDK/IPC/broker/worker pieces
interoperate; it does not replace original-instruction/old-libc ARM fixtures or
qualify a real Sony endpoint, radio, SonicStage lists, sleep or USB behavior.
The report records these limits and source hashes, rather than treating modeled
playlist data as evidence of original format semantics.


## Original Met queue-owner loop

REA and original instruction replay establish MetService's worker loop at0x27c45c:
it drains requests through0x286200 ->0x27bba4, maintains retained sessions through
0x27bc98, then waits through0x336180 with argument1000. That helper is an event
wait adapter, not a timestamp getter: it registers an optional cancellation
callback, calls0x337ea0 and returns0 only for native wait result0x105 (timeout).
A normal signal returns0x106. Only the timeout branch runs0x27bcc8 ->0x27b404.
Both session maintenance wrappers obtain MetPlayer through session+0x20;
session+0x18 is not the player pointer.

test_stock_met_owner.py executes the original service loop, request/session
wrappers, wait adapter and pointer forwarding in four cases: queued/empty and
timeout/signaled. It checks command-before-maintenance ordering, acknowledgment,
paired session-list get/release calls and cancellation registration cleanup.
The queue/event/session-list primitives and actual player processing are modeled,
so this is owner-loop/control-flow evidence, not a queue-content or mutex proof.
No new owner-thread hook, native message injection or queue endpoint is added.

The existing session reference protects player/session lifetime, not a sequence
pointer read concurrently from player+0x3ca8. Group-sequence reference counting
has its own lock, but reading a pointer and retaining it afterwards does not make
the intervening replacement/free safe. Current CtrlInfo track/chapter snapshots
must not be repurposed as an owned queue. A queue implementation still needs
safe acquisition in the Met owner context (or an original synchronized API),
then qualified enumeration/shuffle ordering and source-change handling. This
is the remaining queue engineering work; library/playlist pages do not satisfy it.


## Private Met-owner retained sequence adapter

stock_queue_owner.c/.h implements an isolated reference-lifetime primitive.
Its caller must already be in a separately qualified original Met owner callback;
bind records affinity and validates code spans, but cannot prove that an arbitrary
thread is Met. It must not be bound from GUI/metadata readers or exported as a
public SDK service. No production host callback currently invokes it.

In that owner context, acquire reads session+0x20 -> player+0x3ca8 and calls
original MetGrpSequence retain0x27e74c before leaving the owner boundary. Release
uses0x27e774. An outstanding reference prevents a second acquire/unbind; release
from another thread is refused. It neither enumerates sequence entries nor lets
a background reader call mutable sequence methods. The source compatibility
spans cover session layout, player access and original retain/release routines.

test_stock_queue_owner.py executes the adapter and original retain/release
instructions in nine cases. It verifies held/replaced sequence lifetime, duplicate
acquire, held unbind, wrong-thread release, missing session/player/sequence,
alignment refusal and incompatible image/code. The replaced case drops the
player's old reference while the adapter holds its own, then exercises the actual
zero-reference/destructor branch when the adapter releases it. Mutex/pool and
underlying destructor behavior remain modeled. Original reference counter changes
are not replaced with a hand-written test implementation.

The primitive is not linked into the host DSO or exposed through QUEUE yet.
Actual owner callback integration, safe snapshot/enumeration, shuffle/group
ordering and device qualification remain outstanding. It closes the lifetime
piece of the design without pretending that a retained reference alone makes
concurrent queue methods safe or completes the SDK queue capability.


## Private retained OneGroup order snapshot

stock_queue_owner_order now copies a bounded physical-index page while the
private adapter holds a sequence reference and is called on its registered Met
owner. It supports the qualified MetMmOneGrp/MetMmTrk implementations only:
original group table0x49ab0c, track table0x49a910, group-to-track getter0x27e7d4
and OneGrp getter0x282ad0. Other sequence implementations return UNSUPPORTED;
they are not silently flattened into this view.

Original track count0x280848 reads impl+0x40; shuffle flag0x2807fc reads impl+8;
index map0x280888 ->0x280850 returns the logical index when shuffle is off or
loads the16-bit permutation at impl+0x11a74 when on. The adapter copies at most16
indices, bounds the representable permutation, checks resulting index bounds and
rechecks count/flag before committing output. It does not generate shuffle data,
change a play mode, call the database, or mutate the native sequence. Returned
physical ordinals are not stable media IDs and are not SDK browse rows. Group
range/whole-queue semantics and track-ID resolution remain unfinished.

The expanded original-instruction fixture covers linear/shuffled pages, empty
end pages, invalid limits/offsets, corrupt permutations, unsupported counts/types,
and unchanged native object/permutation bytes. Actual count/map and dispatch
instructions execute; input sequence objects are synthetic. Some REA queries for
small leaf functions incorrectly resolved as file offsets (+0x8000); those results
are not evidence for this mapping. Raw disassembly and execution at the original
vtable addresses establish these getters instead. No actual owner callback or
public QUEUE backend is installed by this primitive.


## Owner-only nonmutating cached ID snapshot

stock_queue_owner_cached_ids resolves an order page to canonical local media IDs
only when all requested entries are already in the original cache. This is not
an arbitrary queue/database read. Original0x280d00 maps shuffle order then calls
0x280bec; a miss there invokes0x27fcb4 to read more database rows. Original cache
lookup0x287058 also moves linked-list nodes between LRU lists. The snapshot calls
neither: it bounds a read-only traversal of the two native cache lists (maximum16
nodes) and copies the borrowed IDs into caller-owned strings while protected.

Protection uses the original gate layout initialized by0x336064: mutex at+0,
condition at+4, active owner count at+8. Original0x337930 passes the mutex handle
directly to pthread_mutex_lock, so the adapter uses original-libc
pthread_mutex_trylock on that same opaque handle without assuming its structure.
If the mutex is busy, it refuses immediately. While holding it, any active logical
owner also causes refusal; the adapter never changes the active count. If idle,
new writers cannot enter the gate until this bounded copy releases its mutex.
The cache/root/node and ABI code spans are compatibility checked. This still
requires a proven Met owner callback for sequence lifetime/order; it is not a
way for GUI threads to inspect the player concurrently.

Each cache node supplies physical index+8 and borrowed Moma ID+12. Both lists
are cycle/duplicate/capacity checked, requested entries must all be present, and
IDs must match the supported local MEDIA class/domain. Missing data returns
UNAVAILABLE, active ownership BUSY, corrupt links PROTOCOL and other ID classes
UNSUPPORTED. A staged result is committed only after unlock succeeds. Neither
LRU links, source IDs, shuffle tables nor gate counts are written. No SQLite or
native cache-filling function is called.

The expanded ARM fixture uses synthetic hot/cold cache nodes and original
reference/index getter instructions. It checks linear/shuffle IDs, misses,
cycles, busy mutex/gate, bad/null IDs, mutex errors, unchanged native bytes and
balanced unlocking. It explicitly fails if query or mutating cache lookup entry
points execute. The mutex boundary is modeled; real concurrency and complete
cache-writer coverage remain device/runtime validation work. Uncached queue
pages, grouped sequences, safe callback installation and a full QUEUE backend
are still unfinished. The16-bit native shuffle generator wraps its counter at
65536, so this private order reader conservatively refuses counts above65535.


## Immutable native query snapshot for uncached queue reads

query_snapshot.c/.h captures a retained MetMm list condition as copied data:
local domain, optional parent ID, numeric predicate tree and sort fields. This
is the next building block for uncached reads by an independent Moma client;
it does not run that read or complete QUEUE. Source ownership/Met serialization
must be established by the caller. The private owner adapter now obtains the
query from the retained qualified track implementation at+0x3c and calls this
capture after checking constructor/layout code spans.

The original list constructors0x27f520(search) and0x27f5e4(children) produce
refcount/kind/domain-or-parent/condition/sort words. Condition wrapper+4 points
to the owned numeric predicate. Sort wrapper+4 points to the native sort header
(entries,count). Search domains must use the original local-domain class0x60fc48,
not its preceding name/size header0x60fc40; domain implementation word0 is0/1.
Children retain a local MEDIA ID whose canonical string is copied. None of these
source handles, query pointers or child pointers are put in the result.

Captured trees have at most32 nodes; binary edges become1-based indices.
AND/OR9/10 and scalar operators1..8 with numeric kinds1..9 are supported.
String/custom kinds are explicitly unsupported. Scalar64-bit kinds7/8 preserve
both words; unused high words for narrower values are normalized to zero rather
than copying native padding. Cycles/shared nodes, malformed addresses, excess
nodes and unsupported domains/sorts refuse without changing output. Sorts hold
at most16 key/direction pairs. The copied representation is1112 bytes on ARM and
needs no heap allocation or database access.

test_stock_query_snapshot.py executes the original list constructors and their
condition/sort reference instructions, captures the result and runs original
cleanup. Fourteen cases cover search/children, empty filters,64-bit values,
cycles, oversized trees, strings, incompatible domains/parents, sort bounds,
unsupported kinds and alignment. Original input bytes remain unchanged and
references return to their initial counts. Pool/mutex and Moma ID clone/release
boundaries are modeled. The owner fixture additionally checks query capture from
retained track objects, parent identity and missing-query atomic refusal.

These copies allow the owner reference to be released before future background
queries. Native query reconstruction/execution against physical ordinals,
source/generation checks, full grouped sequences and the real Met callback are
still outstanding. No shared mutable sequence is handed to a GUI/database worker,
no source cache is filled, and no original player request is sent by capture.


## Reconstructed query and independent single-ordinal read

xw_query_snapshot_materialize validates the copied tree/domain/parent/sort before
writing anything, then reconstructs native Moma predicate/sort storage owned by
the reader. Edges refer only to that output buffer. It rejects cycles, shared
edges, orphan nodes, invalid scalar payloads, excess sort fields and overlapping
source/output buffers atomically. Query snapshot tests compare normalized native
trees/sorts after capture -> reconstruction, including64-bit values, and exercise
malformed copied graphs without changing the destination.

stock_media_snapshot_one consumes that copied query and one captured physical
ordinal on the exclusive background reader. It creates its own original domain
or parent identity, calls native search/getChildren with count1 and the exact
reconstructed predicate/sort, copies ID/title/artist/album and releases the row,
list and domain/parent before returning. Search supports both DOMAINALL and
FOLDERTREE. EOF for a formerly captured ordinal returns STALE. This does not call
Met's cache-filling query helper or use a live sequence/query pointer. Linking the
Moma reader now includes query_snapshot.c; no SDK business/radio protocol changes.

The native media fixture adds copied search/domain-all/children reads, invalid
graphs/parent IDs, end-of-list, native query failure and domain unavailability.
It executes original client/manager/list/getter instructions with modeled storage,
checks reconstructed query arguments and verifies all original resources close.
The query-copy fixture separately uses original MetMm constructors and reference
cleanup. These together qualify the source/ABI connection, not real queue contents.
Owner callback and async queue-job publication/generation checks are not connected
yet; grouped queues and physical runtime acceptance remain outstanding.

## Worker adoption on validation errors

begin_read now enforces affinity and adopts the transferred original Moma client
before validating request data. Previously an invalid current ID or child parent
could return before worker_set was recorded, causing the worker's subsequent
close to be refused and leaving the native client retained. All read methods now
unwind through cleanup with busy cleared, including validation failures. GUI or
different-worker calls still refuse without adopting. Regression cases pass an
invalid ID/parent, assert unchanged output/no extra query, and close from the
worker with manager/client references restored. This fixes the private resource
lifecycle; it is not a diagnosis of a prior physical sleep failure.

## Private queue page reader

queue_page.c assembles a bounded page from a pointer-free query and captured
physical order. Known cached IDs use direct metadata reads; uncached ordinals
use independent native query reads. A caller-owned workspace keeps large rows
off the worker stack and commits output only after every read succeeds. A task
generation accompanies results but is not a native catalog revision. The future
publisher must reject results from superseded generations. Empty and invalid
jobs still adopt the transferred client for worker cleanup.

tools/test_queue_page.py checks mixed reads, shuffled ordinals, atomic failure,
bounds, overlap and empty-job handling under host sanitizers and compiles the
reader for ARMv5. Reader boundaries are modeled; this does not qualify a live
Met callback, public queue endpoint or device behavior.

The dedicated queue_async worker now owns transferred Moma clients through read
completion and close. Its owner API uses trylock, revokes intent on NULL or clock
rollback, expires cached metadata after two seconds and rejects completions whose
internal epoch differs from the currently requested plan. Plan content is compared
as well as caller generation, so reusing a task token cannot publish an old list.
Stop does not cancel an executing native read; destroy requires worker drain.
Allocate this large context statically or on the heap, not on a GUI/thread stack.

tools/test_queue_async.py runs real host pthreads with a deliberately blocked
reader to check superseded results, revoke during read, nonblocking stop and
balanced client closure. It also compiles the worker for ARMv5. The native reader
boundary is modeled; original pthread runtime, Met callback capture and public
queue-provider integration remain unfinished. These private components are built
into the analysis-only host library but do not activate a queue endpoint.

queue_capture.c now combines retained-owner acquisition, partial cache/order
capture and immutable query copying into a plan transaction. Every post-acquire
failure releases the original sequence; publication occurs only after successful
release and validation. Its revision remains zero (unknown). Partial cache reads
copy a known-ID bitmask while preserving the strict all-ID API. Missing entries
are not corruption; malformed IDs, busy gates and broken lists still fail.
The original-instruction fixture checks a cache miss produces only the surviving
ID bit without mutating cache links. tools/test_queue_capture.py checks cleanup
and atomic publication with modeled owner methods. A qualified Met callback and
cross-thread plan handoff are still required before enabling the public queue.

## Queue request handoff

queue_exchange.c provides a trylock-only pointer-free handoff between the GUI
requester and a future qualified Met callback. Changing or revoking a page request
invalidates pending captures. Publish compares generation, offset and limit under
the same mutex; superseded results cannot replace the active plan. Native capture
errors replace readiness with an explicit error instead of retaining a prior plan.
Generation exhaustion refuses new requests rather than wrapping. Destruction
requires externally quiesced callback access; it is not a cancellation mechanism.
tools/test_queue_exchange.py covers superseded/revoked publication, atomic error
reads, GUI affinity and generation exhaustion, plus ARMv5 compilation.

REA evidence for original0x27afa4 shows a boolean test of player+0x3ca8, not a
queue revision counter. Session+0x10 must not be promoted to a public revision.
The original worker calls session maintenance0x27bcc8 at0x27c610 with session in
r0 and cancellation context in r1, and consumes its return at0x27c614. Any future
trampoline must preserve those inputs and the original call/return semantics,
including when no preload library exists. No such trampoline is installed by
these components. Existing compatibility spans overlap this callsite and must
be explicitly qualified for any modified image, never bypassed.

queue_browser.c now coordinates GUI page requests, Met-side plan capture,
exchange publication, background metadata reads and atomic page delivery. Its
capture entry requires a separately bound owner in an already qualified Met
callback. Its GUI entry refuses unsupported containers and nonmatching expected
revisions, preserving caller output on error. The source observer must revoke
intent when the original source becomes unavailable. Shutdown requires external
Met callback quiescence before draining the reader and destroying the exchange;
this coordinator does not claim to stop an uninstalled hook.

tools/test_queue_browser.py executes the complete coordinator with real capture,
GUI and reader threads under host sanitizers, using modeled native capture and
Moma boundaries. It verifies ordered pages, a partial last page, revision refusal,
revocation and balanced reader closure. The analysis DSO builds these components,
but its native boundaries are modeled; later host integration is described below.

The broker now accepts an explicitly attached internal queue provider. Without
one, queue browsing remains UNSUPPORTED. Existing backend browse support retains
priority. For the attached fallback, unavailable original media sources revoke
queue intent and return UNAVAILABLE; the owner tick also revokes it. Broker close
first closes the attached queue service, retaining the original backend and all
remaining broker state if its callback returns BUSY. The attachment's close
callback must quiesce Met access before destroying queue exchange state. Merely
attaching a browser cannot establish that lifecycle guarantee. Attachment is
owner-thread-only and is not called by host_service.c until its native callback
integration is qualified.

The broker fixture now exercises queue rows through the public SDK browse API,
source-off revocation, stale output preservation and close retry while preserving
the original player. Existing cross-process RPC/client regression tests still run
with queue support absent unless explicitly attached. These tests do not qualify
an on-device queue provider or install one.

## Analysis-only Met trampoline

build_player_met_anchor.py creates a separate pinned-stock ELF experiment, never
an update package. It redirects the maintenance call at0x27c610 to a16-byte ARM
stub at0x4d6004. The stub saves r0-r3/r12/LR, calls the existing argument-free
getpid PLT anchor, restores registers and tail-calls original0x27bcc8. The stock
session wrapper still returns directly to0x27c614. No preload callback dispatch
is enabled by this builder.

The original executable load has a virtual gap before the data load. The builder
extends its file/memory extent by16 bytes, inserts one aligned32KiB file block,
and shifts later file offsets and the section-header table. Every original
virtual address, entrypoint, load permissions and data/BSS memory extent remains
unchanged. Program-header location/count stays unchanged, avoiding a new-header
mapping assumption in the old kernel. This experiment increases the ELF file by
32768 bytes; it is not part of a firmware or a capacity qualification.

test_player_met_anchor.py maps the resulting ELF and executes the actual ARM stub
and original session wrapper. A modeled PID call deliberately destroys caller
scratch registers; three modeled original-player return values survive, as do
input arguments, stack and callee-saved registers. Non-text section bytes and all
section addresses/sizes remain unchanged. Original loader startup, real PID PLT
resolution and physical runtime still require separate checks. Native image compatibility spans overlap the changed callsite. They now have an
explicit tested alternative profile for this exact experiment; compatibility
checks remain active. This is not physical runtime qualification.

## Met anchor argument bridge

host_pid.S now exports the getpid entry as an ARM bridge: it passes the incoming
r0/r1 words and LR to the C dispatcher without dereferencing those words. Ordinary
calls still delegate to the original PID function. The separately built Met stub
has return site0x4d600c. Only that caller plus exact16-byte stub and4-byte original
callsite fingerprints can invoke the Met dispatch callback. Dispatch preserves errno and rechecks the exact anchor bytes; the service
adapter selects its owner by list/session identity. Different original Met
services may reach the same instruction on different threads. The production analysis library supplies a lifecycle-controlled queue adapter;
identifying a callsite alone does not qualify complete original-player runtime.

test_player_met_dispatch.py executes the stub, assembly bridge, C guard and
original session wrapper with a strong diagnostic callback. It checks exact
session/cancellation forwarding, multiple Met thread forwarding, altered-stub/call refusal,
wrong-image refusal, ordinary PID pass-through and errno preservation. Image and
thread identity/PID target/player processing are modeled in this test. The
separate original-Sony-loader PID test and GUI-anchor tests also pass with the
new bridge. No complete SpiderApp boot or original queue capture is implied.

## Exact Met image compatibility profile

stock_image.c now accepts two explicit alternative span digests for the pinned
Met experiment, only when the caller requests their exact original digest. The
protected GUI span0x27c300/0x2000 and controller span0x27b400/0x2200 each retain
full-span hashing. Their alternative hashes cover the one changed branch and
all surrounding original bytes. Acceptance additionally requires the complete
16-byte stub digest at0x4d6004 in the same supported loaded image/base. No byte
normalization, ignored ranges or permissive fallback is used.

The composite GUI-plus-Met ARM fixture now executes actual original-provider
binding with this profile, accepts the expected experiment and rejects an extra
code-byte or stub-byte change. Original-image GUI binding still has its separate
regression fixture. This qualifies the local compatibility rule, not complete
SpiderApp loading, on-device worker behavior or callback lifecycle. Production Met dispatch supplies the host queue lifecycle adapter. Matching-session
routing is now checked by value identity as described below.

## Host queue lifecycle adapter

host_queue.c supplies the strong Met dispatch callback in the analysis library.
Its process-lifetime mutex is constructed during startup preload, before original
application threads exist; dynamic late loading is not qualified. GUI attachment
requires an observed verified Met anchor. Met binds its own native queue owner.
A close request changes phase under the gate; Met unbinds and acknowledges before
the GUI can drain/destroy the browser. Future callbacks use the retained gate but
cannot access the destroyed browser. No thread waits on this gate.

test_player_host_queue.py uses real GUI/Met threads and modeled browser/native
methods to test attachment, capture affinity, stop acknowledgement and later
callbacks. Browser and native instruction tests remain separate. Broker source
revocation now records a pending invalidation if a busy callback cannot revoke;
it must finish that revocation before browsing after source recovery.

Automatic attachment now requires an observed Met list matching the GUI music
controller. Native session selection is checked using the list identity and
session number; a generic OneGrp sequence is not sufficient. No device
installation or physical queue qualification has occurred.


## Current music-session routing

The GUI-owned music controller at0x6922d8 contains the original service and
session number consumed by0x27d4e4 ->0x27c314 ->0x27b5e0/0x27b5a4. The original
lookup compares session+0x14 with that number. stock_info_session_key copies the
service+0xec8 list identity and number on the bound GUI owner. It transfers no
reference; the copied list value is never independently dereferenced by Met.

At the maintenance callsite, the original worker retains the current callback
session and keeps its service+0xec8 list identity in r7. The assembly PID bridge
now forwards that value as a fourth C argument alongside r0/r1 and LR. Met compares
this list identity and the retained callback session's number with the GUI key.
Other sessions are skipped, not allowed to overwrite the music queue. Changed
GUI keys revoke previous queue intent before scheduling a replacement.

The original-info fixture now includes an unrelated session before the target in
the original linked-list lookup. The original Met-loop fixture checks r7 at the
actual callsite; owner fixtures check matching/wrong list and number; bridge tests
check r7 forwarding. The threaded lifecycle fixture interleaves unrelated sessions
and lists, and its capture method rejects anything except the selected session.
These are offline instruction and modeled-integration checks, not device tests.

The host builder now also emits a combined GUI/Met analysis-only ELF, preserving
the existing GUI-only experiment. The combined candidate grows by32KiB and is
not placed in a firmware package. The analysis service attempts attachment only
after a matching Met list has been observed. Full combined runtime, multi-group
queues, native worker creation and physical sleep/USB behavior remain unqualified.

## SDK-to-native-queue coordinator integration

Run tools/test_player_broker_rpc.py --native-queue for the separate-process queue
pipeline test. The independent consumer imports public SDK headers only and uses
the same local IPC and media browse contract. The server runs the production
broker, process-lifetime host queue adapter, session filtering, plan capture,
exchange, background queue reader and page assembler. Only original controller,
sequence primitives and Moma boundary methods are modeled in the fixture.

The consumer verifies shuffled order through mixed cached-ID and uncached-query
metadata reads, paging, an audio-session change with different queue contents,
return to the previous session and rejection of a nonmatching expected revision
without changing output. Shutdown keeps Met callbacks running until the native
owner stop acknowledgement, drains workers and checks paired queue references
and clients before explicitly closing the preserved original backend. The normal
fixture still tests unsupported queue behavior without an attached provider.

This joins maintained code across real host processes and threads. ARM original
instruction/ABI fixtures remain separate evidence. It does not prove complete
SpiderApp boot, a physical queue endpoint, multi-group ordering or SonicStage
playlist classification. No device files or firmware packages are changed by it.

## Additional original sequence types

test_stock_sequence_types.py executes the original getters behind the table at
0x49a9bc: count at+0x18 returns1 and ordinal mapping at+0x1c returns0. The table at
0x49aa68 uses0x282048 to return its current track sequence from implementation+0x24.
All tested getters preserve the modeled source bytes. Neither observation proves
constructor/ID lifetime or complete queue enumeration.

The MmGrp next/previous methods0x282258/0x2824c8 call preparation routines and
replace retained current/next/previous state. They must not be used to enumerate
groups for a read-only SDK query. Returning only the current group's track list
would also misrepresent a complete grouped playback queue. A separate immutable
group plan is required before enabling that sequence type. Single-track ID lifetime and constructor qualification now have the separate
original-instruction fixture below.

Several tiny-function REA requests selected another function at a file-offset
fallback address (for example requested0x282048 returned0x28a018). Those results
are not evidence for the requested getter. Vtable addresses, raw instruction
checks and executed original getter tests above establish the actual boundaries.

## Prepared single-track queue support

The OneGrp adapter now accepts the table at0x49a9bc for MmOneTrk sequences. It
uses the original count/ordinal/shuffle getters with exact code/table guards.
Copying its local ID requires preparation state implementation+0 to equal1;
only then may the owned ID at+0x24 be read. An unprepared sequence returns
UNAVAILABLE without interpreting the stale pool slot. Invalid local ID classes
remain unsupported. Empty pages past its one item do not dereference the ID.

REA and test_stock_single_lifetime.py establish the lifetime: original constructor
0x2817e4 initializes state0 but leaves the ID slot untouched; original prepare
0x28194c clears the slot and invokes original callback0x281430 to clone the ID,
then marks state1 only when a row was delivered. Original destructor0x2813dc
disposes the ID only for a prepared sequence and releases client/query/pool state.
The fixture executes those original functions for success, empty and cancellation
paths with modeled allocation/DB/clone boundaries and balanced cleanup.

The owner fixture checks prepared, unprepared poisoned-slot, invalid-ID and empty
page cases without source mutation. Fully known-ID pages now skip unnecessary
query capture; their plan has no query execution requirement and the background
reader fetches each captured ID directly. Partial pages retain the immutable
query snapshot path. This does not enable grouped traversal or prove physical
single-track behavior. The public SDK media browse contract is unchanged.

## Multiple Met service threads

The PID bridge must not pin Met dispatch to the first arriving thread. Multiple
original service loops can use the same verified callsite. host_hook.c now checks
the exact branch/stub bytes without mutable global Met thread state and forwards
each qualified callback. The adapter's process-lifetime trylock gate serializes
its own state; unrelated lists are filtered before native owner binding.

When the GUI target changes to a different list, the existing native owner is
retired only on its original thread. The replacement service waits for that
acknowledgement before binding. Callbacks from unrelated lists on the same thread
do not themselves retire an otherwise current owner. Closing likewise waits for
the recorded native owner, rather than allowing an unrelated service to free it.
A missing old-owner callback leaves a bounded BUSY result; no forced teardown or
cross-thread native unbind is attempted.

The host-queue fixture starts an unrelated service thread first, attaches from
the GUI, then starts the music service. It switches the GUI target to the second
service and back, verifies captures on the selected sessions, and closes with
both callback threads still active. Original PID-loader and public SDK/RPC queue
regressions remain separate checks. Hardware service topology and scheduling are
not inferred from these modeled services.

## Immutable grouped-read inputs

The private query module now copies original numeric condition/sort references
into a pointer-free filter template. A portable with-parent operation binds that
template to a canonical local container without accessing Sony memory. Invalid
graphs, sort values or parent IDs leave output unchanged. This reuses the same
bounded graph parser as captured native queries, rather than fabricating new
original reference objects or retaining their pointers in a worker.

stock_queue_owner_group_plan captures the MmGrp list query, track-filter template,
cached group count, current group index and shuffle flag while the caller owns a
retained sequence on its Met thread. Constructor/table/query/ID layout fingerprints
remain required. Unknown cached count is preserved as UINT32_MAX; capture does
not invoke initialization, query counting, next/previous preparation or cache-LRU
methods. The owner fixture checks immutable capture, missing query and unsupported
shuffle state. Query fixtures check template copy/parent binding and atomic errors.

This descriptor now feeds the incremental worker path described below. Native
group IDs and ordering still need qualification before physical compatibility
can be claimed. Unknown totals remain explicit, without altering playback. In
particular, current-group getters do not establish complete future shuffle order.
The existing OneGrp path and its public SDK tests remain separate.

## Incremental unshuffled group walker

group_reader.c now consumes an immutable group plan through a bounded page-reader
callback. Each step performs at most one group or child-page read. It keeps its
cursor, copied parent query, scratch page and staged result in caller-owned heap/
static state. Empty groups, offsets crossing groups, unknown group counts and
partial final pages are explicit. A complete observed traversal can report a
total; an early full page preserves UNKNOWN instead of inventing a total.

Captured group ordinals disappearing return STALE; malformed child IDs or empty
non-exhausted pages fail without publishing output. The worker owner can reset a
job between steps; the eventual publisher must still reject superseded generations.
Shuffled group plans are refused because future group-specific permutation has
not been qualified. No original sequence next/previous/cache methods are called.

The callback currently has a modeled implementation in test_group_reader.py.
It still needs a native copied-query page adapter and queue-worker integration.
The Windows Clang run verifies host behavior only. Its separate report identifies the host/compiler and excludes GNU/sanitizer
qualification on Windows. The Linux test path includes ASan/UBSan and GNU ARM
compilation when that environment is available.

## Native copied-query pages for group steps

stock_media_snapshot_page adds bounded1..16-row native query pages with explicit
EOF. It executes copied predicates/sorts and independently creates/releases its
domain or parent ID, list and each media object. Separate caller-owned workspace
and output buffers keep large pages off the native worker stack and preserve
output on error. The captured-ordinal snapshot_one API retains its distinct
STALE-on-missing behavior. Query/offset/count/overlap checks still adopt an eligible
worker for transferred-client cleanup.

group_native_step connects one group-walker step to that page API. Each invocation
adopts a GUI-prepared client and closes it after the step, even when the walker
returns BUSY, has finished without I/O, or rejects arguments. A failed close does
not publish its staged result. Only pointer-free cursor/query/item state persists
between steps; no idle original client is kept while awaiting another GUI tick.
The future asynchronous scheduler must transfer a fresh client for each step and
still reject a superseded job generation before publishing.

The native instruction fixture now includes copied-query search/children pages,
empty and exact-full pages, mid-page error, invalid counts/offsets and overlapping
buffers. With WSL stalled, the pinned Unicorn version was installed into ignored
Windows test dependencies; a separate Windows Clang ARMv5/LLD wrapper runs these
original-instruction fixtures and records that it is not a supported GNU/loader
qualification. The grouped-step host fixture checks per-step client cleanup and
atomic output on close failure. Its Windows path also compiles ARM objects with
Clang using maintained freestanding declarations. Actual native DB data, original
LinuxThreads scheduling, loader startup and hardware remain unqualified.

## Grouped jobs in the queue worker

Private queue plans now distinguish copied flat order from an immutable grouped
plan plus requested offset/limit. Capture falls back to the qualified MmGrp
descriptor when the flat sequence type is unsupported, rejecting grouped shuffle.
Capture scratch is caller-owned in queue_browser, rather than a growing local
frame on the original Met thread. The ARM Clang frame check keeps the capture
function below2048 bytes; its callees and original runtime remain separate limits.

The same queue_async thread now advances a grouped job one native step at a time.
GUI observations transfer a fresh client for each step, and only pointer-free
walker state persists. Progress is scheduled on a subsequent GUI tick; a BUSY
native read without cursor progress gets a short retry delay. A changed epoch
resets the walker, and completed jobs reset before a later cache refresh. Merely
changing the current group index does not restart the same unshuffled query.

The worker fixture tests grouped completion, current-position stability,
revocation during an active group read, stop/drain and balanced clients. On
Windows it uses a test-only Win32 implementation of the opaque pthread calls;
that file is excluded from device/SDK modules. Linux retains its host-pthread
ASan/UBSan path. Queue-browser and capture fixtures are updated for the new
private plan and workspace. GNU/old-loader/physical qualification remains pending.

ARM Clang layout currently reports4496 bytes per private plan,107336 for the queue
worker and140096 for the complete queue browser, including fixed page buffers
and group workspaces. These are static/heap contexts, not thread-stack objects;
public SDK client layouts are unchanged. This is a compiler layout observation,
not a measured device memory/power qualification or a firmware capacity result.

The queue-browser integration fixture now transitions from flat to grouped plans,
reads across an empty group through the exchange and actual asynchronous/native-
step adapters, and checks ordered rows and final totals before draining clients.
Its native capture and page boundaries remain modeled. Windows tests use real
threads through the test-only Win32 pthread surface; GNU/ASan/UBSan checks remain
pending while the original WSL jobs are stalled. No physical compatibility,
complete queue notifications or random grouped order is established by this test.

## Stable grouped-query comparison

Grouped job invalidation now compares validated query fields rather than raw
snapshot bytes. Parent text is compared only through its terminator, and only
active predicate nodes and sort entries participate. Padding and unused capacity
cannot restart an otherwise unchanged long group walk. Invalid graphs never
compare equal. Active predicate, sort and parent changes still revoke the job;
this is structural comparison, not algebraic predicate simplification or a native
catalog revision.

test_query_equal.py checks those distinctions. The asynchronous worker fixture
also mutates unused slots/padding while a grouped result is cached, then changes
an active sort key and verifies a new native job is scheduled. Existing epoch,
revoke and reader-drain checks remain. Windows Clang/Win32-shim results do not
substitute for GNU/sanitizer/old-loader or physical qualification.

## Clock observation failure and cache recovery

The broker now revokes its metadata/catalog/queue observations when the monotonic
clock cannot be read. Internal revocation uses time0 only to remove intent; it
never schedules a new native read with a fabricated timestamp. Independent valid
backend state/volume fields remain available. Cache freshness must be reestablished
from a subsequent successful clock observation and native read.

Previously, metadata was omitted during the clock failure but its cache remained
valid; the next successful call could immediately resurrect pre-failure artist
text. The regression changes modeled metadata while the clock fails and checks
that recovery first has no valid metadata, then emits METADATA only after a fresh
read. Catalog and attached queue browse tests check unchanged outputs during the
failure and explicit revocation before recovery. Source-off ticks reuse the same
revocation path, including deferred queue invalidation if its gate is busy.

The Windows broker fixture uses real worker threads with modeled native media and
a test-only Win32 pthread surface. Its report excludes sanitizer, GNU and Sony
pthread/runtime qualification. The ARM Clang compile bounds this source's local
frames only; it is not a whole-call-chain or original GUI stack guarantee.

## Arbitrary-track selection research boundary

PLAY_ITEM remains unsupported by the native command mask. A software event that
looks like a selection handler is not sufficient evidence to enable it.
test_stock_audio_control_roles.py executes original handlers0x69064/0x690b0 and
0x681f0/0x6821c plus their wrappers: they submit change-state operations3/4 with
signed payloads100/-100 or10/-10 and second word1. They do not consume a supplied
media ID. Payload units are not qualified. They must not be mapped to PLAY_ITEM.
The0x440035 candidate instead reaches component mode/argument setters, not an
arbitrary local-ID playback entry.

The actual source construction path has now been identified at App wrapper
0xacc9c. It selects sequence factories by descriptor kind, including direct item
factory0x283a38, flat query factory0x283ad4 and grouped factory0x283bc4, then calls
controller0x27d54c. It releases its temporary sequence and frees the source
descriptor afterward. Wrapper result alone is not controller acceptance: the
original wrapper logs/discards some downstream results.

test_stock_source_admission.py executes original0x27d54c,0x27c66c, sequence retain
and enqueue code. Successful admission retains the sequence before copying seven
configuration words, rebases optional16-byte and28-byte pointed blocks into the
owned request, and returns an admission ticket. Caller sequence release leaves
the request's retained reference alive. Allocation/inactive cases retain nothing
and preserve the invalid ticket. Allocation, synchronization and initialization
boundaries are modeled; request consumption/destruction and actual playback are
not qualified. This does not yet provide a safe SDK source-selection transaction.

Windows static analysis uses the existing Ghidra headless engine directly because
REA6.5's Windows provider explicitly refuses ARM ELF. Its persisted project and
query evidence remain under work/player-ghidra-windows. Results identify that
provider and pinned target SHA; they are not mislabeled as REA output. A Node22
Windows path-stat volume discrepancy was observed and independently confirmed;
the process-local metadata workaround preserves identity/extent/time checks, but
it cannot make the unsupported REA target supported. No MCP registration, target
execution or device connection was performed for this research.

## Source descriptor ownership and GUI handoff

Original0x4ab70 allocates/copies64 descriptor bytes without cloning pointer fields.
The source install path0xad270 replaces the previous pending descriptor and, for
supported kinds with a nonzero selected ID, calls0xacb20. That setter disposes the
old selected ID and stores the incoming ID without cloning it. Thus the input ID
reference moves into the original wrapper; it is not a borrowed reference that
an SDK binding can unconditionally dispose after dispatch.

test_stock_source_descriptor.py executes original copy/install/replace/free and
selected-ID setter instructions. It verifies the input descriptor buffer can
expire, replacements dispose the previous selected ID, and descriptor allocation
accounting balances. Heap/ID-disposal and UI helper boundaries are modeled; this
is not an OOM or complete wrapper-teardown qualification.

The correct source handoff software request is0x44001d in the mapped stable
phases: mode1/state5 ->0x68e78, mode2/state2 ->0x68248. Both install the descriptor
then request controller state0, and transition to mode1/state7. Original0x440104
in mode1/state7 reaches0x68ea4, which invokes source construction0xacc9c. Other
source handlers in mode1/state3 and mode1/state2 have separate entry conditions.
This mapping is not permission to dispatch in arbitrary transient phases.

test_stock_source_dispatch.py executes the original generic FSM, stable handlers,
descriptor handoff and stop wrapper with modeled lower acceptance. Importantly,
a rejected stop still transitions the GUI and leaves the item owned by the
wrapper, with an invalid admission ticket. Future native control code must track
ownership independently from command result, must not free the handed-off ID on
UNCERTAIN, and must not blindly retry. End-to-end request completion, error
recovery and source consumer/destructor behavior remain unqualified; native
PLAY_ITEM remains disabled rather than claiming those guarantees.

## Experimental source submission component

stock_source.c now implements the private, non-advertised handoff component. It
checks GUI ownership/stable phase, local-ID encoding, source readiness and exact
source/ID code fingerprints, creates an owned local ID and dispatches original
0x44001d with a bounded type0 descriptor. Internal result bookkeeping separates
attempted, moved and observed ticket. Only an untransferred ID is disposed; a
filtered/uncertain result after ownership move cannot free the original wrapper's
ID. The public provider command mask is unchanged: PLAY_ITEM is still unsupported.

The component requires the caller to first qualify the item as audio. It does
not itself prove the media type or item existence and is not a complete arbitrary
ID playback API. The legacy descriptor heap path, completion, request consumer,
error recovery and teardown still need qualification before public integration.

The24-case original-instruction fixture test_stock_source_submit.py covers both
stable GUI modes, lower rejection, unchanged ticket, filtering before/after
handoff, ID allocation failure, unavailable source, malformed ID, busy/wrong
thread, changed descriptor code and transient phase. Its current Windows run uses
Clang ARMv5/LLD and the pinned Unicorn package; it executes this C component and
original filter/FSM/descriptor/stop-wrapper code with modeled boundaries. Its
separate output is not labeled as a GNU or original-loader qualification.

## Per-intent audio identity preflight

stock_media_validate_audio now projects only OBJECT_TYPE0 and MEDIA_TYPE1 through
the original enum getter, verifies the returned canonical object identity matches
the requested identity, and accepts only the same0/1 type pair used by the native
default-song predicate. Missing objects/fields, mismatched identities, non-audio
objects and wrong scalar representations fail without publishing an observation.
Type fields start with an unknown sentinel; the unwritten-type fault-injection
case bypasses the typed getter to model a broken output contract, not an observed
bug in the shipped getter. The native fixture pins both key names to the original
registry and checks projection, cleanup and alias refusal alongside prior cases.

The returned identity is only a point-in-time observation. It is not a catalog
revision, a security token or a guarantee the object remains playable. A later
source transaction must still handle deletion, format/license rejection and the
original completion/error lifecycle.

audio_check_async reuses the background-reader implementation with an immutable
per-instance reader callback. It checks each new nonzero request generation,
normalizes local ID text, rejects old intent results and revokes observations on
source loss. Its generation is a private cache key, never advertised as a native
catalog revision. The generic metadata worker preserves its default metadata
behavior while this specialized mode propagates native validation refusal codes.
GUI-owned status fields avoid reading worker result state outside its mutex.

The threaded fixture covers replacement during a blocked read, video refusal,
fresh validation for repeated IDs under a new intent, source loss, cancellation,
client drain and wrong-thread refusal before any native readiness call. No title
reader or GUI command is used. Native instruction cases remain separate evidence
from the Win32-thread-surface host tests. Both preflight and source submission
remain internal; PLAY_ITEM is still not exposed until complete integration and
recovery qualification.
