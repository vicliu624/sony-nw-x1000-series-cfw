# Wireless Remote

## Native Settings work in progress

The page bridge now requires an attached view begin/end adapter before OPEN.
Failed acquisition leaves the page closed; failed end retains the page and
preview so Back can retry. An accepted end may still be restoring, so another
begin must return BUSY until native completion. Cancel/apply-success do not
navigate away if the release request is refused. HOME keeps its stock path.
The adapter context must outlive pending restoration as well as the bridge.

The current dedicated ARM integration fixture is
tools/fixtures/native_page_backend_chain.c, selected by --native-page-chain.
It checks missing/refused view ports, delayed close, cancellation without
start, committed start/stop, generation renewal and foreign owners. The view
completion itself is a fixture. It does not replace the generic backend test.
Evidence: work/remote-page-view-lifecycle-chain.log and the separately passing
work/remote-generic-mode-switch-current.log. Current composed page code is600
bytes with920 metadata bytes, no ELF growth, verified in
work/remote-page-view-port-registration.log and work/remote-page-view-port-guard.log.
This still lacks the deployed native view adapter/observer/Wi-Fi entry guard.

The composer also emits `remote_native_page_profile.h`, pinning allowed request
callers and code/metadata/registration/view-helper spans. The optional
XW_PLAYER_NATIVE_REMOTE_PAGE host dispatch branch requires bound GUI ownership,
no host reentry and a matching page image before invoking the private request
adapter. Its weak default is unavailable. The ordinary build does not enable
this branch or link an adapter. `test_remote_page_guard_dispatch.py --review ...`
executes actual composed page -> PID shim -> host dispatcher -> image guards,
with a backend fixture. It covers unbound/foreign owners, every span mutation,
unsupported loader identity, legacy toggle refusal, ordinary PID and errno.
Evidence: work/remote-page-guard-dispatch.log. This is not a real-loader DSO or
an installed view observer/Wi-Fi guard.

`compose_remote_native_page.py --host-review ...` now creates a separate
analysis ELF with the Remote entry/callback code in mapped padding and194 UI
states. Both original registration paths keep initial group193. The original
Root/Pcs156-entry layout is unchanged; Remote uses existing control29 only
under the qualified view lifecycle adapter. The code/metadata are576/920 bytes
in the checked build, with no ELF size growth. `test_composed_remote_native_page.py
--review ...` executes both patched registrations, actual Settings row lookup,
entry/cancel/ready flow and unchanged stock-selection delegation. An unpaired
request retains interactive Settings rather than entering a waiting state.
Evidence: work/remote-native-page-composition.log and
work/remote-native-page-registration-check.log. The guarded DSO adapter/view
observer and ordinary Wi-Fi entry guard remain unpaired. This is not a UPG.

View restore now checks the original menu context/state through736c0/17ca18:
begin requires interactive Settings; end must originate from Remote group194;
completion requires interactive Settings again, its active control97, settled
layer states and the existing inactive/draw/property checks. A bounded observe
tick performs these reads and restore without synthesizing a ready event.
HOME/playback can leave an inactive borrow until Settings is reached. A
production integration must also prevent the ordinary Wi-Fi initializer from
reusing a still-borrowed view; that entry guard is not installed yet.
work/native-choice-view-menu-ready.log executes the original menu ready
transition with supplied scene/layer sequencing, including20 restore cycles.
This still does not qualify actual renderer ordering or a production observer.

`native_choice_view.c` is an unpromoted existing-control29 borrow/restore
prototype. It changes count3->2 and SID13900->13901 without adding Root slots
or freeing/replacing the original object. It uses the original active-layer
query and Pcs parameter functions; restore additionally requires this scope's
completion epoch, no active layer, an empty draw queue, unchanged view identity
and expected borrowed properties. Unexpected content is left untouched.
Twenty repeated restores pass with exact view/Root bytes in
tools/test_native_choice_view.py (work/native-choice-view.log). Layer state,
draw count, code/resource readiness and completion are fixtures. The real
completion producer and renderer order must be bound and verified before use.
No ordinary firmware profile includes this helper.

Remote choice resource13901 (`ucs2-dev-sid-139-01.swd`) is228 bytes and reuses
the existing Remote title7310 and On/Off255/256. The original SID filename
loader, SWD parser and STX lookup pass33 checks across11 languages, including
the title key0x400. File/stat/mapping and STX context are fixtures, not physical
font rendering. See tools/prepare_remote_choice_resource.py,
tools/test_remote_choice_resource.py and work/remote-choice-resource-check.log.

The prototype's cancel/apply-success return now posts actual Settings control97,
sets category2 and waits in0201 for a ready event before becoming interactive.
It does not use73608 as a stack pop: that function is the original playback
shortcut. Event4a011b retains that shortcut via an explicit playback callback;
the original helper and group56 initializer execute in the FSM replay, with
the playback-service leaf modeled. HOME remains a separate stock path.
Evidence: work/remote-native-page-return.log and
work/remote-native-page-return-chain.log. View close/restore timing is still
unqualified; no production registration or device package is generated.

`native_page_bridge.c` now connects the page protocol to the actual private
backend. Open/query/preview/cancel do not enqueue control. The GUI owner and
backend generation bound the preview; a retired generation cannot apply later.
Closing a page discards only preview and does not undo a committed request.
Wrong-owner calls and unbinding an open page are refused. The backend must
outlive its bound bridge; cancel then unbind before discarding either object.

Run tools/test_remote_supervisor.py --settings-backend --reusable-sessions
--native-page-chain for actual C page callbacks -> bridge -> managed queue ->
backend -> supervisor/service retirement in the ARM guest. Sony UI/category
leaves and RF/media remain modeled. The same fixture checks foreign-owner
refusal and a real backend renewal invalidating the old page generation.
Evidence: work/remote-native-page-full-chain.log. This is not original-loader
native registration, resource rendering or physical acceptance.

