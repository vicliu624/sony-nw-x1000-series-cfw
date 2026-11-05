# Wireless modes and consumers

Wireless mode belongs in the original wireless settings. Remote control is one
consumer of ESP-NOW, alongside independent Homebrew applications. Enabling remote
control must not silently select ESP-NOW or grant unrelated player permissions.

| Setting or interface | Responsibility |
| --- | --- |
| Wireless mode: Off / Wi-Fi / ESP-NOW | System policy and exclusive handover between radio uses |
| Remote control settings | Pairing and permission to use the original player |
| ESP-NOW SDK | Authorized radio transport, without a player dependency |
| Player SDK | Playback control and information, without a radio dependency |

Selection is not actual hardware state. ESP-NOW can stay selected with no active
consumer and no powered radio. The authoritative system owner must wait for all
old ownership to retire before admitting ordinary Wi-Fi or another radio mode.
Closing remote control releases its usage; it does not change the selected mode.
Entering Homebrew retires the original player's remote consumer so an independent
app can acquire radio usage through the same system policy.

## Current source boundary

`runtime/platform/wireless/mode.h` defines policy values only. It is not an
implemented cross-process mode manager, hardware status API or released SDK
service. `mode_policy.c` now provides the private serialized authority core:
it starts unverified, requires explicit original-off evidence or adoption of a
qualified existing stock Wi-Fi owner, and issues one exclusive hardware-owner
lease with generation/serial/consumer/mode identity. It imports no player code.
A mode request with an active lease enters DRAINING: old ownership survives for
restoration, data/new-owner admission is denied, and selection changes only on
verified release. Reversing a pending choice does not revive the draining lease.
Unknown retirement retains the lease and latches failure; positive release does
not silently clear failed policy. Repair requires a separate explicit off
confirmation. Neither selection nor lease issuance powers hardware in this core.

The core belongs to a single trusted system owner process/thread. It is not a
daemon, transport, global lock implemented by every app, or original Wi-Fi hook.
The authority adapter must validate consumer identities and actual native/off
evidence; the core's supplied evidence is not a voltage/current measurement.
Independent apps must use a broker-issued capability, not a copied core object.
Public SDK registration/persistence and native authority binding remain unfinished.

`mode_channel.c` implements a private cross-process capability channel over an
already-connected AF_UNIX datagram socket. The trusted authority supplies the
consumer identity and separate READ, SELECT, WIFI and ESPNOW grants. An ordinary
consumer cannot select the system mode; a Settings capability need not acquire
radio ownership. There is no listener, discovery or identity supplied by packets.
Each owner dispatch processes at most one receive or reply without blocking.

Requests are32-byte WMC1 records; replies are80-byte WMS1 records. Integers are
little endian. Nonzero request serials increase monotonically. An identical last
request receives its cached reply without reapplying the operation; that snapshot
can be old, so observing a transition requires a fresh QUERY serial. The client
decoder matches operation/serial, exact length, reserved bytes, enum ranges and
ownership consistency, preserving its output on rejection. A reply is policy
information, never physical power-off evidence.

RELEASE and channel close only begin drain. Only the authority's local
`xw_mode_channel_retired` call can supply qualified driver retirement/off evidence.
Malformed traffic closes the channel while retaining uncertain ownership. Datagram
peer exit alone is not a reliable retirement notification: the production launcher
must notify the authority when a consumer exits and arrange verified cleanup.
No timeout or dead client is treated as proof that the radio is off.

`tools/test_wireless_mode_channel.py` exercises actual forked clients with host
ASan/UBSan and Sony-libc ARM guest execution. Cases include independent selector
and consumer grants, replay/stale requests, malformed forged off evidence,
consumer exit, retained ownership and explicit repair. Physical RF completion is
modeled by a separate fixture channel. This transport is not yet an installed
global authority or a released SDK endpoint.

`mode_client.c` is the private nonblocking consumer half. It receives an already
connected capability and expected generation from the trusted launcher, duplicates
and records socket identity, binds to its process/thread, and permits one request
at a time. Each step performs at most one nonblocking send or receive, without
allocation, waiting, hardware polling or a new worker thread. Operation status is
separate from successful reply delivery. Pending/error paths preserve caller output.
Unexpected generations fail closed; stale operation/serial replies are discarded
one at a time. Exhausted serials are not reused.

Client close does not supply retirement evidence; owned or in-flight usage returns
PENDING and remains the authority's cleanup responsibility. FD identity checks
avoid closing an unrelated reused descriptor. The channel test now runs the
actual client/server across forked processes through query/acquire/release and
verified retirement, plus wrong-generation and FD-reuse cases, under host
sanitizers and Sony-libc ARM guest execution. Trusted capability provisioning,
original queue binding and physical retirement remain outside this test. A GUI
adapter must advance this client through later dispatches rather than spin/wait.

The trusted owner can bind a READ-only worker channel to an existing native
service lease with `xw_mode_channel_observe`, before any traffic. Consumer identity
must match and the lease must currently allow data. This is observation, not a
transfer: the worker cannot select, acquire, release or report retirement, and
closing/faulting the view does not quiesce the native service. The authority and
native lifecycle adapter retain the actual lease. A QUERY includes that service's
lease while it remains owned, including drain; `xw_mode_reply_data_allowed`
separately refuses drain/failure and accepts only a stable matching QUERY view.
The view is a snapshot, not an indefinite authorization or a physical-off proof.

The cross-process client/server test covers this worker view, denied mutations,
mode-change revocation, actual-owner retirement and closing a view without
revoking the native service, under host sanitizers and Sony-libc ARM. Production
native-worker capability provisioning and RF-operation interception are still
unbound. Do not hand an authority object to the Wi-Fi thread.

`native_permission.c` supplies the worker-only synchronous boundary needed by
stock synchronous RF wrappers. A trusted binding supplies the GUI process/thread,
READ observation channel and exact native lease. Binding/checking on the GUI
thread is refused; a bound context rejects foreign worker PIDs/threads. Each check issues a
fresh QUERY and matches the full generation/serial/consumer/mode key, not merely
the selected mode. It uses the verified fixed-word monotonic clock bridge and
socket polling with a caller budget of1-200ms. That budget bounds requested waits,
not operating-system scheduling latency. It creates no thread/timer/file and has
no idle polling loop. It must never be called while holding a GUI-needed lock.

Timeout or transport failure closes only the observation channel and latches
failure, retaining the real native lease at the authority. It cannot infer off
or authorize another mode. Real pthread host/ARM tests run the client on a worker
while the authority pumps on the original test thread, then revoke mode, test
GUI refusal and exercise a silent-authority timeout. ARM uses Sony libc/librt
clock ABI; the host test has a separate fixed-word conversion fixture. These are
not actual Sony worker/callsite/lock-order tests. Original queue publication and
physical handover remain unbound; the optional callsite profile is described below.

`native_rf_worker.c` connects the RF receiver to this permission check using one
pthread-specific context per configured native worker. A single pthread_once/key
initialization uses original LinuxThreads synchronization; no raw shared worker
pointer is read from the GUI. Trusted binding duplicates the supplied observation
descriptor and allocates one small context. Missing bindings refuse RF calls.
Explicit close clears the key and closes/frees the context; the pthread-key
destructor does the same on thread exit, retaining the authority's actual lease.
The key lasts for the process-lifetime host DSO; dynamic DSO unloading is not
supported by this private profile. Actual pthread host and Sony-libc ARM tests
exercise unbound/duplicate/GUI refusal, revocation, explicit close and destructor
cleanup. Production provisioning of the original Wi-Fi thread remains unfinished.