`native_page.c` implements private prototype open/init/preview/confirm/cancel,
category-pop return and stock HOME callbacks. The prototype uses UI group194
and borrowed Pcs control29; the ordinary builder does not register this UI yet.
The original choice event map separates selection0x4a0111 from confirmation
0x4a0119, back0x4a011b, HOME0x4a0110 and ready0x4a0116. Its offline replay clones
the stock module descriptor and replaces only the page-specific callbacks.
Open refusal, preview without apply, confirm On/Off, cancel, back, HOME and
apply refusal all pass through the original FSM with the actual C callbacks.
Resource rendering, owner request bridge and category leaves are modeled.
See tools/test_remote_native_page.py and work/remote-native-page.log. No page
resource, production startup patch or firmware package is created by this test.

The private backend now provides `wr_settings_backend_query` and
`wr_settings_backend_request_enabled`. Query is owner-only and has no polling,
process or radio side effect. Its `requested_enabled` field is intent, not RF
readiness; FAULT reports unknown. Explicit On/Off requests go through the
existing managed queue. Repeating the same target does not toggle it, and an
opposite target while queued returns BUSY. Wrong-owner and native-exit requests
are refused. A query failure preserves the caller's output.

The original-queue/backend/supervisor tests exercise repeated queries, explicit
start/stop, duplicate/conflicting requests and foreign-owner refusal, plus the
mode-change retirement path. RF and original media are modeled. Evidence:
work/remote-explicit-settings.log and work/remote-explicit-mode-switch.log.
These APIs are not yet connected to a completed native On/Off page. The old
entry's action-on-click path must be replaced, not wrapped as a page-open action.
No firmware package or device update is made by this work.

This application is under development. The graphical `main.c` is still a
generated SDK scaffold; it is not a working wireless player remote.

Source: main.c. Build: python tools/sdk.py build wireless-remote.
Preview: python tools/sdk.py preview wireless-remote.
Touch the on-screen button; Back to apps exits.
The scaffold has no persistent state or networking.
Offline entry checks: --help, --version, --selftest. Preview is not hardware qualification.

## Native remote service entry

Library requests use WLBQ/WLBR with a single bounded metadata item and the existing
SDK browse API. The native remote session explicitly requests READ, CONTROL and
BROWSE; the descriptor does not grant database/file writes. Final duplicate reads
reuse the cached reply. A BUSY provider read is continued by the serialized worker
at 100 ms intervals for up to two seconds; this is completion of an admitted asynchronous
read, not replay of a radio request or playback control. Stop disables all further
read steps. Core2 alpha.7 uses a five-second reply window and requires explicit navigation
or Reload after timeout. No periodic library scan is introduced. Unsupported
views remain unsupported; native containers are not reclassified as playlists.

`tools/prepare_remote_first_use.py --component-review work/.../review.json
--pairing-review work/.../review.private.json` freezes the eight matching external
files after rechecking their source receipts and identities. It writes only under
ignored work. The separately invoked `Install-RemoteFirstUse.ps1` requires a plan,
drive and expected Sony disk serial, validates WALKMAN/FAT32 and USB disk identity,
and uses RemoteFirstUse.psm1 for no-overwrite staging/commit. It records one
installation attempt on the PC before device writes; uncertain attempts require
review. This installer never flashes firmware or starts a device program. Do not
install a set onto an older unmatched player build. These are private diagnostic
materials, not a qualified public release or recovery mechanism.

`tools/prepare_remote_pn_proposal.py --pairing-review work/.../review.private.json`
creates first-use counter proposals for a fresh, unused pairing. Its staging
directory is created once, with exclusive file creation. These are initial
records, not backups: never install them over existing scopes or restore them
after radio use. Device deployment must independently validate user storage and
USB ownership and use no-overwrite creation. The tool itself is PC-only and does
not install anything. Actual C counter-store interoperability is checked by
`tools/test_remote_pn_proposal.py` using synthetic temporary data.

`tools/prepare_remote_pairing.py --player-mac MAC --remote-mac MAC` prepares a
fresh private pairing proposal under ignored work/remote-pairing. It generates
matching player config.bin, PMK16+API-LMK16 session.keys and a fixed-width MCU
USB command. It never opens serial/network connections, installs files or creates
PN journals. The USB command contains secrets and must not enter logs or Git.
The default proposal format is XWRUN001. Adding `--host-review` verifies the
current source-built native mode-reader host and enables XWRUN002. The reusable
supervisor accepts that same host review in addition to the retained finite-lab
review format. Mode capability is not inferred from a filename. Existing
keys/counters are never automatically overwritten or migrated.

The managed owner's optional `--data-leaf wireless-remote` build uses
`/contents/HOMEBREW/data/wireless-remote` for candidate radio images, session.keys
and the pn directory. It compiles all candidate and state paths together;
the default laboratory build retains espnow-test. The supervisor builder accepts
the exact matching runtime subdirectory for service.arm, owner.arm and config.bin,
in addition to existing reviewed laboratory directories. It does not accept an
arbitrary system path. The isolated ARM chain's `--formal-data-layout` option
checks real-owner startup refusal, cleanup and retry from this runtime location.
This check does not start RF. No installer, pairing or PN migration is implied:
existing packet counters must never be replaced with seed records.

This consumer requires an explicit read-only system-mode view and refuses launch
unless ESP-NOW is already selected. It never selects the mode. Mode changes away
from ESP-NOW request cooperative consumer stop; closing remote alone preserves
the selection. Hardware policy belongs to the [wireless platform](../../platform/wireless/mode.h)
and the [wireless design](../../../docs/sdk/WIRELESS.md), not the remote menu.