Worker renewal uses `xw_native_rf_worker_replace`: the trusted caller supplies a
fresh observation capability for a strictly newer lease serial at the same
authority generation and consumer. A fresh QUERY must validate that exact lease
before TLS is replaced. The old view is closed/freed only after successful key
installation; failed validation preserves it. This does not release either real
lease or infer off. A new authority generation requires separate bootstrap,
not silently relabeling old state. Real pthread host/ARM tests retire the first
lease at the authority, issue a second lease/view, replace it on the same worker
and verify RF admission can succeed again. Old-serial and relabeled-old-view
attempts are rejected, with failed replacement leaving the original view usable.
The receive path below handles fresh-capability delivery. The paired original
GUI hook now triggers publication when an authority is bound; startup qualification
and repeated RF use remain unqualified on hardware.

`native_offer.c` now transfers a READ observation descriptor using SCM_RIGHTS over
an already-trusted connected AF_UNIX datagram delivery channel. Its fixed64-byte
WFO1 record carries the native lease and GUI identity, with reserved bytes zero.
The receiver requires exactly one connected datagram descriptor, marks it
CLOEXEC, validates metadata, adopts/renews it on the worker, and closes the
received descriptor on success or rejection. Initial adoption validates a fresh
QUERY before returning; renewal preserves old TLS on failure. No discovery path,
file, timer or hardware operation is introduced. Sender admission requires the
actual authority thread and a currently data-allowed Wi-Fi lease.

LinuxThreads has distinct kernel PIDs for GUI and worker: equality of their
`getpid()` results is not a valid process-membership test. Native permission
binding verifies the observation socket's SO_PEERCRED PID against the trusted GUI
PID; delivery verifies its own peer credential too. The client separately records
the actual worker PID/thread and rejects forked copies after binding. Earlier
fixtures passed the worker PID as the GUI PID and did not cover this distinction;
current fixtures use the producer's real GUI PID. A connected capability and
trusted bootstrap remain the authority boundary, not metadata or PID equality.

Real host/LinuxThreads ARM tests deliver two actual descriptors across a pthread,
validate initial adoption and renewal, reject GUI self-adoption, malformed offers,
wrong peer PID, draining offers and forked bound contexts, and check rejection
does not leak received FDs. The paired profile below now attaches the delivery
endpoint at worker entry and checks it at the RF boundary. Conditional software
startup qualification is implemented below; native retirement and physical RF
cycles remain unfinished.

`native_bootstrap.c` prepares one connected datagram pair in the host constructor,
before Sony creates its Wi-Fi worker. These are two bounded process-lifetime
descriptors, with no listener, storage path, new thread or RF power. The guarded
worker-entry bridge attaches a duplicate of the receive endpoint through TLS,
preserving Sony's original worker argument and tail-calling its original body.
Only one worker can claim this bootstrap during a player-process lifetime;
in-process replacement worker startup is unsupported and refuses admission.

`native_delivery.c` checks at most one pending offer before an RF permission
request. Empty delivery leaves the existing view available; a valid newer offer
renews it, with direct validation avoiding recursive receive/check calls. Invalid
offers refuse that RF operation. There is no background polling. Endpoint identity,
worker PID/thread and destructor cleanup are checked. Constructor publication
must precede thread creation; this is not a lazily initialized shared mailbox.
`xw_native_rf_publish` is GUI-owner-only and still requires actual policy admission.
Real pthread host/Sony-libc ARM tests exercise automatic initial receipt and
renewal without explicit receiver calls, destructor cleanup and descriptor-count
balance. The SDK owner loop pumps its publisher, and the paired GUI hook now
triggers it for native RF requests after authority binding.

`native_publisher.c` owns creation and publication of one READ view per qualified
native lease. Repeated prepare calls do not send duplicate offers. A new lease
can replace the old view only after the authority reports the old key stale;
pending delivery retains its endpoint for retry before enqueue, without saving
any native message/payload pointer. Closing publication resources does not release
the real lease. FD identity is checked before closing a pending endpoint; faults
latch instead of reporting delivery success and close owned observation endpoints.
An uninitialized-delivery negative test checks FD balance and retained real
ownership after publication failure.

`player/wireless_host.c` binds this publisher to an existing authority and is
called by the optional SDK owner-loop hook before player service work. One tick
handles a bounded receive and immediately flushes its newly pending reply; it
does not wait, create another thread, poll idle delivery or inspect storage.
Original-loop ARM tests check tick dispatch and errno preservation. Real pthread
host/Sony-libc ARM tests now use this actual backend for two automatic lease
publications/receipts, duplicate suppression, drain refusal and FD balance, rather
than manually constructing observation channels in that cycle.

The original GUI call0x10958 now reaches a source bridge at0x4d87fc, reads only
the native event word and invokes the qualified SDK request entry before
tail-calling original router0x3b994 with unchanged arguments/message. Events
0x4c0001/0x4c0005/0x4c0007/0x4cc001 can reserve the native Wi-Fi consumer and
publish/reuse its READ view. Other events do not allocate ownership. Some WPS UI
events can be configuration-only; reserving a lease does not power hardware.
The helper always delegates original routing, including on admission failure;
actual RF remains guarded later, preserving the stock error/cleanup path.

The trusted `xw_player_host_wireless_native_retired` endpoint requires the exact
generation/serial/consumer/mode key and does not treat a UI/scan event as evidence.
An old completion cannot release a new lease. After actual policy retirement,
the publisher closes/resets that view and its idle tick performs no socket poll.
Backend close
returns PENDING while that key is retained. Real pthread host/ARM cycles now use
the actual request handler to acquire/publish twice, refuse requests during drain
and wait for explicit modeled retirement before close. The conditional read-only
bootstrap below supplies initial authority. The original power-off result now
feeds the retirement notice path described below. The GUI now posts the original disable event once per draining lease, retrying queue backpressure without retaining native payload pointers. A never-admitted lease can adopt a cleanup-only view; this does not grant RF data access. Installing hooks alone does not grant authority.

## Original power-off result and retirement notices

The paired candidate redirects power-off at 0xb34f4 through the owned-cleanup
entry at 0x4d8834 (SDK return site 0x4d884c). Disconnect, cancel-connect and
cancel-WPS have matching cleanup entries. Current native ownership permits the
original call exactly once. Unknown ownership or an invalid image returns native
refusal. A sealed old native epoch performs a successful no-op, rather than
touching hardware now owned by another consumer. GUI cleanup uses its direct
authority check without waiting for a worker RPC. Original callees' return values
and errno are preserved when called; permission-only side effects are discarded.

`native_permission_snapshot` and `native_rf_worker_observe` issue a fresh QUERY
for the exact worker lease without granting data access. A stable scan completion
does not emit a retirement notice. Only an owned DRAINING or FAILED view can
produce WRO1: once drained, that same key cannot become data-allowed again.
Successful native return is followed by the original manager-state read and
the read-only four-module absence check. The worker sends the key, native result,
state, phase, module result and local seal over its existing delivery channel.
After qualified software-off and before sending success, the worker seals its
old context, closes its READ view and refuses further data work at that key.
Queued cleanup at that old epoch also becomes a no-op. A newer validated native
lease creates a fresh unsealed context; the old key is never revived. A notice
accepted by the connected datagram socket is sent once; unsent proof can be retried
without repeating hardware cleanup or flooding the control queue.