The supervisor also accepts `--delivery-fd FD GENERATION` with the existing
explicit lab confirmation arguments. A trusted original-owner manager supplies
an already connected AF_UNIX datagram descriptor and an SDK-issued player
capability; this path creates no startup rendezvous directory and does not exec
or restart the player. It verifies the socket, exact generation and READ/CONTROL
grants before starting the existing service/owner children. This transport does
not authorize a caller or generate a fresh peer/config profile on its own.
`tools/test_remote_supervisor.py --direct-delivery` runs the actual supervisor,
service and SDK host with modeled radio/media in an ARM guest. Separate
`--bad-generation` and `--bad-grants` cases reject before the owner starts.
Default builds leave the Settings queue unbound; a reviewed opt-in automatic profile now composes the backend as described below.

`supervisor_process.c` supplies the private same-owner-process launcher for that
backend. It forks only after explicit prequalified admission, execs a fixed
immutable supervisor path, supplies the delivery capability and strips inherited
preload/grant environment. The parent does not wait for config checks or RF
startup; later polling drains bounded output into a512-byte RAM tail and reaps
with WNOHANG. No disk log or temporary file is created by this launcher. Abnormal
exit latches uncertainty; keep polling to reap, and do not reset the object into
a successful/off state. Descriptor identity is checked before close. Default
runtime signal handling is not replaced. Vendor atfork/SIGCHLD behavior, native
admission and UI timing remain unqualified.

`tools/test_supervisor_process.py` checks actual host fork/exec, inherited-FD and
environment cleanup, bounded logs, rejection cleanup, abnormal reap and FD reuse
under sanitizers. `tools/test_remote_supervisor.py --managed-process` uses this
same C launcher in the real supervisor/service/SDK ARM guest chain. Combining
it with `--bad-generation` exercises rejection through the process launcher.
These tests do not bind a launch backend into the installed player's Settings.

`native_settings.c` is a separate analysis-only stock-menu callback.
`tools/prepare_remote_settings_row.py` builds it into checked unused RX padding,
appends item0xfd0000 after the Japanese Settings/Language entries and prepares
SWD/STX wording. Old selections delegate unchanged to the stock handler; the new
selection issues one request anchor and retains the Settings page. The opt-in
`build_player_host.py --managed-host --engine-provider --native-prepare
--builtin-localization --native-remote-settings` profile consumes it through a
guarded owner-side queue. Existing/default hosts retain ordinary PID fallback.
No remote backend is bound by default. This is not an enabled switch or a
firmware package: activation, progress/status UI and original RF admission must
be integrated before it can be offered for installation.

The compatibility `radio_stop.c` delegates to the generic platform wireless
release implementation, using guarded stock power-off before cnmgr RELEASE/fin. It
requires a controller started without stock-disconnect permission, no borrowed
Wi-Fi connection and an explicit exclusive-owner callback. It keeps ownership
on a power-off/fin error and never changes generic SDK close behavior.
`tools/test_xnow_full_control.py --remote-stop` exercises this adapter with the
actual controller/session/manager code under host sanitizers and stock-libc
ARM926 execution. Driver operations and cnmgr calls are modeled. The finite
qualification owner's default build retains its previous restore/reconnect
path. `tools/build_remote_owner.py --power-off-exit` explicitly selects this
adapter in that actual owner executable, disables stock-disconnect permission
and uses the existing operator-confirmed lab admission plus cooperative gate/IPC
checks. This is not global Sony ownership qualification or an installed Settings
switch. `tools/test_full_owner_runtime.py --power-off` checks actual pipe HUP,
inflight TX retention, restore/power-off before data cleanup and DONE+EOF, and
withholds the receipt on cleanup failure, with modeled stock/RF effects.

The opt-in `XWRUN002` configuration enables mode queries against a matching
mode-capable host; legacy `XWRUN001` never sends the new SDK request. The private
supervisor review must explicitly mark mode-host support for version2. Mode
telemetry uses a separate authenticated48-byte WRM1 frame with session, independent
sequence, validity, native value and menu index. It is sent on change and at a
low-frequency heartbeat; unavailable reads send an explicit invalid state.
Core2 validates the frame and selects nothing when validity/freshness is absent.
Before-sample scheduling lets mode telemetry run even when status transmission
takes longer than its nominal interval; control receipts retain precedence.

`tools/test_remote_service.py --play-mode` executes the actual ARM service and
SDK host with modeled media/radio. It checks the real mode RPC and authenticated
native5/index4 publication alongside pause/deduplication and cleanup. This is not
five-mode physical acceptance or a qualification of the new Core2 hardware.
`--all-play-modes` additionally cycles all five native values0,1,2,3,5 and
requires authenticated packets for every corresponding index before the fixture
may stop. This full-process five-value regression passes; original settings and
radio are still substituted, and no Core2 firmware is installed by the test.

The intended integrated layout uses one player executable; an additional full
player copy is not part of the system-partition budget. Original firmware and
rollback evidence remain on the development computer. The current one-start
qualification staging still contains retained user-volume player copies; that
temporary test layout is not the final integrated filesystem layout.

Stock playback-mode regression remains unqualified: normal order, repeat-all,
repeat-one and shuffle must be checked through actual track boundaries while
remote is enabled, after remote shutdown and across app switching. Verify that
manual previous/next does not silently change the selected stock mode. The
managed player SDK reads all five stock modes; mode-setting is not implemented.
Working volume/skip does not prove track-boundary repeat/shuffle behavior.

`service.c` is the actual separate service executable, built with
`python tools/build_remote_service.py`. It is not the graphical scaffold or a
default-enabled system listener. A trusted supervisor must first supply the
authorized player stream, ready encrypted radio-client pipes and armed owner
retirement reader. It then explicitly executes:

```text
wireless-remote-service.arm --run CONFIG_FD PLAYER_FD RADIO_IN_FD RADIO_OUT_FD RETIRE_FD
```

Each FD must be distinct and at least 3. The config FD is a nonblocking read-only
FIFO carrying exactly 80 bytes followed by EOF: magic `XWRUN001`, player
generation u64LE, remote session u64LE, peer MAC6, zero reserved2, application
authentication key32 and retirement cookie16. Secrets are not command arguments,
environment variables or stored files. The sender assumes the separately
managed owner has already configured its encrypted peer and PN journals. It does
not discover hardware, load a driver, pair, reconnect, create a log or write a
filesystem. Supervisors must direct health output to a bounded user-volume log
or discard it, never a system-volume persistence path.

SIGTERM/HUP requests orderly stop without cancelling the player-close RPC.
The owner retirement reader uses explicit `xnow_handoff_adopt_reader`, with
CLOEXEC restored. An uncertain radio receipt retains the process for supervised
repair. A known radio retirement with failed player closure exits unsuccessfully;
the supervisor must not reinterpret that as a clean original-app transition.

`tools/test_remote_service.py` executes this actual ARM program with the actual
player host on the computer. It verifies real SDK status, one PAUSE, cached
duplicate receipts, observed paused status, SIGTERM, player closure, client-pipe
EOF and owner retirement. The player backend and radio owner are models; no RF
or hardware is exercised. Supervised physical owner startup and the original
Settings/exit integration remain incomplete. Do not install this entry as an
unconditional boot service or run it with guessed descriptors.

## Read-only qualification client

### Private finite supervisor

`supervisor.c` is the C launch entry joining the startup rendezvous and both
executables. Build it with `tools/build_remote_supervisor.py --review ...` using
a private work-directory review. The builder pins service, owner and 80-byte
configuration hashes and permits only the explicit test user-volume directory.
The executable checks those exact inputs through the existing no-symlink file
checker before creating its fresh RAM rendezvous. No nonce, key or payload is
installed in the system image by this builder.

After receiving a READ+CONTROL player stream, it forks the independent RF owner
and service with separate whitelisted environments. Children close every
unintended inherited FD and restore inheritance only for their explicit pipes.
The parent closes unused command/response ends. It independently verifies the
owner's real completion record plus EOF, then forwards that verified result over
a separate receipt pipe to the service. This keeps the real owner receipt
available even if service exec/startup fails. Child status is reaped; no deadline
kills an in-flight owner. An uncertain owner receipt retains the supervisor.

The RF owner now reports a correlated startup-failure record only from branches
before its first controller step, when no radio/manager mutation has begun.
Original-libc ARM tests verify this refusal on a non-Sony root and preserve the
normal test entry. The supervisor itself has passed ARM help/argument checks;
its full fork/exec/rendezvous path now passes `tools/test_remote_supervisor.py`
inside an isolated ARM Linux guest with original libc. The actual supervisor,
service and SDK host execute; the owner/media backends are models. The test
verifies user-volume input admission, inherited-FD closure, one PAUSE with a
cached duplicate response, owner DONE+EOF verification, receipt forwarding and
both child exit statuses. It does not qualify the real radio or Sony kernel.

The first finite physical attempt did not yield a Cardputer player session in
UART observation. Logs and post-run owner/overlay checks remain pending; neither
physical success nor automatic restoration is established by the elapsed window.

### Finite real-radio owner entry

Physical timing located a repeated file-integrity scan in the READY loop:
one unchanged storage check took 497 ms on X1060. The finite owner now keeps full
root/candidate hashes before controller mutations and uses current mount/root
read-only checks in the packet loop; the latter measured 5 ms. Both read-only
measurement helpers were removed after execution. Generic owner lease checks
remain in place. This does not qualify global original-Wi-Fi/USB arbitration.
In the subsequent bounded physical run, Cardputer accepted 72 additional status
packets with no source/auth/session/sequence rejection. Its observed session
remained valid until the test ended. Post-run owner timing/retirement logs and
the user's volume-control result are still pending for that run.

`python tools/build_remote_owner.py` builds `espnow-test/remote_owner.c`, a
separate 60-second qualification owner for the service's real-radio test. It
retains the previously exercised test context, exact root/candidate guards,
security/PN preparation and original driver restoration. Test-context C inclusion
is deliberate lab-only reuse, not a production daemon or application dependency.
The ordinary espnow-test main is excluded by a compile switch in this entry;
the default entry is separately built and entry-checked as a regression.

The owner receives explicit command/response/completion FDs, a correlation cookie
and the peer MAC. Keys remain in the verified test user directory. It initializes
the actual generic owner runtime, configures the encrypted peer, serves SDK
requests and reports DONE only after controller restoration, data-FD closure and
owner release. A 60-second deadline requests cleanup; it never forces a pending
driver operation to finish. Uncertainty retains the process. A supervisor must
close unused FD copies, supply fresh peer keys/PN scopes, keep the current
operator assertions true and wait for real completion plus EOF. This entry has
passed original-libc ARM help/invalid-argument checks only; it has not run on
hardware. It is not the final system owner, Settings integration, global native
Wi-Fi exclusion, sleep/USB policy or RF power-off implementation.

`probe.c` is a separate temporary C client for qualifying the real original-player
host before adding radio control. It is not part of the scaffold build and does
not install a service or change firmware. Build with
`python tools/build_player_live_probe.py` on the supported WSL host.

By default the probe receives a specifically authorized READ-only session through
the private startup rendezvous, obtains one snapshot, requests a close receipt
and detaches without playback commands. It requires a fresh RAM IPC directory,
32-hex nonce and nonzero generation. No response means a bounded failure, not
success. Optional `--detach` starts a bounded background qualification process;
the deploying caller must validate and direct output to user storage, not a
system-backed log. Temporary IPC lives in RAM and is removed on ordinary exit.