The GUI processes at most one notice per active publisher tick, requires its
own current drain/failure state, and retires only the exact native key when
result=0, public state=2, all four modules absent and worker sealed. A stale notice cannot
release a newer lease. A failure retains ownership and latches policy failure;
a later qualified success can clear that lease but does not silently repair
FAILED policy. Malformed notices never establish off evidence. No notice is
created merely because a thread or descriptor exits.

The module check is required by an original script defect. In w8_proc_unload,
the `let` test overwrites the status of later rmmod commands before err is saved.
`tools/test_stock_wlan_unload.py` executes the original function with Sony's
original BusyBox shell in a generic ARM guest: mocked failure of sd8xxx returns
failure, but mocked mp200_sdio, wlan_pm_register or wlan_pwr_ctrl failure can
still return success. The daemon correctly propagates script errors when they
exist; it cannot recover errors that the script has already hidden. Neither
the script nor its commands are modified by this firmware work.

Real pthread host/Sony-libc ARM tests now use the notice path for both retirement
cycles, rather than a GUI-side success assertion. They check stable-off suppression,
an old notice delivered during a newer drain, explicit native error, masked module
failure, a later qualified receipt, retained FAILED policy and descriptor balance.
Native power-off/state/modules remain fixtures in that chain. Original-wrapper
ARM tests separately check owned, refused and sealed cleanup, original result/
errno and changed-image refusal. Independent ESP-NOW ownership is not affected
by an old native GUI cleanup. Original stop requests and never-started lease retirement now have offline coverage. Lock ordering, lifecycle composition and real RF/power qualification remain outstanding.

## Read-only startup observation

The guarded original Wi-Fi worker entry now runs `native_boot.c` before entering
Sony's original loop. It reads original manager state and uses the shared
`radio_modules.c` parser to scan at most16KiB of
`/proc/modules` in256-byte blocks, then rechecks manager state. The modular radio
names wlan_pwr_ctrl, wlan_pm_register, mp200_sdio and sd8xxx must all be absent.
Only the software-closed state2 on both sides of that scan permits an8-byte
nonzero generation from `/dev/urandom`. Open/read/close paths are bounded and
read-only; native manager IPC still depends on the original daemon's responsiveness.
No command powers off hardware, unloads modules or writes configuration here.
Absence/state observations are software evidence, not measured rail/RF power or
proof against arbitrary external root programs.

The worker sends one64-byte WBS1 observation on the existing reverse delivery
direction. `wireless_auto.c` consumes it nonblocking on the original GUI owner,
qualifies the pinned image, and reads the original cached category6/item0x600
byte. Getter0x37f5c is void: its return register is not a status. Cached0 selects
Wi-Fi; cached1 selects Off; unsupported values refuse initialization. The original
getter span is included in generated image guards. Successful software evidence
initializes/binds the single authority and existing Settings/publisher adapters.
It never replaces an authority already supplied by the trusted owner.

While waiting, the GUI checks only the receipt socket; code qualification is
cached and rechecked on receipt, not rehashed on every idle dispatch. A rejected
observation latches unavailable until player-process restart, with no repeated
file probing, forced radio operation, setting repair or user-storage fallback.
Module/entropy/status errors leave authority uninitialized. Before receipt/binding,
the original GUI can coalesce native RF demand into one scalar flag, qualified
by the constructor GUI identity even before player-provider readiness. Binding
services that demand once if Wi-Fi is allowed. No message, payload pointer or
original task is copied or replayed; Sony's queue retains the original work.

A configured worker with no view can wait for initial delivery for up to200ms
of requested poll time, then the delivered view is validated by the existing
up-to200ms QUERY phase. These are separate bounded phases, excluding scheduler
and original RF-operation latency. The GUI never performs this wait. An offer's
successful validation is reused for that RF call, avoiding a duplicate QUERY.
No offer by the deadline returns native refusal and leaves real ownership alone;
later authority failure stops new pending demands. There is no automatic replay
after timeout. Whole original boot scheduling and these budgets remain hardware-
unqualified.

`tools/test_native_boot.py` checks128 qualification combinations, module-name/
chunk/error/size cases, entropy failure/short/zero input, codec rejection and four
executions of the actual original cached getter through production C glue. Host
sanitizers and Sony-libc ARM run with explicit manager/filesystem/entropy fixtures.
The pthread channel chain now starts from WBS1 automatic binding, tests rejected
startup and Off, and then runs two request/publication/renewal cycles. Its startup
observation, flag and loader identity are models; real filesystem/RF/startup
qualification and original retirement integration are still outstanding. Its
test-link-only poll marker forces the worker into the real initial wait before
the GUI can initialize, making the early-demand regression independent of sleeps.
Off/rejected startup also tests pending demand without granting hardware use.

The remote Settings backend requires an explicit read-only system-mode
callback in addition to native admission. Off, Wi-Fi and unknown deny launch
before a child exists. If selection moves away from ESP-NOW, the consumer asks
its service to stop cooperatively. It never writes the selection. Its normal
stop test retains ESP-NOW selection; a separate mode-switch test retains Wi-Fi
selection after remote retirement. Both use a modeled policy view, not native
device arbitration. The ARM chain now uses the actual policy core and keeps its
lease until explicit modeled owner-off evidence after supervisor/SDK retirement.
It refuses premature Wi-Fi acquisition and then grants another generic consumer
without reopening the player SDK. `tools/test_wireless_mode_policy.py` separately
checks stale leases, drain reversals, explicit failure/repair, existing Wi-Fi
adoption and wrong-thread/forked-copy refusal under host sanitizers and a generic
ARM kernel with Sony libc/LinuxThreads. These are not device handover tests.

Driver restoration, original power-off and cnmgr release now live in
`runtime/platform/wireless/radio_release.c`, without player/remote dependencies.
`wireless-remote/radio_stop.c` is a compatibility adapter for finite review
profiles. The platform release entry requires qualified exclusive ownership and
no borrowed stock connection. Determining the final owner belongs to the system
manager; this helper does not implement a global consumer counter. Ordinary SDK
close still has its existing behavior.

## Original menu location

`native_setting.c` supplies the private same-authority Settings transaction:
native rows0/1/2 map explicitly to Wi-Fi/Off/ESP-NOW, independently of policy
enum values. Highlighting and cancellation before confirmation change only a
preview. Confirmation requests a policy transition; with an active owner it stays
pending until qualified release. Repeated confirmation does not restart drain,
and cancel cannot revive a draining lease. A setting changed elsewhere makes the
old page stale. Host sanitizer and Sony-libc ARM tests cover preview, cancel,
all three choices, pending/release and stale-page refusal. This adapter is not
yet bound to the stock ARM callback; it must run in the authority's owner thread.
A separate-process Settings client must use its SELECT capability instead of
copying or directly accessing this policy object.

`native_callback.c` is a separately compiled pinned callback candidate. Confirm
and cancel pass operation/row through the existing request anchor; unrelated
events preserve all three arguments and delegate to the original callback.
Only a tagged W M response with a zero policy status navigates back to list0x5a.
An unpaired ordinary getpid return, pending transition, invalid row or failure
keeps page0x9a selected by native transition encoding. The trusted endpoint
`xw_wireless_setting_request` connects APPLY/CANCEL/POLL to the transaction and
polls a repeated pending confirmation without restarting it. It does not validate
the original code image/caller/thread; the host dispatcher must do that first.