`tools/test_player_probe_startup.py` verifies its handshake, stream receipt,
snapshot and close against a sanitized model host with the actual ARM client
and Sony libc. This model test does not prove original Sony GUI operation;
separate physical results are recorded below.
`tools/prepare_player_live_start.py` prepares private, pinned
one-start files without deploying or activating them. Its output contains Sony
binaries and a private nonce and must never be published.

## Physical player qualification

The temporary client has read real state, track identity and title/artist/album
from the Japanese X1060 original player. A bounded observation reached PLAYING,
received five state/metadata notifications and obtained a successful close
receipt. A separately granted control test observed volume 9 to 10 and back to 9.
Private logs remain in ignored work storage.

These tests used a checked, one-start RAM bind mount; the wrapper detached the
mount before starting the candidate. The root partition was not written and no
firmware was flashed. The original entry was checked after return. They do not
qualify browsing, skip/pause/resume, sleep/wake or the combined radio link.

The probe defaults to READ only. `--observe` waits for actual PLAYING and complete
metadata; `--volume-roundtrip` explicitly requests CONTROL and changes volume
once in each direction. No command is replayed on an uncertain outcome.

## Required final radio behavior

The ESP-NOW SDK and player-control SDK are independent services. This remote
feature is their consumer, not their owner or a mandatory bridge between them.
When the original player exits for Homebrew, its remote session must drain and
release radio ownership. A Homebrew application may then independently acquire
ESP-NOW without starting the player. Driver availability persists across this
boundary; a player-owned listener must not. This lifecycle still needs physical
integration and qualification.

The private original-player host now has optional
`xw_player_host_exit_dependency` registration for a trusted owner-thread manager.
After its own SDK drain, the original prepare continuation can wait for that
manager's nonblocking retirement-receipt poll. BUSY keeps waiting; an error
retains the existing fault outcome; successful retirement allows one native
continuation. Without registration, the existing path is unchanged. This is a
generic dependency hook, with no ESP-NOW types or driver calls in the player SDK.
It is not automatically registered by external apps and is not active in the
previously installed physical candidate. Radio-manager registration and actual
shutdown receipts remain to be connected before sustained remote operation.

`tools/test_player_service_drain.py --host-wrapper --inherited-delivery
--exit-dependency` checks delayed retirement through the actual host wrapper,
broker and reader threads under a generic ARM kernel. Native original-player
contexts and dependencies are modeled; this does not qualify physical exit,
sleep/wake, USB ownership or RF power-off. `tools/test_service_lifecycle.py`
also checks dependency failure without invoking the native continuation.

### Cardputer remote candidate

`worker.c` is the serialized application lifetime around the two independent SDK
clients. It samples status at most every 500 ms while pumping commands/receipts.
Stop disables further sender steps, waits for the player-close callback, detaches
only its own radio-client pipes, wipes application keys and waits for the
manager's verified owner-retirement callback. Pending cleanup cannot report DONE;
cleanup uncertainty is retained. A separate process/thread must use manager IPC,
not access this worker object concurrently. The current stock-restoration
receipt must not be described as proof that the RF power rail is off.
If player close fails, the worker still detaches the radio client and waits for
radio retirement. It retains the player failure after radio cleanup rather than
leaving RF active or claiming a clean native transition.

`radio_retirement.c` supplies the real generic radio SDK handoff adapter. It
consumes an already armed supervisor-owned handoff, waits for the SDK parser's
correlated `XRFDONE1` record and EOF, then closes the owned reader. Empty EOF,
wrong cookie and descriptor identity failures retain a fault. A reported startup
failure is retained separately from the fact that the owner has retired.
`tools/test_remote_retirement.py` verifies actual pipes, partial records and the
real SDK parser under host sanitizers and original-libc ARM926 execution. The
completion records are fixtures; no RF or original-player action is performed.

`tools/test_remote_worker.py` builds the C fixture with host sanitizers and the
original-libc ARM926 runtime. `tools/test_remote_worker.c` tests this business
ordering with modeled services. It also passed native Windows C execution;
the Linux checks passed from a temporary Linux-local source copy after shared
filesystem compiler I/O blocked an unrelated running regression. Those checks do not attach it to the
physical player or qualify the radio. The manager IPC and owner startup still
need integration; this module is not itself a background system service.

Cardputer alpha.3 includes a queued ESP-NOW receive callback and a native status
screen for real WRS1 data. It requires an explicitly configured encrypted peer
and additionally verifies a 128-bit HMAC-SHA256 tag using a separate per-session
32-byte application key. The signed frame is 893 bytes. Source MAC, provisioned
session and strictly increasing sequence must match. Five seconds without fresh
valid status marks the display disconnected. No synthetic player state is used.

Local USB provisioning accepts `pair MAC SESSION AUTHKEY LMK PMK`: fixed-width
hexadecimal lengths 12, 16, 64, 32 and 32, separated by single spaces. Session is
big-endian hexadecimal text; its binary WRS1 encoding remains little-endian.
Provision only fresh random keys/session, with matching values on the X1060;
do not reuse a radio key across resets without the required PN continuity.
Credentials live in RAM, are not echoed and are cleared by `unpair` or reboot.
Re-pairing requires explicit unpair. Overlong USB lines are discarded as a whole.
Keyboard controls are A/D previous/next, W/S volume up/down and Space play/pause.
They require fresh status and an advertised operation. Space resolves to an
explicit play or pause request from the known state, never an implicit toggle.
One request may be outstanding; no timeout retransmission or key auto-repeat is
performed. A missing receipt is shown as unknown, not as successful execution.
The GPIO matrix follows the original Cardputer hardware map; native scanning
and physical end-to-end operation still need device qualification.
Alpha.3 was written to the previously identified original Cardputer on COM17
using ROM/no-stub and verified by the flasher. The running application reports
the expected version, initialized 240x135 LCD and radio, no pairing and no player
session. This is boot/initialization evidence, not reception or control evidence;
the flashed image hash and serial receipt remain in ignored deployment records.

`status_sender.c` composes already-admitted player and radio SDK clients on a
serialized application worker. It reads a real provider snapshot, signs it and
submits one status at a time. It distinguishes queue admission from TX completion;
busy sampling does not repeat the read or allocate another sequence. Its caller
must schedule heartbeats and stop on error, then close the player session and
drain/release the radio using their independent lifecycle interfaces. Clearing
application memory is not a radio-off receipt.

`control.c` defines authenticated 48-byte WRC1 commands and WRA1 receipts.
`control_player.c` dispatches through the independent player SDK. It retains the
last request/result and refuses older or changed duplicate requests. In
particular an UNCERTAIN result is cached, never replayed. The sender accepts
control only from its authenticated paired source and matching session. Receipts
are sent separately from status; ACCEPTED is not observed playback. This ledger
is session-local and does not promise exactly-once behavior across crashes.

`tools/test_xnow_client.py` also checks this composition through the actual player
client, partial FIFO radio stream and Cardputer receiver core. The player provider
and RF backend are synthetic in that test. It does not qualify the combined
physical link or attach this worker to the original player's exit callbacks.
It also exercises incoming authenticated control, SDK dispatch, receipt TX and
uncertain-command deduplication. The native owner must finish its completion poll
before admitting the next TX; the client does not conceal a busy result by replay.

### Application status wire

`link.c`/`link.h` define the shared WRS1 status codec for the X1060 and Cardputer.
The exact 877-byte little-endian frame contains magic, a nonzero 64-bit session,
nonzero 32-bit sequence, valid/command/state/metadata masks, signed volume and
range, a 65-byte opaque track ID and three 256-byte UTF-8 text fields. Strings
must be NUL-terminated with zero padding; malformed UTF-8 and control characters
are rejected. This fits one 1470-byte ESP-NOW v2 payload. It does not provide
authentication: the receiver must require its explicitly paired encrypted peer,
the admitted session and increasing sequence before committing status. A stale
link must be shown as disconnected rather than retaining an apparent live state.

`player_status.c` maps the existing SDK snapshot to this format without touching
audio or hardware. Unavailable fields are cleared; position/duration are not
advertised by this first status profile. `tools/test_remote_link.c` covers the
codec and adapter, including truncation, invalid UTF-8, unchanged rejected
outputs and clearing fields after invalidation. This is not yet an RF link or
Cardputer display qualification. The codec is application-local, not a change
to the generic radio SDK protocol.

System capability and application policy are separate. Installing the compatible
driver/module makes ESP-NOW available to the system; it does not itself request
radio power or start the remote application. A shared system owner supplies the
SDK lifecycle, power and ordinary-Wi-Fi exclusion mechanisms. The remote business
requests/relinquishes its session through those mechanisms. Do not encode this
application's on/off policy inside the generic driver or infer powered state from
the presence of a module file. Module initialization's power effects still need
explicit qualification before deciding when the system may load it.

The user-facing remote switch belongs in Sony's original Settings, not only
inside this application. Turning it off must drain remote work, release wake and
driver ownership and power the radio down through the original power path. The
user may subsequently start ordinary Wi-Fi explicitly; remote-off is not a ban
on those manual Wi-Fi uses. ESP-NOW and ordinary Wi-Fi must never own the radio
simultaneously. A transition or failed teardown must not admit a second owner.
Do not automatically restore an AP connection when the requested outcome is off.

Prefer the lowest transmit power that passes measured remote-link reliability.
Existing RF initialization invokes the original `iwconfig eth0 txpower 15`;
that is an interface lead, not evidence of qualified lower settings or units.
Trace driver acceptance, range/readback and any firmware override before changing
it. Low transmit power does not prove low idle current: receive duty, wakeups,
power-save behavior and physical power-off need separate qualification. None of
these final Settings/power requirements is implemented by the read-only probe.

## Session renewal protocol

The finite supervisor still pins its configuration generation, and current peer
frontends still pair to one run session. Restartable Settings activation must
prepare a fresh host session and authenticate the receiver's session change;
reusing the old profile or resetting replay counters from a status packet is
not an implemented restart path.

`session_wire.c/.h` defines64-byte WRQ1 challenge and WRP1 response records using
the existing application HMAC key. Requests carry a caller-supplied fresh,
unpredictable16-byte challenge; responses echo it and identify a nonzero host
session. Version/reserved fields, length, magic and tag are checked. No pairing
key, generic ESP-NOW permission or player capability is exchanged.

The receiver explicitly starts a challenge and accepts a matching response only
from its paired address while that challenge is pending. Ordinary status frames
cannot rebind it. A new session clears old status/replay state; a same-session
reply keeps the last accepted sequence and status. Replayed or mismatched replies
preserve the receiver. Challenges must come from platform entropy, not a counter;
the receiver exposes explicit cancellation so delayed responses cannot survive a retry cycle.

The codec/receiver path passes host sanitizer and Sony-libc ARM tests, including
all64 one-byte reply corruptions, wrong source, reflected request, reply replay,
reused challenge and same-session replay-floor preservation. Core2/Cardputer
build inputs include the new source/header. The host responder is connected to the actual status sender. Core2/Cardputer
alpha.5 now schedule confirmation while paired and stale/no-status, using fresh
platform entropy at three-second intervals. Reusable launch-profile generation
remains unfinished; codec/build checks do not qualify physical reconnection.