`tools/test_native_wireless_callback.py` executes75 compiled ARM cases covering
all valid rows, invalid rows, delegation and missing/pending/error replies. The
anchor target is modeled in that focused test. The optional host build below
now composes the callback into an analysis ELF and pairs it with the dispatcher.
Page navigation/rendering and progress feedback remain unqualified. The
standalone display probe is still unchanged.

`tools/build_player_host.py --native-prepare --builtin-localization
--native-remote-settings --native-wireless-settings` composes this callback at
0x4d8500 and redirects only the qualified confirm pointer at0x405438. The
composition verifies an empty single executable slot, restores all declared
changes back to the input exactly, and preserves ELF headers and size relative
to that input. The preexisting Homebrew base has its own growth; zero growth for
this edit is not a claim of zero growth versus original firmware.

The paired DSO receives generated callback/pointer SHA-256 guards. Its dispatcher
handles only the generated qualified return site (currently0x4d854c), on the already-bound original
owner thread, preserving errno. The private `xw_player_host_wireless_bind` binds
an existing authority; it does not create an app-local authority, guess radio
state or initialize an off proof. The optional RF profile conditionally binds it after qualified startup observation.
`tools/test_player_host_anchor.py --native-wireless-settings` executes the
composed native callback, shim, actual endpoint and actual policy core, including
unbound/foreign-thread/code-change/pointer-change refusal. Identity, loader and
native-off evidence remain fixture supplied. This is not installed firmware.
The optional profile does not yet compose the three-choice display resources,
progress UI, persistence or original Wi-Fi interception.

In pinned Japanese1.11, Settings opens wireless list0x5a. Its six native IDs are
0xf60005,0xf60004,0xf60007,0xf60006,0xf60009 and0xf60008. The first item is the
wireless enable entry; callback0x7c8cc routes it to native page0x9a. SWD
sid-100-00 supplies the wireless labels and existing On/Off text. This is the
intended location for mode selection, rather than the remote consumer entry.
`tools/test_wireless_settings_entry.py` executes the original index lookup and
selection callback for all six rows under both classifications (12 cases).
It models state/UI boundaries and creates no changed menu or firmware.

The native on/off initializer is0x88400 (referenced at0x405304), selection
callback0x88480 stores a temporary index at0x4ee5d8, and confirmation0x88494 is
referenced at0x405438. The stored property is category6/item0x600:

| Original selection | Stored value | Meaning |
| --- | --- | --- |
| 0 | 0 | Wi-Fi enabled |
| 1 | 1 | Wi-Fi disabled |
| 2 | No original write | Unsupported extra selection |

`tools/test_stock_wireless_switch.py` executes those ARM instructions in4 init
and144 apply/cancel cases (72 valid-property cases and72 unsupported-value
cases). The original initializer normalizes nonzero stored
values to selection1. Confirmation writes only0/1 and may queue0x4c9007 with an
enable/disable argument depending on the supplied network/context state. Cancel
does not write. This establishes the original encoding; generic system mode
values must never be copied directly into that property.
The original apply routine does not repair a preexisting stored2/255 through
either ordinary On/Off choice in this replay. Display normalization is not a
persistence repair. No such value is written or "fixed" by these PC tests.

## Original Wi-Fi admission and retirement boundaries

`native_owner.c` now provides the private authority-thread lifecycle adapter for
a qualified native queue. It acquires one stock Wi-Fi lease before synchronously
calling the enqueue adapter, reuses that lease for subsequent jobs, refuses new
work outside stable Wi-Fi, and starts native stop once when policy begins drain.
It retains ownership until a separate trusted retirement callback reports
qualified off; pending keeps ownership and failures latch fault. Natural shutdown
keeps the selected Wi-Fi mode. A preexisting authority-issued stock lease can be
adopted explicitly; cnmgr state alone does not create that permission.

The adapter stores no native message or payload pointer and never delays enqueue
after returning admission. Its caller must classify RF work and preserve original
cleanup/cancel handling. The enqueue callback must copy the16-byte message and
report accepted status synchronously; native payload lifetimes remain unchanged.
Callbacks are private trusted adapters, not SDK-provided functions or evidence
from external consumers. There is no default binding to guessed Sony functions.
Host sanitizer and Sony-libc ARM tests exercise reuse, drain, exactly-once stop,
retirement, natural close, queue failure, failed shutdown and preexisting adoption.
Actual original-router binding and physical retirement remain unfinished.

Pinned SpiderApp calls the imported cnmgr power-on PLT0xda9c through wrapper
0xb3458, from0x61e10 (scan) and0x6205c (power preparation). Power-off PLT0xd4fc
is wrapped by0xb34c8, which has multiple cleanup callers. Connect wrapper0xb3538
calls prepare-connect0xda3c then connect0xe2ac; its caller0x62acc handles profile
and proxy preparation. Search PLT0xe108 is wrapped by0xb3784. These are static
references in the pinned image, not proof about other processes or indirect calls.

`tools/test_stock_wifi_admission.py` replays96 combinations of the original
0x61e10 and0x6205c ARM paths. Only public state2 calls power-on. States3/4 proceed
without a fresh power-on call. A successful scan reaches power-off even when
entered in state3/4, after exhausting modeled scan results. The scan returns1
and queues0x4c8009 regardless of the modeled power-off result. The power-preparation
path retains its original0x201/1 transitions and completion events.

Consequently, intercepting only power-on cannot enforce exclusive admission,
and native scan completion cannot release an ESP-NOW or stock Wi-Fi lease as
verified off evidence. A production adapter must cover scan/connect admission
and qualified retirement separately, preserve original error/cleanup flow, and
account for the original caller's execution context. Static decompilation does
not prove these operations run on the SDK GUI owner thread. Directly calling the
single-thread authority from an unqualified native worker is not permitted.
The replay models cnmgr, events and memory helpers; it creates no hook, firmware
or hardware qualification. No production Wi-Fi interception is installed yet.

The stock Wi-Fi factory0x61d48 constructs a three-group FSM at0x682d00.
Its event dispatcher0x61db4 calls the generic table engine0x17c608 synchronously.
`tools/test_stock_wifi_fsm.py` executes the original factory and engine for all
53 listed event/state routes, modeling only action bodies/logging. Group1/event
0x4c0005 selects power preparation0x6205c; group1/event0x4c0007 selects scan
0x61e10; group2/event0x4c0001 selects connect0x62acc. Arguments are preserved.

The upstream router0x3b994 normally queues those operations through0x336abc.
Factory0x3bf88 creates the queue and passes worker0x3b9a8 to0x337534, whose
original body calls pthread_create (minimum stack32KiB). That worker receives
16-byte events and synchronously calls0x61db4. Selected cancellation/cleanup
events0x4c000d/0x4c0010/0x4c0011 can instead dispatch directly; event0x4c000d
has a separate busy/cancel branch. Power preparation0x4c0005 is suppressed when
the modeled native hold flag is set. `tools/test_stock_wifi_event_router.py`
executes184 original router cases across event/group/hold/busy combinations.
Queues, flags and downstream dispatch are explicit fixture boundaries.

This establishes a real native worker path and a separate direct path, rather
than a single GUI-thread-only wireless interface. It rules out unconditionally
calling the GUI-owned policy object from stock RF wrappers. A future admission
adapter must preserve the queue/cancel contract and communicate across owners;
it must not block the GUI waiting on a worker that needs GUI progress. The
replays do not establish actual scheduling, lock ordering or physical cleanup.