The status sender accepts WRQ1 only from an authenticated paired RX event,
queues one64-byte reply and sends it through the same managed radio client. It
does not dispatch a player command or obtain additional player/radio grants.
At most one response is admitted per published status sequence, bounding repeat
traffic; command receipts keep send priority. The real partial-FIFO client/owner
stream test executes request/reply, correlated ACK/TX completion, duplicate
request suppression and unchanged player-command count under host sanitizers
and Sony-libc ARM. Full service/five-mode regression also remains applicable.

Both frontends accept WRP1 replies through their existing bounded RX queue. On
a verified session change they clear pending commands and command IDs, and Core2
also clears mode telemetry. Controls remain disabled until fresh status arrives.
Same-session confirmation retains command/status replay floors. Fresh status
cancels an outstanding challenge; retry cancels the previous challenge before
creating another. Unpaired devices send no confirmation traffic. Pairing keys
remain RAM-only and are never included in confirmation frames.

## Reusable private launch profiles

`build_remote_supervisor.py --reusable-sessions` keeps the reviewed service,
owner and template hashes and validates exposed user storage as before. After
that validation, the supervisor reads24 bytes from the character device
/dev/urandom and builds a RAM-only configuration with the authorized player
generation, a new application session and a new retirement cookie. Peer/key and
protocol-version fields are retained. Invalid/zero/reused template randomness or
read failure refuses launch; there is no clock-derived or old-session fallback.
The template is never rewritten. ESP-NOW encryption/PN-journal handling is not
reset by this application-session change. Default finite mode remains unchanged.

`run_profile.c` is shared C construction logic with host-sanitizer and Sony-libc
ARM tests for invalid templates, entropy failure, output preservation and in-place
operation. The reusable supervisor/actual service/player-host ARM guest chain
uses the guest RNG and verifies the user-volume template remains byte-identical.
This qualifies the userland path, not Sony-kernel entropy or radio power.

A trusted reusable-profile factory can call `wr_settings_backend_renew` only after
normal child reap, all process descriptors closed and the player service stopped.
It requires a strictly newer generation, refuses fork-copy ownership and retains
the UI request replay floor. It creates no process and writes no profile. The
Settings request path remains responsible for new admission and descriptor
offer. A two-cycle Settings/backend/process/supervisor/service/SDK ARM test checks
a new child, distinct application sessions, a second player command, matching
cleanup and unchanged template. Failed/reaping state cannot be reset this way.
The production Settings factory is still not automatically installed.

The profile reader now rechecks the opened template's regular-file/device/link/
size identity and hashes the exact80 bytes used for construction, after the
initial path/input qualification. This prevents the configuration read from
relying solely on an earlier hash check. New run values remain memory-only.
`test_remote_supervisor.py --settings-backend --reusable-sessions --rf-admission`
checks two complete generations and inactive-player refusal/cancellation through
the actual Settings backend and managed host in an isolated ARM guest. The
player-admission observation is fixture supplied; original native hardware
callbacks still have separate coverage.

## Original Settings factory composition

`settings_factory.c/.h` composes the real Settings backend, supervised process
and existing original-owner wireless authority. A trusted bounded qualification
callback remains mandatory. The factory prepares a fresh admissible SDK
generation, reserves the fixed remote-consumer lease, retains it through stop
and returns it only after clean supervisor/SDK retirement. If launch fails
without creating a process, it returns the unused logical reservation. Unknown
child/resource retirement latches failure and retains ownership. The callback
must not hash user files or wait on the UI thread.

The original GUI owner must bind the factory and tick it after SDK dispatch,
including during native exit. It is compiled in the paired RF/Settings profile
and is automatically bound only when a reviewed private profile is explicitly selected. `--settings-factory`
in the supervisor ARM test composes the actual factory/backend/process/service/
SDK/policy chain, with qualified readiness and RF behavior supplied by fixtures.
It checks three independent run sessions, normal off/reopen, Wi-Fi mode change,
another consumer's exclusive lease and permanent exit. An intervening local SDK
generation42 remains active while the old generation41 backend retires.

Generation-specific stop/retirement queries prevent an old cleanup callback
from stopping a newer SDK service. The factory asks the current SDK manager for
the next generation instead of assuming no other service has run. On native
exit, cleanup-only backend polling continues even though normal Settings request
polling stops; it never processes a new request.

Native preparation first closes SDK admission while retaining existing channels
for cooperative CLOSE/ack. Hard-draining those channels before the supervised
client can acknowledge close produces an uncertain result and is not equivalent
to successful retirement. The tested sequence preserves the explicit close
receipt, then drains the broker and verifies radio-owner retirement before
original coordination continues. No EOF or timeout is substituted for off proof.

## Opt-in automatic original-player binding

The host builder's `--remote-profile work/.../build.private.json` option requires
a reusable supervisor review with matching artifact and source hashes. It
compiles `remote_auto.c` and `remote_ready.c`, generates a private profile header
and calls the automatic binder after SDK dispatch in the qualified original
owner loop. Default builds omit automatic binding. Binding registers an OFF
backend and creates no process or RF owner. Idle OFF bypasses factory polling.

Launch admission reads the original APF active state, Root command/pending
tracker and latched environment busy field, then validates a distinct mounted
/contents directory and stable Root sample. The cached busy field is rejection
evidence, not physical USB-disconnect proof. The fixed read-only-root supervisor
is checked for regular-file/device/link/size identity; its exact artifact is
pinned by the reviewed root-image composition. Full user-input hashes are
checked by that supervisor before owner execution, not hashed on the GUI thread.
No additional synchronous APF query or background thread is introduced.

`--automatic-factory` in the ARM supervisor test executes the production automatic
binder with modeled native readiness, real supervised programs and the actual
SDK/policy chain. It checks default OFF, three run sessions, a foreign SDK
generation, mode change and permanent exit. The host-anchor profile test checks
that the qualified main-loop path invokes the auto tick; that tick body is a
fixture in the anchor test and is independently exercised by the ARM chain.
The19-case readiness replay executes actual singleton getters and C sampling
with filesystem/image/mode fixtures, including busy/transition rejection and
I/O-free fast lifecycle reads. These are not hardware ownership qualification.

A fixture supervisor/owner review is suitable only for these offline composition
checks. It is not an installable remote-control profile. Real owner/driver
qualification, native sleep/USB paths, root-image capacity and device acceptance
remain required before making a firmware candidate. No UPG is produced by this
builder, and its report remains `ready_to_flash=false`.

## Real RF owner qualification

`tools/build_remote_owner.py --window-seconds 180 --power-off-exit` builds the
actual Sony-libc RF owner, not the synthetic owner used by the process-chain
tests. Entry checks run without radio access and require refusal on a non-Sony
root. The report explicitly marks this as `finite-qualification` and
`ready_for_native_settings=false`. Its help text reports the selected duration.

This owner retains the existing reviewed driver/candidate inputs, session keys
and persistent packet-number journals on verified user storage. Do not reset or
replace those journals when preparing another session. Private command/response
pipes, a fresh retirement cookie, cooperative stop and the completion receipt
remain part of its lifetime. The power-off-exit profile compiles the controller
that retires the radio; its build is not evidence of physical power-off.

A persistent native Settings profile still needs an explicitly reviewed owner
lifetime and admission contract in place of the lab operator-confirmation
arguments. The finite owner is useful for the next bounded hardware test, but
must not silently become the final always-available remote. The synthetic
four-session process test and native sleep analysis do not qualify this real RF
owner's hardware, user-storage/USB timing or standby behavior. No player or MCU
is accessed by this builder.

`owner_admission.c` is the private READ-capability consumer for that migration.
A trusted launcher must supply the connected system-mode view and exact lease;
the helper cannot select a mode, acquire/release a lease or create authority.
No data is admitted until a matching ESP-NOW observation succeeds. Mode/lease
denial and transport loss revoke that instance, and a newer lease cannot revive
it. Forked copies cannot use the cached grant. Refresh scheduling and the
supervisor stop channel remain the caller's responsibility: cached permission
is not an instantaneous physical RF or global authority check.

Six host-sanitizer/Sony-libc ARM cases exercise the real mode channel, policy and
consumer, including mode revocation, mismatched lease, invalid mode, transport
loss, observation-only close and refusal to revive an old grant. Closing the
view leaves the policy lease active until its owner supplies retirement. This
component is not yet passed through the supervisor into the real RF owner.

The original-owner factory now provisions that view from the shared wireless
authority after acquiring its exact remote lease. Repeated pre-fork admission
reuses the same capability. The owner loop pumps one bounded channel step while
it exists; idle OFF creates no descriptor. A private generation-checked accessor
borrows the client FD for future launch forwarding, preserving outputs on stale
requests. Both ends are disposed after qualified process retirement, before the
logical lease is released; closing observation is never itself an off receipt.
The four-session ARM chain queries this real factory view before and after sleep
recovery and verifies disposal.

The opt-in supervisor profile `--forward-owner-mode-view` now carries the
borrowed connection and exact lease through the original launcher and supervisor
into the radio-model child. It requires a reviewed owner entry that supports
the extra arguments; legacy profiles retain their existing argument/FD list.
The original host builder enables forwarding from that supervisor's review.
Only one client may read the datagram/serial stream: parent diagnostics stop
reading once it is delegated. Failed starts and completed processes clear their
borrowed metadata without closing the factory-owned descriptor.

Four ARM sessions, including sleep/restart, pass end-to-end capability delivery
and the child's actual admission query before test data activity. The old
three-session path also passes. This is real descriptor/mode-protocol execution
with a radio model.

The real owner's opt-in `--mode-view-required` build now accepts the same
inherited entry. It requires `--power-off-exit`, queries the exact READ capability
before candidate/key/controller initialization, and refuses a denied or
mismatched lease. Three Sony-libc user-emulation entry checks cover matching,
wrong-lease and revoked replies: even the matching case then refuses the
non-Sony root before RF starts, returning its never-started receipt. Authority
replies are fixtures in these entry checks; they are not a hardware run.

The default remains finite qualification and retains the lab operator arguments.
The opt-in `--managed-session --mode-view-required --power-off-exit` build removes
the fixed60/180-second window and follows its parent stop/pipe lifetime. It
requires the mode capability; specifying a finite window with this profile is
rejected. This is a supervised analysis profile, not hardware qualification.

The mode-view owner now uses the single-loop periodic admission API: refresh
every200ms, revoke DATA permission after1000ms without a fresh observation, or
on clock regression, mode denial or channel failure. These are analysis timing
defaults, not physically calibrated values. Four additional sanitizer/Sony-libc
ARM cases exercise cadence, stalled authority, clock regression and channel loss
using a supplied clock. The actual owner compiles the same path with the
verified two-word stock clock bridge. It requests existing cooperative shutdown
on denial and keeps cleanup ownership until controller retirement; observation
close still cannot assert RF-off. No new thread/timer service is created.

Managed-view
supervisors now distinguish a verified never-started refusal: matching
cookie/clean record/EOF, service exit1 after player close and owner exit69
produce typed supervisor exit70. The parent recognizes that outcome only for
its mode-view profile, disposes resources and allows another generation; other
nonzero/uncertain exits retain fault handling. The real binary passes two such
refusal/retry cycles in an isolated Sony-libc ARM guest, without RF initialization
or player-control commands. The supervised-profile binary passes the same retry
chain. This is cancellation evidence, not sustained RF operation or readiness.