The retirement boundary is stronger than scan completion. The expanded
`tools/replay_cnmgr_power_off.py` runs24 original daemon-handler combinations
across internal states/client counts and low-level success/failure, four original
low-level wrapper cases, and eight chained handler+wrapper executions. In the
chained cases, modeled stop/unload shell failures return16 through the actual
wrapper and actual daemon reply; the internal daemon state remains unchanged.
Success replies0 and changes the permitted internal2/3 state to0 (the public
client state encoding is different). This confirms error propagation without
modifying Sony's daemon or scripts. Refcounts alone still do not prevent power-off.

Only qualified exclusive ownership plus the original shutdown result, state
recheck and module absence can participate in the retirement adapter; a scan/UI completion,
dead client or elapsed time cannot substitute for them. Shell execution/results,
initial daemon context and open pipe descriptors are modeled here. There is no
physical driver unload or measured power/current. The original result observer
is now composed, together with proactive original disable-event posting. Physical shutdown remains unqualified.

There is a second native wireless configuration FSM, not just the three-group
scan/connect FSM. Factory0x62ef0 builds seven groups at0x682d24; dispatcher0x62f5c
uses the same original table engine. `tools/test_stock_wifi_fsm.py --secondary`
executes1,142 listed event/state routes with modeled action bodies and checks
exact callback arguments. The primary53-route test remains separate and passes.
The secondary test does not execute the WPS or registration operations themselves.

The admission replay now separately executes18 original PIN/Vista/PBC wrapper
cases, preserving their original argument registers and registration result.
All three still invoke registration when cnmgr_prepare_wps returns16. Therefore
rejecting only prepare-WPS cannot block the subsequent RF operation: admission
must cover the registration calls as well. These calls and logger results are
models; no real WPS, registration write or packet exchange occurs.

Secondary action0x6673c selects among wrappers0xb3ee4 (PIN WPS),0xb3f70 (Vista
PIN WPS) and0xb3ffc (PBC WPS). Each wrapper calls original cnmgr_prepare_wps
before its registration call. Actions0x666fc/0x67618 reach cancel-WPS wrapper
0xb4078. Other identified actions reach add/delete-register wrappers0xb39dc/
0xb3a54 and provider-reset wrapper0xb42d4, which are configuration operations,
not evidence of RF use. WPS admission and cancellation must be covered separately
from scan/connect; blanket blocking all configuration events would also block
unrelated stock settings. Full action classification and original queue bindings
remain unfinished. These are pinned static/ARM replay findings, not installed hooks.

## Native RF callsite candidate

`native_rf_bridge.py` composes a separate analysis candidate with460 bytes of
ARM anchors at0x4d8700, ten qualified BL changes in the original wrappers and
one worker-factory pointer change at0x3c138 (0x3b9a8 to0x4d87e0), and the GUI
router call change at0x10958 (0x3b994 to0x4d87fc), plus four owned-cleanup
calls, including power-off at0xb34f4.
Eight operations cover power-on, scan, prepare-connect, connect, prepare-WPS,
PIN, Vista PIN and PBC. Prepare-WPS has three original callers. Registration-data
edits are not patched. Current-owner cleanup keeps its original operation/result;
retired-owner cleanup cannot affect a new radio owner. Empty-slot and
mapping checks precede writes; reverting the declared edits reconstructs the
input exactly, with no further ELF growth relative to that input.

`native_rf_anchor.S` preserves callee-saved r7 and the original return address,
carrying operation/three original arguments through the existing capture-arg2
shim convention. `native_rf_dispatch.c` checks the operation/return-site pairing,
requires image qualification and worker permission, preserves errno and calls
the original imported function. Missing qualification returns native error1.
Both preparation and execution are guarded: prepare failure alone does not stop
the original WPS/connect wrappers from making the following call.

`tools/test_native_rf_bridge.py` runs48 combinations through original wrappers,
compiled anchors and the C receiver, checking allowed/refused/image-failure,
return values, argument registers and r7/errno preservation. Request-shim
transfer, image/permission and imported functions are fixture boundaries. It
does not itself register the receiver with the SDK dispatcher, compose
worker provisioning or establish original lock ordering. The standalone analysis
ELF is not ready to flash and no UPG is created. Its anchors must not be combined
with an unpaired host library or treated as a working Wi-Fi firmware.

The optional paired build now supports `--native-rf-gate` alongside
`--native-prepare --builtin-localization --native-remote-settings
--native-wireless-settings`. It composes the RF edits, generates exact code and
callsite SHA-256 guards, and compiles the receiver, worker permission/TLS binding
and clock/stat adapters into the existing host DSO. No second player copy is
introduced. Missing worker provisioning remains fail-closed; the build explicitly
reports `rf_worker_provisioned=false` and is not ready to flash.

`tools/test_player_host_anchor.py --native-rf-gate` checks52 combined scenarios.
Original RF wrappers and anchors execute through the actual host_pid.S capture,
host_hook.c dispatch, generated loaded-code guards and RF C receiver. Cases cover
allowed/denied RF, changed code/callsite refusal, native arguments and preserved
r7/errno, alongside the previous SDK/Settings routes. Permission, imported RF and
loader identity are still fixtures; actual TLS/thread permission is separately
tested in the Sony-libc ARM channel chain. The default seven-case SDK anchor
regression also passes. Three additional scenarios execute the worker-entry
bridge through the real shim, check original worker argument/body preservation,
and refuse changed code/factory-pointer bootstrap. Four GUI-router cases check
the original call instruction, scalar event delivery, untouched arguments/message,
thread/code/site refusal and unconditional original delegation. Two early-GUI
cases check constructor-role admission/refusal before provider readiness. Two
power-off cases plus owned/denied/sealed cleanup cases check execution, result,
errno and image refusal. Conditional
startup code is compiled, but original startup scheduling, native retirement
binding, lock ordering and physical RF handover remain unqualified.

## Display-only native probe

`tools/prepare_wireless_mode_probe.py` builds an uninstalled ELF/resource probe
from the source-built Homebrew/localization base. Its140-byte C payload replaces
only the init and confirmation callback pointers. It borrows the native GUI
controller's option object0x1d, copies its15-word parameter structure through
the original0x10a118/0x10a0d4 methods, and changes only parameter13 from2/3 to3.
Null objects or unexpected counts are left alone. The original initializer still
runs. Valid confirm/cancel events are deliberately returned to WLAN list0x5a
without calling the original persistence or network APIs.

The overlay labels the existing Wi-Fi/Off choices and appends ESP-NOW, preserving
all other STX text and the native Wi-Fi index ordering. Twenty-six ARM cases
check parameter preservation, missing objects, original init and discarded
confirmations. Reverting declared edits reconstructs the exact base; ELF size is
unchanged. No UPG or device operation is created. Actual object readiness,
subsequent factory resets, third-label resolution, layout and touch bounds are
not qualified by these memory models. This is a display probe, not an enabled
three-mode system or a package to flash.

The probe preserves UI index ordering0=Wi-Fi,1=Off,2=ESP-NOW. This is different
from the internal policy enum Off0/Wi-Fi1/ESP-NOW2; any later activation bridge
must translate explicitly. Its standalone wording IDs7310/7311/7312 are allocated
without the separate remote-row overlay. Those overlays must not be merged by
copying files: a unified builder needs one allocation order. The probe checks
init callback0x405304 and confirm callback0x405438 against the restored source
base and reverts only those pointers plus its RX payload for equivalence.

The three-mode native selector, original Wi-Fi request interception, authoritative
cross-process ownership and physical handover/power behavior remain unfinished.
No new enum is written to an original NVP field. The separate Remote Settings
analysis row is a consumer entry, not a substitute for wireless mode management.
Read [ESP-NOW implementation notes](ESPNOW.md) and [player integration](PLAYER.md)
for the current prototype and test limits.

## Original disable queue and idle retirement checkpoint

`native_stop.c` posts event0x4c0006 through original function0xa57f0 with
its duplicate-coalescing argument enabled. Native return0 means queue
backpressure and is retried on a later GUI tick; return1 accepts the request.
Other results retain uncertain ownership. There is no direct module unload.
`tools/test_native_stop.py` executes the original ARM queue function in five
cases: empty, duplicate, occupied cursor, lock refusal and changed-image refusal.

The worker call at0x3b9e4 delegates to original dispatcher0x61db4 before the
40-byte bridge at0x4d88a4 observes disable completion. Only disable6 reaches
the image check and retirement adapter; ordinary messages avoid that work.
The original dispatcher result, errno and callee-saved registers are preserved.
The paired anchor test covers disable, unrelated event and changed-image refusal.

An offer first consumed after revocation can bind a cleanup-only view (status2),
never a data grant. This lets a lease that never began RF retire after the
original idle disable path, which need not call power-off. Both retirement kinds
require a fresh owned DRAINING/FAILED view, closed manager state, absent radio
modules and a local seal before notification. WRO1 stores provenance kind at
byte56 (1=power-off result, 2=disable checkpoint), leaving bytes60..63 reserved.
The real-thread channel test covers this rapid-switch case, queue retry and
exactly-once accepted stop requests. Hardware state and module results are
fixtures there; these checks do not establish measured radio power-off.

## Unified Settings resource allocation

The Remote Settings overlay now calls `tools/wireless_resources.py` after its
independent Remote label is allocated. It reserves7310 for Remote, then7311 for
Wi-Fi,7312 for ESP-NOW and7313 for Wireless Mode, and produces the wireless
page SWD alongside the Remote page SWD. All languages must have identical index
counts; preexisting third-choice or unexpected original SWD references are
refused. `tools/test_wireless_resources.py` checks pinned original resources,
preservation of every preceding string and four refusal paths. This removes the
resource collision; the standalone display probe remains a separate historical
analysis tool and must not be copied over the unified overlay. The paired host builder now includes the selector initializer alongside the
authoritative confirmation callback. Native setting synchronization, selected-row
restoration and hardware rendering remain unfinished. These resource outputs are not a flash package.

## Paired three-choice initializer

`wireless_init_bridge.py` adds `native_mode_init.c` at the checked empty RX slot
0x4d8100 and changes init callback0x405304 while preserving the independent
confirmation callback0x405438. The initializer looks up the native object both
before and after original initialization, converting only count2 to3. Null or
unaligned objects and unexpected counts are left unchanged; no object pointer
is retained. Original return values are preserved and there is no radio, file
IO or background task. ELF length is unchanged, and reverting declared edits
reconstructs the input exactly.

`test_wireless_init_bridge.py` composes the source-built native Remote Settings
base and confirmation callback, then executes120 ARM initializer cases with
modeled UI accessors, missing objects, counts0..4 and object replacement during
stock initialization. It also refuses duplicate composition. This establishes
parameter and callback preservation, not actual widget rendering or asynchronous
factory behavior. `build_player_host.py --native-rf-gate` now includes these
initializer code/pointer digests in its loaded-image checks. It remains an
analysis candidate, not a firmware package.

### Current-mode restoration on page entry

The paired initializer now requests operation5 through its own generated,
callsite-qualified SDK anchor after original initialization. A stable authority
returns the distinct tag0x574e0000 plus native row0..2; this refreshes the local
Settings transaction from the authority. Draining/failed/unbound authority cannot
produce a valid row reply. The initializer accepts only that tag and range,
updates the original selection variable and posts the original dialog-selection
event0x20106 for option0x1d. Invalid or unpaired replies leave the original
selection unchanged. The query changes neither radio mode nor Sony persistence.
The host checks initializer code/pointer, confirmation code/pointer, GUI owner
and provider readiness before forwarding operation5. Native two-state setting
synchronization now delegates to the original confirmation function as described below; no value2 is written to it.

The current initializer is224 bytes including the tagged current-mode query and
native selection event; the earlier132-byte form only expanded the item count.
The expanded ARM initializer cases include all three valid rows, malformed and
pending tags, out-of-range rows and object replacement. The mode-policy test
also checks stable page refresh and refusal while draining under host sanitizers
and the original Sony libc in an ARM guest. Native Settings persistence and
physical widget behavior are not established by these tests.

The paired host-anchor suite now passes48 cases, including five current-mode
request routes through the actual SDK shim: bound, unbound, foreign GUI thread,
changed initializer code and changed initializer pointer. This checks the host
request boundary separately from the120 initializer UI/reply fixtures.

### Original two-state setting synchronization

After a successful SDK APPLY only, `native_callback.c` temporarily maps native
row0 to Sony On0 and rows1/2 to Sony Off1, calls original confirmation0x88494,
restores the three-state selection and refreshes the three-choice page on
immediate completion. Asynchronous transitions retain Sony's original result.
Cancellation, malformed replies and pending/failed requests never enter this
write path. The original function retains change detection, the cached-property
update and conditional0x4c9007 event posting; it can return4 to wait for original
event processing. Unsupported existing Sony values are not repaired. The SDK
mode is not persisted into this binary field.

The stock Wireless LAN settings list displays the binary Wi-Fi preference.
With ESP-NOW selected, that list displays Off, while the Wireless Mode
selector displays ESP-NOW. The list label does not report ESP-NOW link or
radio power state.

In the asynchronous disable path, the original secondary Wi-Fi actions
0x64504, 0x646b4 and 0x645a4 emit a completion addressed to the wireless
settings parent (group 90). The original menu dispatcher takes that route.
Reopening the mode selector then reads the committed SDK mode. The offline
replay executes those original actions with supplied power acknowledgements.

The request return site is derived from compiled instructions, not a handwritten
constant. `test_native_wireless_callback.py` passes75 ARM callback cases with
modeled SDK/native calls. `test_stock_wireless_switch.py --paired-callback` then
executes the real original confirmation body through the compiled callback for
144 apply/cancel combinations plus four original initialization cases. Storage,
manager state and event dispatch remain modeled, but the original write/route
conditions execute. Only values0/1 reach the modeled store; the native selected
row is restored, including ESP-NOW2. No device settings or firmware were written.

## GUI preparation drain boundary

`xw_player_host_wireless_prepare_stop(epoch)` is a private GUI-owner adapter.
It requires an existing qualified authority and a nonzero preparation epoch.
The first accepted epoch blocks future native RF start requests for this player
instance and clears deferred start demand. Repeated calls at that epoch observe
the same drain; another epoch is stale. Active ownership is quiesced through the
mode policy while the selected mode is preserved. Success requires no active
lease, stable policy and verified software-off. Failed/unverified policy is not
converted to success. Native cleanup/configuration events remain delegated.

The existing GUI tick posts the original stop for a native lease and services
worker permission/retirement notices. Independent ESP-NOW ownership remains
owned and must be retired by its consumer; this adapter does not force its
module unload or invent an off receipt. Backend close now waits for any active
mode-policy owner, not only the native Wi-Fi owner. No timeout implies off.
The actual-thread channel suite checks native drain completion, duplicate/stale
epochs, denied new starts, preserved mode and independent ESP-NOW release under
host sanitizers and Sony-libc ARM execution. Driver results remain fixtures.

The optional RF profile now calls this boundary from the original preparation bridge before native continuation.
The verified prepare-view adapter accepts root0x613e60/command3 only; it must not
be reused as a sleep/USB callback without evidence. Reentry after suspension also
needs a qualified new lifecycle; the current stop boundary intentionally has no
automatic rearm. No new firmware package or device action is produced here.

### Command3 preparation integration

`host_prepare_bridge.c` now validates the retained preparation view before
starting wireless drain in the optional RF profile. Pending drain holds original
prepare and records only the existing epoch/context. The existing GUI owner-loop
calls `xw_player_prepare_tick` after wireless processing; it revalidates the view
and waits for positive retirement before entering the SDK exit decision. An
empty SDK session set can use the original factory continuation; an active SDK
set still follows its session/worker drain. A failure holds the original path
without automatic retry or fabricated completion. The original caller's stack
output pointer is never retained across ticks.

`test_player_prepare_dispatch.py --wireless` executes the bridge/view/drain and
original command3 body with modeled radio retirement, resource readiness and
component effects. The ordinary profile keeps its previous direct behavior.
This does not identify sleep or USB entry points and does not qualify original
manager scheduling, remote-consumer retirement or hardware handover.

### Reversible native application handoff research

Original APF notification6 queues0x420024 and command6 preparation. Unlike
command3, this path can preserve the player process/root context for command7
restoration. A bounded original-instruction replay exercises both native menu
variants across close/reopen cycles: the receiver/coordinator enters the GUI
resume worker, receives its completion, reconstructs the interface and emits
the APF activation acknowledgement. The shared0x420034 completion event uses
token0x206 for close and0x207 for restore; event identity alone cannot authorize
wireless rearm. The permanent command3 stop gate must not be attached to this
reversible path without a distinct suspend/resume epoch and verified completion.
This establishes application handoff, not the physical sleep or USB trigger.

`check_home_parent.py --native-activation-route --lookup-manifest <manifest>
--report work/<report>.json` now accepts an explicitly identified archived
integration input for name lookup and records both AppList and manifest hashes,
with `current_release_qualification=false`. It no longer requires an absent
current-version integration artifact for this research mode. The explicit report
option keeps fresh test output under ignored work/. Native instructions execute
with virtual OS/IPC/allocator/display/manager service boundaries; no current
firmware acceptance, hardware power or physical wake claim follows.

### Reversible player wireless admission

`xw_player_host_wireless_prepare_handoff(epoch)` now implements a separate
reversible player gate. It requires a nonzero, monotonically fresh epoch and
qualified GUI authority. First entry quiesces current ownership; later polling
only observes retirement, so it cannot revoke a new lease acquired by another
Homebrew app. Native player starts remain denied while the gate is set. Other
consumers can acquire the independent system radio after original retirement.

`xw_player_host_wireless_resume_handoff(epoch)` is private trusted glue, not a
raw event handler. It requires the exact pending epoch, stable policy, no active
owner and verified software-off. It clears only player admission: no radio is
powered and no old lease is revived. Replayed/stale epochs are refused. A
permanent command3 stop dominates reversible resume. The actual-thread channel
suite passes native retirement plus independent consumer/replay cases under
host sanitizers and Sony-libc ARM execution; off evidence is still modeled.
The paired profile now binds command6 and command7/result observers as described below; standalone API tests still use trusted fixture observations.

Additional instrumentation of the original activation replay records the
coordinator call instructions: command6 reaches0x112fc from0x71f5c; command7
reaches it from0x71cd8 in both modeled menu variants. The two existing patched
prepare sites0x718e0/0x71aa4 both pass command3 and do not cover these paths.
Command7 entry is not completion and cannot itself authorize resume. The
recorded callers narrow the next native bridge work; they do not prove other
USB/sleep routes use these sites or establish original timeout/OS behavior.

### Original wireless component handoff contract

Fresh static decompilation and224 original ARM callback cases establish the
wireless component at0x3b498. Command6 calls0x3b404(1); commands7/21 call
0x3b404(0). That helper writes context+0x20. These branches return pending
token0 and enqueue no RF operation: neither is a radio-off or restore-complete
receipt. Command3 can instead post0x4c000f and return original token0x503 when
that internal flag is set.

Helper0x3b41c is not a shutdown primitive. With cached category6/item0x600 equal
to0 and environment query0xf674 reporting0, it posts0x420012(arg1) followed by
0x4c0005. Commands10/13/18 can reach that helper; command10 additionally posts
0x4c8012. Calling it as an off adapter could therefore initiate Wi-Fi work.
`test_stock_wireless_lifecycle.py` executes these original callback/getter/setter/
helper instructions, varying command, internal flag, primary/secondary state,
cached flag and environment result. Configuration/environment/queue are modeled;
no physical shutdown follows from a passing case.

Original coordinator0x112fc collects nonzero component tokens via0x48a14 and
completion0x11250 removes a token before PCS/finalization. The original wireless
command6 branch supplies no such token. A new handoff binding must explicitly
join this native completion contract and prove token identity, exactly-once
completion and stale-cycle refusal; a pause flag alone cannot make APF wait for
SDK retirement. No new pending token or command6 firmware hook is enabled yet.

### Holding command6 before its coordinator

A new bounded replay mode (`check_home_parent.py --defer-coordinator`, with the
explicit lookup manifest/report options) tests the existing command6 caller
returning without entering0x112fc. Before resumption, no component callback,
GUI-close event or pending-token registration occurs, and the modeled UI-manager
state is unchanged. The replay then invokes original0x112fc with root/command
and a fresh scratch output after the caller has returned. Original command6
cleanup and command7 recovery complete in both menu variants across four cases.
The original caller's output address is not reused for resumption.

This supports delaying the complete coordinator at0x71f5c instead of allocating
a new native pending token. Earlier token research remains relevant if a module
level integration is used, but no invented token is needed for this candidate
route. The current replay delay is a harness boundary, not production C wireless
waiting. Actual root lifetime, intervening events, APF timeouts and physical
scheduling still need qualification before this route is enabled in firmware.

### Production C deferred command6 candidate

`host_handoff_bridge.c` now retains a separate validated Root/epoch view for
command6. Interception always returns before original coordination; existing
GUI ticks poll the reversible wireless handoff, then stop SDK sessions through
the existing service-stop path. Pending work waits without forwarding; a failed
radio/SDK result or changed Root/code latches refusal. Once both retire, it
invokes original0x112fc exactly once with a fresh local output. No native pending
token or caller stack pointer is retained. Forwarded/faulted state cannot be
reentered or automatically reset. Command7 completion/rearm is still unbound.

The optional RF composition now redirects the checked BL at0x71f5c to the
existing prepare anchor, includes the new BL in loaded-image guards and links
the C adapter. The SDK dispatcher handles command6 separately from permanent
command3 exit, checks owner/readiness/image, and pumps handoff from the existing
owner loop. Other commands at this dynamic callsite delegate unchanged. The
Root read-only view now explicitly admits commands3/6; command7 remains refused.

`test_player_handoff_bridge.py` passes nine ARM C/view/original-coordinator
cases: ready, radio wait, SDK wait, changed Root, changed code, radio failure,
SDK failure, wrong owner and duplicate entry. Radio/SDK retirement, native
component effects and scheduling are fixtures. The combined new BL/shim/handoff path is now separately covered by the51-case
paired suite; command7 entry/result observers are now paired as described below, and the build
remains analysis-only with no UPG or hardware qualification.

The handoff BL edit is an explicit `native_handoff=True` composition option,
used by the paired host builder only. It verifies the existing44-byte prepare
anchor before changing0x71f5c. Standalone RF-wrapper analysis keeps its previous
callsite behavior and does not redirect command6 into an unpaired/empty anchor.
The full host-anchor suite additionally exercises the new BL/real PID shim/C
handoff route, changed-callsite refusal and foreign-owner refusal. Original
coordinator effects are intercepted in that combined test; its real body is
covered separately by the nine-case handoff replay.

### Qualified activation result and rearm

Original0x2680a8 confirms APF state: logical argument0 requests active state2;
argument1 requests inactive state1. It commits client+4 only after successful
send, receive and manager status, preserving failures. `test_stock_activation_confirm.py`
executes this method and its original logical-state getter across72 combinations
of initial state, request and transport/reply result. Transport/mutex/log effects
are fixtures; a passing case is not a physical manager acknowledgement.

The C handoff adapter now records command7 entry only after forwarded command6,
with inactive original APF client, empty native tracker and matching Root command6.
It captures the client sequence. A post-confirmation observation requires the
same client, native return0, active state2, a newer sequence, Root command7 and
an empty tracker. Only then may a GUI tick call reversible wireless resume. A
pending independent owner keeps the gate closed; success unbinds the old view
and permits a fresh handoff epoch. Wrong/stale identities or context/code errors
retain refusal. The client getter at0x265510 is covered by a pinned code/literal
guard before dereference. No old lease or hardware power is restored.

The paired RF candidate additionally redirects command7 caller0x71cd8 to the
existing prepare anchor and active-confirmation call0xb0624 to a new40-byte
observer at0x4d88cc. It invokes original0x2680a8 first, reports client/result via
the existing SDK shim (return site0x4d88ec), then restores the original result.
The loaded-image profile includes both edits, the active wrapper, original
confirmation method and client getter. RF anchor length is now500 bytes, with
no ELF growth. The standalone RF profile does not enable these handoff edits.

The C handoff suite now covers18 cases, including successful next-cycle reentry,
pending/faulted resume, failed APF result, missing command7 entry, stale sequence,
foreign thread, wrong client and changed getter code. Native APF observations and
radio/SDK retirement remain fixture supplied there. Combined native callback
scheduling, physical handover and firmware qualification remain incomplete.

The post-APF observer preserves the original32-bit result and callee-saved
registers; the SDK handler saves/restores the native errno around observation.
Failed confirmation does not release the handoff gate. An accepted confirmation
is recorded first and rearm is polled later on the GUI owner loop, outside the
original APF call. This avoids treating callback entry, a void wrapper return
or the shared completion event as success.

The52-case paired host-anchor suite now covers an entire command6 -> command7
-> post-APF-result -> next command6 cycle through actual modified BL instructions,
PID shim and production C handoff state. Its original coordinator and APF method
are fixture boundaries, covered independently by original-body replays. A failed
activation variant preserves native error16 and refuses the next handoff/rearm;
changed-site and wrong-owner variants remain refused. Native result/errno and
exactly-once forwarding are checked. This is stronger integration evidence than
calling the C observers directly, but not real manager, radio or device timing.

### Repeated Settings activation and original-player admission

The optional RF host now rejects new Settings requests and player-session offers
while its original-player handoff/stop gate is set. An already queued Settings
request is completed as CLOSED, while backend cleanup polling continues.
Command6 interception starts SDK service quiescence immediately, before waiting
for radio retirement, so new SDK work is not admitted during the radio drain.
The existing GUI loop still performs resource cleanup; no new polling thread is
introduced. The radio mode itself is not used as the player-admission flag.

Reusable private supervisors and explicit retired-backend renewal are described
in the wireless-remote app guide. Tests cover two complete Settings generations
with new RAM-only run values, unchanged template, another player command and
closed old descriptors, plus inactive admission/queued-request cancellation.
This does not automatically install the production Settings factory or qualify
physical radio power, USB ownership or Sony suspend timing.

### Private Settings consumer lease boundary

The original host now exposes private remote-mode/acquire/retired adapters to
the future Settings factory. They operate on the already bound publisher policy;
they do not construct or copy another authority. A fixed remote consumer ID gets
one exclusive ESP-NOW lease only while the player is active and mode is stable.
Repeated admission with the same exact key is idempotent; another empty key is
busy, and old retirement cannot release a later key. Mode drain/handoff refuses
new admission. Uncertain retirement latches policy failure and retains ownership;
a later positive release does not silently repair failed policy.

The actual mode-channel host/Sony-libc ARM suite checks these adapters against
the same policy object, including native Wi-Fi handover, new-generation stale
retirement, fault retention and inactive-player refusal. Retirement evidence is
fixture supplied. The adapters neither power RF nor install the Settings factory.

Static inspection confirms0xe5f4 is a cached environment-pointer getter and
0xf674 is a void copy of environment+4. This is not a status-returning USB query
or proof of completed USB handoff. The original RF helper's zero-value condition
does not establish that field's full producer semantics. The lifecycle replay
now calls this fixture value `environment_flag`, avoiding an unsupported USB
label. Production admission must not infer USB safety from that cache alone.

### Factory retirement and cooperative SDK closure

The paired RF/Settings build now includes `settings_factory.c`; startup still
reports automatic factory binding disabled. It uses the existing remote-lease
adapters, does not create another authority and needs a qualified native/profile
readiness callback. The actual ARM factory chain exercises three child runs,
ordinary off/reopen, mode handover and permanent original exit. It also inserts
a separate SDK generation42 between remote generations41/43, proving old
retirement does not stop the new service. Radio/native readiness remain fixtures.

The managed host now exposes next-generation and generation-scoped stop/retired
queries. `xw_sessions_stop_admission` and the private host quiesce adapter deny
new sessions/operations without destroying live channels. Native preparation
uses this admission barrier so a supervised client can receive explicit CLOSE
acknowledgement. After child retirement, generation-scoped stop drains local
resources; cleanup-only backend polling remains available when native exit
suppresses normal Settings requests. Immediate channel destruction previously
produced a player-close uncertainty in the full-process test; the fix preserves
that uncertainty check rather than treating EOF as success.

### Automatic binder and software readiness boundary

A reviewed reusable profile can now opt the host build into automatic factory
binding after SDK dispatch. The real automatic factory body is exercised in
the ARM service chain; the real main-loop/shim calls are checked separately
with a factory-tick fixture. The default profile remains unbound and the opt-in
registers OFF without launching RF. Invalid finite/artifact/source reviews are
rejected before compilation.

Readiness uses original singleton identities, active client, stable Root/pending
state and a distinct mounted user volume. It also rejects the original latched
busy field: decompilation shows original USB-event handling updates it after
recognized USB states. Zero still is not independent USB authority proof. The
fast active-state observer uses fixed qualified data without file I/O or RPC;
full image/mount checks occur at launch. Only command3/6/7 lifecycle composition
has the current integration evidence; additional sleep/USB routes are not
qualified by this software predicate. A fixture review must not be repackaged as
physical firmware qualification.
