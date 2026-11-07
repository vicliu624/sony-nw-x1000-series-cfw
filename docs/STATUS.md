Current SDK source is 0.2.0-alpha.9. All 16 installed SDK consumers have now been
rebuilt with successful current-version compiler receipts. Eleven executables
are byte-identical to their installed versions. Five changed packages and the
matching managed launcher were installed on user storage and hash-verified.
Glass Marble is outside this SDK-consumer set. The recorded alpha.8 consumer
tests and existing published archives retain their original scope; no new SDK
archive has been published by this maintenance.

# Current status and validation scope

The original-interface QEMU viewer runs the pinned Japanese Sony userspace
with framebuffer and touch adapters. Home, Settings, Music Settings and return
navigation have been observed in an isolated ARM926 guest. It uses a generic
kernel, an empty media-component registry and explicit peripheral models; it
does not qualify physical RF/audio, Wi-Fi retention, sleep/USB or recovery.
See [the QEMU guide](QEMU.md) for local preparation, controls and limitations.

Physical clarification: after selecting ESP-NOW, the screen remains the
three-choice Wireless Mode list, but its selected label temporarily reads On.
Reopening shows ESP-NOW. This is a refresh-path symptom, distinct from the
Remote entry trapping Settings. Current offline callback and original-FSM
replays pass in work/wireless-mode-callback-current.log and
work/wireless-mode-refresh-current.log. They verify the three-choice
reinitialization path, not physical rendering or RF switching. No new device
test or installation follows from these checks.

The page bridge now enforces mandatory view acquisition/release ports. OPEN
fails without them; rejected release stays interactive, and an unrestored view
refuses reopening. A dedicated fixture runs actual page/bridge/backend/process
logic and checks delayed completion, commit preservation, stop and generation
refusal. Evidence: work/remote-page-view-lifecycle-chain.log. The current generic
fixture had no page-port code, so it was preserved and page tests now select
tools/fixtures/native_page_backend_chain.c; old generic-file hashes are historical,
not current evidence. Generic mode-switch also passes separately. Current
600/920-byte analysis composition and registration/guard checks are recorded at
work/remote-native-page-composition/1793851099755707383/report.json,
work/remote-page-view-port-registration.log and work/remote-page-view-port-guard.log.
Native restoration completion remains a fixture in the process chain; no
production adapter/observer/Wi-Fi guard or UPG/device action was completed.

The optional native-page host-dispatch guard is implemented and tested through
actual composed page/PID shim/host dispatch/image guards. It requires allowed
caller, ready non-reentrant GUI owner and matching code/registration data before
the private adapter; the default adapter is unavailable. Span mutations, foreign
owner, unsupported loader, unbound source, legacy toggle refusal and ordinary
PID/errno checks pass in work/remote-page-guard-dispatch.log. Backend and loader/
thread identity are fixtures. Guarded analysis composition:
work/remote-native-page-composition/1793849879227107836/report.json.
Ordinary firmware profiles do not enable this branch. Real adapter/view observer
and Wi-Fi entry guard remain to be paired; no UPG or device action occurred.

A separate native-page analysis ELF now composes the actual Remote entry,
callback tables and194-state registration in checked mapped padding, preserving
initial group193 in both original registration paths. Root/Pcs capacity stays
156; Remote uses borrowed control29. Code/metadata are576/920 bytes, ELF growth0.
Both native registrations plus actual row lookup/category and entry/cancel/ready
flow pass in work/remote-native-page-registration-check.log. Unpaired requests
stay interactive, and stock selections delegate unchanged. Artifact/review:
work/remote-native-page-composition/1793848504808747239/report.json. Guarded DSO
bridge/view observer/Wi-Fi entry guard are not paired and no UPG was generated.

View restore observes the original menu state as well as Root state: acquire
requires interactive Settings, release originates from Remote, and completion
requires interactive Settings/control97 and settled layers before restoring.
The actual menu ready-event transition plus20 bounded observe/restore cycles
pass in work/native-choice-view-menu-ready.log; layer/scene sequencing remains
supplied. Production observer, Wi-Fi-entry guard and state-table composition
are not installed. Both native AppMenu registration paths have been identified;
future extension must preserve startup group193 in both. No package/device
operation was performed.

An unpromoted existing-choice view helper is implemented with owner/epoch and
explicit completion gates. It borrows only count/SID, refuses active/queued or
changed native state, and restores without replacing/freeing the Sony object.
Actual active-layer lookup and parameter helpers pass20 exact restore cycles
and negative cases in work/native-choice-view.log. Layer/draw state and close
acknowledgements are fixtures. Ready producer2d21c and normal page request55544
have been located, but their asynchronous ordering is not qualified or wired
to the helper. No production profile/UPG/device action was created.

Remote resource13901 is prepared locally (228 bytes, no new STX entries) and
passes the original filename/load/parser/text path for title/On/Off in11
languages (33 checks). Evidence: work/remote-choice-resource-check.log. Original
navigation inspection corrected a prototype mistake:73608 is a playback
shortcut, not parent-pop. Cancel/apply-success now post Settings control97 and
wait for its ready event; playback shortcut and HOME are separate callbacks.
Actual FSM replay passes in work/remote-native-page-return.log. The combined
backend chain is recorded in work/remote-native-page-return-chain.log. UI
category/service leaves remain modeled. Production registration/view reuse and
close/restore timing remain pending; no UPG or device action occurred.

Existing-view reconfiguration is being checked as an alternative to unsafe
Root-array expansion. Actual Pcs control29 allocation and original parameter/
provider setters support count3->2->3 with exact view-byte restoration and no
modeled Root-byte changes. The original live SID getter separately observes
13900->13901->13900, preserving provider index2. Evidence:
work/native-choice-reconfigure.log. Provider-context pointers, inactive Root
state and resource availability are fixtures; no active renderer or restore
timing is qualified and no production sharing hook is installed.

The three-mode confirm source now re-enters its custom initializer only when
the stock confirm returns its normal terminal5a01; asynchronous/error results
are preserved. Actual C confirm + original stock confirm/FSM + actual custom
initializer + original stock initializer replay pass for rows0/1/2, ending with
the committed row queued and group154/substate2 after a supplied ready event.
Evidence: work/wireless-mode-refresh-callback.log and
work/wireless-mode-refresh-fsm.log. Binary preferences are supplied already
matching, and GUI/NVP/mode authority are fixtures; RF transitions and physical
rendering are not qualified. No new package was generated.

Native Remote page registration needs a revised view strategy. Pcs pool capacity
176 is not Root view-array capacity: Root's156 slots end at+0x2ff8, which original
code uses as another object. Do not install experimental control156 or simply
increase the Root loop/count. The C callbacks/bridge tests remain useful logic
tests, but their supplied control does not qualify production storage. See the
knowledge guide and work/remote-ui-views-inspect.log. Existing tested kit is
unchanged; no device operations were performed.

The private native page bridge now connects actual C page callbacks with the
actual managed queue/backend/process chain under the ARM guest. Open/preview/
cancel leave no request/process; confirm On commits, and closing the page does
not undo the commit. Backend renewal invalidates the old page generation;
foreign-owner operations, invalid rows and apply-before-open are refused.
Evidence: work/remote-native-page-full-chain.log from
tools/test_remote_supervisor.py --settings-backend --reusable-sessions
--native-page-chain. Original UI/category leaves and RF/media remain modeled.
Production page registration/resources and guarded DSO entry are still pending.
No package or physical operation was performed for this bridge work.

Native Remote page callbacks are implemented as an unpromoted C prototype in
runtime/apps/wireless-remote/native_page.c. Seven scenarios pass through original
FSM registration/dispatch and a cloned stock choice-event map: open refusal,
cancel, back, HOME, apply On/Off and apply refusal. Preview never calls apply;
the earlier prototype posted Pcs156 and waited for a supplied ready event; apply refusal
retains group194/substate2. Evidence: work/remote-native-page.log. GUI/resources,
category leaves and request bridge remained modeled. That control156 prototype was not
installed by production startup or connected to a real owner backend. No UPG
or device operation occurred; the old native entry still awaits replacement.

Remote backend query/explicit-target APIs are implemented and pass the actual
managed queue/backend/process chain under the ARM guest. One thousand queries
leave the backend OFF with no process/request; explicit On/Off, duplicate and
conflicting queued targets, same-target no-op and foreign-owner output preservation
are checked. The ordinary mode-switch retirement chain also passes. Evidence:
work/remote-explicit-settings.log and work/remote-explicit-mode-switch.log.
Query reports request intent and phase, not RF readiness. These interfaces are
not yet wired to a completed original Settings page. The legacy toggle entry
remains pending replacement; no package or physical operation was performed.

The Remote Settings trap has a reproduced local FSM cause and source fix:
0201 puts Settings into its noninteractive substate1, while0202 preserves
interactive substate2. Original registration/event routing plus the rebuilt
candidate's actual Remote callback pass in
work/remote-settings-transition-fixed.log; the full host compiles under
work/player-settings-substate-fix-20261105-1/build.json. This is not the completed
On/Off UI: the legacy entry still enqueues an action, and proper page creation,
query/apply/cancel and visible state are outstanding. Do not package this narrow
fix as the final remote feature. Existing physically tested kit remains intact.

Current candidate is PARTIAL FAILURE for native remote Settings despite its
accepted Homebrew flow. The user confirms Wireless Mode labels are correct,
but tapping Wireless Remote shows no On/Off page and traps navigation in
Settings while scrolling still works, regardless of ESP-NOW selection. Selecting
ESP-NOW also refreshes with On selected; reopening shows ESP-NOW selected.
Keep these two UI defects separate from RF reception and the earlier hard freeze.
No remote control acceptance is claimed. Core2 on COM28 runsalpha.7; its existing
matching pairing was loaded into RAM only, with player_session=0. No MCU flash,
X1060 write or PC-triggered radio-mode change occurred in this test.

Source inspection confirms native_settings.c only enqueues a request then
returns0x0201; it does not create an On/Off page. Original0x950f0 encodes
state/category in its return and posts/initializes a page for real selections;
its unknown-row fallback is0x0202, not the injected constant. This is an
incomplete native UI implementation, not a user sequencing error. The mode
confirm bridge temporarily maps row2 to binary1 for the stock callback; trace
the resulting native navigation before changing its selection redraw. Original
function disassembly is in work/settings-exit-inspect.log. No repair package
has been generated for these newly reported defects.

The user reports installing the0b5ede45... manual-test candidate and seeing the
Homebrew app list normally on the NW-X1060. This gives physical acceptance for
the reported entry boundary and supersedes the entry-unqualified statement
below. Evidence: work/managed-firmware-review/1793817320395206222/physical-acceptance.json.
The user also reports Graphics runs normally and one HOME press returns to
the stock main menu. Entry, this app execution and one-key return therefore
have physical acceptance. It is user-reported acceptance, not installed-file
readback or a causal proof that the pending-token fix alone resolved the
previous freeze. Two additional stock menu -> Homebrew -> Graphics -> one HOME
return cycles also pass by user report, without RESET in the requested test.
Sleep/wake, USB and RF remain unqualified for this candidate.

Current manual-test kit is
work/startup-candidate-materials/1793817713327352464/01_PC_UPDATE/FWUpdater.exe.
Its UPG is0b5ede45ef0703bfdcff75a9fc1531c99f697c5e4d904a782294dd64b9516a49,
46,809,144 bytes, generated from current OpenSSL-container source and freshly
reviewed host/layout/Settings/cold/exit receipts. Independent Rockbox extraction,
three identical repacks, exact declared root changes and33 copied kit files
pass. Evidence: work/managed-firmware-review/1793817320395206222/review.json,
startup-delta.json beside it and work/homebrew-current-materials-check.json.
System regular-file growth is296,057 bytes; this is not measured device free
space. The candidate corrects idle native preparation and wireless choice text,
restores stock resource permissions and retains one player. Sony updater,
installer, kernel and initrd are unchanged. No external App reinstall is
required. This supersedes the earlier withheld kit status, not the captured
failure evidence. No device action was performed. Physical startup, direct
Homebrew entry, app execution/return, sleep/USB/RF remain unqualified for this
candidate. First manual check is main menu -> direct Homebrew with remote OFF,
before visiting new Settings pages. Do not report the physical freeze fixed.

PC container encoding/decoding now uses OpenSSL3 through scripts/upg_crypto.py,
with explicit same-backend reverse checks and no automatic retry/fallback.
The captured failed ciphertext independently decrypts under OpenSSL to the same
bad root bytes; encrypting its expected plaintext produces different ciphertext.
Further mixed-backend tests also reject verification and one final bulk decode,
so both previous directions are isolated rather than attributing every failure
to encryption alone. Internal cause in the previous execution path remains
unproven; this is not a general claim about PyCryptodome on other systems.
Six full current-component pack/unpack runs now produce63762fc4... identically
(work/container-openssl-both.log). DES known-answer, invalid inputs, missing
backend/no-retry, wrong roundtrip rejection and exact original Sony UPG rebuild
pass in work/upg-crypto-check/report.json. Rockbox remains independent of these
same-backend checks. Rebuild current-source receipts before delivery; existing
candidate receipts pin the superseded container implementation. No kit or
device action occurred. Physical Homebrew entry is still unproven.

Package delivery is withheld after a reproduced PC container failure. The
preserved-metadata candidate63762fc4... at
work/managed-firmware-review/1793809016620354871 passes its independent Rockbox
extraction, but repeated pack/decrypt can corrupt the root component. Captured
evidence in work/container-repeat-failure/1793809318650835662 contains both
containers and expected/decoded components:34 root bytes differ and the decoded
copy fails gzip CRC, while expected/Rockbox copies match and pass CRC. Component
script/kernel/initrd remain equal. This does not implicate device hardware.
Staged checks added to release_firmware.pack isolate a subsequent failure to
the component DES encrypt/decrypt roundtrip (run2 after two identical successes),
not padding or body assembly. Evidence: work/container-stage-isolation.log.
Whether encryption or decryption/backend execution is at fault remains unknown.
Do not retry until a convenient pass and deliver it. No updater kit was made.

Resource-overlay generation now preserves the input resource permissions.
The third-choice SWD previously changed0664 to0644 unnecessarily. Current
layout1793808880914675624 preserves its original metadata. The local candidate
review tool compares exact declared paths and verifies loaded wrapper segments;
symbol-only wrapper changes are not execution changes. Latest pack-source
checks invalidate old reports that pinned release_firmware.py; retain them as
historical evidence rather than relabeling them as current passes.

The idle/native-token correction now also passes the real managed-service
policy under host sanitizers and ARM/Sony LinuxThreads, using an explicitly
busy native-view fixture. It preserves closed admission, delegates repeated
empty exits and refuses subsequent RF-retirement failure. Production owned
worker/dependency drain and exact-DSO cold/repeated-exit checks pass separately.
Evidence logs: work/idle-sdk-native-policy.log, work/idle-sdk-owned-drain.log,
work/idle-sdk-exact-dso.log. Their fixture boundaries remain in the reports.

A local review-only UPG5d994ca6... is retained at
work/managed-firmware-review/1793808305022343156. It is46,809,136 bytes; regular
system-file growth over stock is296,057 bytes. Its independent Rockbox extraction
matches all four components and the complete gzip/inventory checks pass. The
installer/kernel/initrd are unchanged. This includes the previously described
wireless choice resource correction. The first packing attempt rejected its
in-memory component roundtrip; its failed bytes were not retained and the
cause remains unexplained. A diagnostic-only builder change now retains future
rejected bytes and per-component hashes. Do not describe that initial failure
as resolved by a successful rerun. No updater kit was prepared and no device
action occurred. Physical Homebrew success is still unproven.

A concrete resource-free prepare defect is now reproduced and corrected in
source. A pre-existing Sony pending token previously caused the new bridge to
consume command3 even with no SDK resources and a retired radio. ARM regression
replay now reaches original prepare immediately or after radio retirement;
resource reappearance refuses continuation. Owned-resource and non-RF dispatch
tests still pass. The full composed host builds successfully with the same
162,364-byte library size. Evidence: work/idle-sdk-native-token-before.log,
work/idle-sdk-native-token-after.log, work/idle-sdk-native-token-nonrf.log and
work/player-idle-native-token-fix-20261104-1/build.json. This does not establish
the physical freeze's cause or cure; no UPG or device action was performed.

Regression comparison now takes priority over adding device probes. Retained
candidate8/9/10 roots were compared against physically failed999846fd. AppList
is identical; candidate9/10 mode1 and the checked native name-query/switch-call
words match. The current wrapper/preload integration instead adds five native
prepare interceptions plus GUI-router, worker-dispatch, activation and main-loop
boundaries. The PC-only comparison tool records hashes and exact words in
work/homebrew-working-current-comparison/candidate10-boundaries.json. External
launcher changes remain a separate variable. This is an inventory, not a
reproduction or a Homebrew fix. No new package or device action was performed.

Local observer/storage pairing now passes through the exact248-byte ARM
capsules and opt-in six-argument PID shim. It validates caller/tag/image and
entry-SP+8 frame identity, copies values immediately, and records stages1..5
with CRCs under Sony libc/LinuxThreads. Denied ownership leaves the file empty
and preserves the fixture native result. The actual production host_hook.c
dispatcher, original continuations and physical ownership are not integrated;
fixture callbacks explicitly supply those boundaries. Ordinary four/five-arg
PID text/relocations remain byte-identical to the preserved pre-pairing source,
and ordinary capture tests pass. No ordinary profile links the observer/store.
Evidence: work/parent-observer-pair/1793804112969827028/report.json,
work/parent-observer-default-pid-check.json and work/parent-pid-default-compat.json.
No UPG, device code execution or device file write occurred.

The separate parent-trace fixed-file backend is now implemented and tested,
but is not paired with the original-player dispatcher or a real ownership
predicate. It writes only fixed64-byte slots in an existing2048-byte nonce
file on validated user storage, at most one attempt per16 stages, preserving
errno and closing its record FD before return. A mandatory caller-supplied
ownership check runs twice. ARM/Sony-libc tests cover every slot and CRC,
unchanged header/tail/size, absent/invalid/replayed files, denied/revoked owner,
bad mounts, contention, short writes and fsync failure. The PC reader accepts
valid records while identifying partial CRC failures; empty remains ambiguous.
Current evidence: work/parent-trace-store/1793802927959008354/report.json.
RAM volume/mount text and ownership are fixtures; real VFAT/USB, observer
dispatch pairing and physical capture are not qualified. No UPG or device
operation was performed, and no ordinary firmware profile links this backend.

Parent-process entry observation is now prepared locally as passive capsules,
not a device candidate. The five stages precede/follow Home entry, native name
query and native APF switch, avoiding the assumption that an external process
has already started.248 bytes occupy a verified empty RX slot with four
declared branch edits and no ELF growth.21 ARM differential cases preserve
registers, stack and condition flags; original name-query/manager parsing also
passes with stage sequence1..5 and the unchanged mode1 packet.
Evidence: work/parent-entry-trace/1793801224405780767/report.json,
work/parent-entry-trace-abi-check.json and work/parent-entry-full-query-check.json.
There is a separately tested fixed-file backend, but no paired observer
dispatcher/real storage-ownership guard, no UPG and no device deployment.
This is not a Homebrew fix or an executable diagnostic ready for the user.

Latest physical verdict for999846fd... is PARTIAL FAILURE. Boot, twelve Settings
items and English/local controls pass by user report; Homebrew freezes on the
stock main menu with all controls unresponsive. A RESET/direct-Homebrew control
test without visiting the wireless page also freezes, so visiting that page is
not a necessary trigger. Wireless Remote remains untested. The third choice
on the original On/Off page displays000/@en instead of its expected label.
Do not offer this candidate again as a fixed Homebrew package.

The third-choice label defect is now traced to the actual Pcs control0x1d:
resource13900 selects sid-139-00, while the earlier composer put tid12 only
on parent sid-100-00. The displayed page therefore had no local tid2. The
corrected composer updates sid139 title/tid0 and adds tid2, retaining OFF at
tid1; parent sid100 keeps only its navigation title change. Static count,
capacity and final count fields21/22/32 also change2->3 for control0x1d, with
all other Pcs descriptors preserved. Tests connect original Pcs records to
the actual output SWD and11 STX files and resolve Wi-Fi/OFF/ESP-NOW correctly.
Both combined and standalone display builders use that shared composition.
This fixes a local resource/layout defect; physical display and RF behavior
remain unverified. Old source snapshots are in ignored .tmp.
Current local source build: work/player-wireless-label-fix-20261104-1/build.json;
resource proof: wireless-label-resource-check.json beside it. No new UPG or
device operation was made for this correction. Homebrew's physical cause is
still unresolved; prior lifecycle repairs did not achieve physical entry.

The user manually installed the999846fd... candidate from the supplied exact
updater path and reports update completion followed by the stock main menu.
This qualifies the reported startup boundary only. Settings visibility,
language switching, Homebrew entry, application run/return, sleep/USB and RF
are not yet verified. Installed root hashes were not read back. Evidence:
work/managed-firmware-review/1793797140142263096/physical-stage1.json.
The user also confirms twelve Settings items with both new entries visible.
The data-only Pcs count correction therefore has physical menu-visibility
acceptance. The user subsequently confirms switching to English changes the
stock menus and leaves touch/keys operating normally. Homebrew entry/run/return,
Chinese switching, sleep/wake, USB handoff and RF remain pending.

Current local review candidate is now prepared, not installed or qualified:
work/managed-firmware-review/1793797140142263096/review.json, UPG SHA-256
999846fdc45810edba004059a41bfb267038e3e343970c89695c727302e54ca2,
46809128 bytes. Manual updater materials are under
work/startup-candidate-materials/1793797432283077705. Its FIRST_TEST_REVIEW.md
in the review directory describes exact changes, capacity limits and runtime
uncertainty. Independent Rockbox extraction matches all four components;
original script/kernel/initrd, complete root gzip CRC, normalized tar inventory
and updater copies pass. This is review-only material, not a proven physical
fix. No device program, file installation or flashing occurred during creation.
The last physical capture failed and has already been fully restored.

Exit regression now executes the original readiness getter instead of forcing
success. With Root+0x50 zero, native command3 returns before module preparation;
an explicit later-ready fixture then permits the original exit. A second case
executes original pending-token registration/removal for two supplied module
tokens: unknown completion preserves both, first completion does not finalize,
last completion reaches10ee4. Its body remains intercepted. Eleven wireless
dispatch cases pass; no real module readiness, termination or hardware is
qualified. Evidence: work/native-exit-real-readiness-check.json and
work/native-exit-real-pending-check.json.

The current local layout/capacity review retains one player body and22 changed
paths, with296060 regular-file bytes above original (192 bytes above the last
failed managed candidate inventory). See work/player-system-layout/
1793796646206139703/report.json and work/managed-root-capacity/
1793796672291581658/review.json. This is file-inventory growth, not measured
partition margin or allocated ext2 usage. No UPG or updater kit was generated.

The exact library's ordinary getpid now matches original Sony libc in a real
LinuxThreads worker, after moving the threaded test out of PID1 into the normal
child supervisor. No PID behavior fix was needed. An expanded current Home
test executes preflight on the installed ELF header and original APF name
query/manager parser against AppList extracted from the failed de4a2330... UPG;
it resolves0x30001 and constructs the mode1 request. The native bounded string
copy runs directly after correcting a test-model return-value assumption.
Full gzip validation precedes tar seeking. Evidence:
work/exit-lifecycle-thread-pid-check.json and work/current-home-full-name-check.json.
Active client state, file IO, locks/transport and switch acceptance remain
fixtures; actual process retirement, GUI and physical failure remain unverified.
No new firmware or device change was made.

Latest local build is work/player-exit-lifecycle-fix-20261104-1/build.json.
It additionally prevents automatic wireless bootstrap while the managed player
is exiting or has no bound owner. The refusal does not latch a permanent boot
failure, allowing later ordinary owner binding. The pre-fix lifecycle fixture
observed bootstrap during exit; the corrected real auto/policy code passes on
host sanitizers and ARM/Sony libc. Existing cross-process mode-channel tests
pass with an explicit active-owner fixture. Exact DSO cold/empty-repeat and
468 original Settings construction/index cases pass for this build.
Evidence: work/wireless-auto-exit-before.log, after.json, channel-check.json,
work/exit-lifecycle-cold-check.json and settings-check.json. Original lifecycle/
OFF observation inputs are modeled; physical startup, Homebrew and sleep/USB
remain unqualified. No new UPG or device operation occurred.

The bound-radio/verified-OFF empty-repeat case is now reproduced and corrected
as well. The real prepare bridge plus managed service initially reports
BOUND_NATIVE_REPEAT_HELD after first fallback; the correction reuses the
retired epoch, revalidates code/owner/root, resource emptiness and wireless OFF,
and preserves admission CLOSED. A subsequent refused RF recheck suppresses
fallback. Host sanitizers and ARM/Sony-libc tests pass with explicitly modeled
Root/image and radio responses; no worker or RF hardware runs in that case.
Current local build: work/player-bound-repeat-fix-20261104-1/build.json.
Evidence: work/native-bound-repeat-before.log, after.log, prepare-check.json,
and work/bound-repeat-fix-cold-check.json. The actual-DSO cold/unbound-repeat
checks remain passing. No physical cause, startup success or Homebrew return
is claimed; no UPG or device action was performed.

The latest local source also fixes a separate resource-free native-exit repeat
defect. After the first delegated command3, the ordinary admission-gated idle
query returned CLOSED and the second command was consumed. The real DSO
negative test reports NATIVE_EMPTY_REPEAT_HELD. A private native-continuation
resource query now preserves stock fallback while keeping new admission
closed; corrected exact-DSO tests report NATIVE_EMPTY_REPEAT_DELEGATED, with
ordinary idle/admission still CLOSED. Managed-service empty/live tests and
nine wireless prepare cases pass, including refusal with owned resources.
Current local build: work/player-native-empty-repeat-fix-20261104-1/build.json.
Evidence: work/native-empty-repeat-before.json and after.json plus the owned
prepare/service logs. Direct repeated calls and provider initialization are
fixtures; physical repeat/order and the Homebrew freeze are not reproduced.
No UPG, installation or device action was performed.

A new local defect has been reproduced and corrected: unbound command3 marked
the managed service's native_exit_seen before SDK binding, poisoning later
admission even though no SDK session existed. The exact pre-fix DSO prints
COLD_EXIT_FLAG SET and fails the new --cold-exit-contract test; the corrected
DSO keeps it clear and passes cold commands3/6/7 with errno preservation.
The physical boot's command order is still unobserved, so this is not yet a
proven cause of the Homebrew freeze. Current local build is
work/player-cold-exit-fix-20261104-1/build.json (library SHA-256909cfcec...).
Old artifacts are retained, using the builder's new explicit fresh review
directory option. No UPG or device change was made. Exact cold DSO, original
Settings widget/index replay (468 constructions), empty native exit and owned
managed-session drain checks pass. Whole startup, Homebrew and physical return
remain unqualified; do not issue a claimed fixed package on these checks alone.
Current Home switch-mode replay now executes the actual selector/default
branch and argument adapter in that payload, then original APF packet builder.
It confirms mode1 quit/relaunch at wire word6. The older check_home_parent.py
integrated path asserts mode0/deactivate-resume and must not be cited as
qualification of this current path. Mode0/mode1 client controls pass alongside
the actual adapter case; manager/native exit completion remain unverified.
Evidence is work/current-home-switch-mode-check.json and timestamped reports
under work/current-home-switch-mode/. No device action or UPG was made.
The cold-exit regression now additionally executes the real managed bind/idle
API with an explicitly initialized player fixture. The pinned historical DSO
sets the exit flag and refuses the subsequent idle query; the corrected DSO
keeps the flag clear and reports idle. This confirms an API-level consequence
of the defect, while original provider binding and physical event order remain
unverified. Logs: work/cold-exit-contract-bound-before.json (negative control)
and work/cold-exit-contract-bound-after.json (current test).

The Japanese NW-X1060 reached the original main menu with candidate
`d1d2b6c...` in the user's 2026-11-03 test. Follow-up on 2026-11-04 reports only
ten Settings entries with no Language option, and a freeze at the original main
menu when Homebrew is selected, with hardware keys unresponsive. The user
confirms the provided updater directory. This qualifies startup only; it does
not qualify Homebrew entry, app return, language visibility, sleep/USB or RF.
Installed payload hashes have not been read back from the device.
The latest de4a2330... follow-up also fails physically: the user reports the
same ten Settings items and pre-Homebrew freeze after the updater explicitly
completed and the device automatically restarted. Treat this as a failed
candidate, not an update-skipped explanation. The mocked control/owner states
in offline checks have not reproduced this real path. Do not generate another
candidate from those checks alone; actual runtime evidence is now required.
Read-only USB follow-up identifies the expected player/user volume and the
expected external launcher hash (0be95032...). No UPG remains in the user-volume
root and no existing launcher/diagnostic output is available. This does not
read back the installed system or establish the live control/exit path.
That initial read-only inspection executed no device program and wrote no device
file. The separately authorized boundary tests below have since completed.

Current source analysis has replaced the ineffective media-list adapter with a
data-only Pcs descriptor edit. The original Home Settings request produces
control0x61; its resource5000 descriptor still initialized two count fields to10
in the failed de4a2330... image. Original Pcs manager/pool initialization,
allocation and widget record construction now reproduce that ten-item object
and a twelve-item corrected object. All other155 descriptors and capacity49
remain unchanged. This covers468 native construction cases, not complete pixel
rendering or physical acceptance. The former176-byte adapter/four media-call
redirections are removed; failed source snapshots remain in ignored .tmp.
No new UPG has been generated for this data-only revision. Homebrew's actual
freeze path is still unresolved. The first external-launcher boundary test was
canceled and restored; the later authorized tests have completed.
The user later explicitly authorized one temporary external capture diagnostic.
It was installed/readback-verified, tested once, and completely restored.
Homebrew stayed frozen, connecting USB did not expose the user disk, and RESET
was required to regain USB. The4096-byte trace is exactly the original seed
(3ebbd00e...): no entry, exec error or completion record. This fails physical
auto-return; it does not prove the process never started, because storage
preflight/refusal or a blocking operation before its first marker remain
possible. Original launcher0be95032... and absence of all temporary paths were
verified after restoration. Evidence: work/physical-validation/
launcher-capture-20261104T112938648Z/physical-result.json. The one-time execution
authorization is used; do not repeat it or generate another claimed fix from
the generic guest passes alone. No firmware/system-partition change occurred.
The expanded original-index replay confirms corrected visible items11/12 are
Language0xf80000 and Remote0xfd0000, with the first ten unchanged. Original
list-state setter0x74668 and index getter0x74634 execute; selection category2
is explicitly supplied, so page activation/touch/scroll remain unqualified.
Current receipt: work/settings-descriptor-check/1793781641956734271/report.json.
The later authorized missing-file test produced the native unavailable prompt;
the exact launcher was restored. A separate one-shot C entry probe was then
tested and also fully removed/restored. Latest user clarification is temporary
unresponsiveness followed by a usable original menu, without confirmed reboot.
Its128-byte record remained identical to the seed, so process entry is not
proven; mount/file refusal and pre-entry failure remain possible. Do not treat
that result as a successful normal application switch. Original launcher hash
0be95032... and cleanup were verified. A transient Windows Code47 safe-removal
state cleared after full unplug/replug; no driver reset or firmware update was
used. All static prepare-guard spans match the failed package; live values and
handoff progress still require actual runtime observation.

The exact 14,480-byte entry probe now also executes through the unchanged Sony
appproxy in a generic ARM926 system guest. Registration, activation, marker
readback, proxy exit status0 and endpoint cleanup pass. The mount listing and
user file are RAM fixtures; the APF manager is a C protocol peer, not SpiderApp
or the physical manager. This narrows generic proxy/ELF execution concerns but
does not explain the unchanged physical trace or qualify Homebrew entry.
Evidence: work/entry-probe-stock-proxy-20261104-2/system-probe.json. The first
attempt failed during guest fixture setup and is retained as failed evidence.
Follow-up cases now establish the ambiguity: guest storage-check refusal and
an absent child executable both leave the trace unchanged while the original
proxy completes registration/activation, returns0 and cleans endpoints. These
are negative controls, not successful app sessions. Current-source receipts
are under work/entry-probe-stock-proxy-20261104-3,
work/entry-probe-stock-proxy-refusal-20261104-2 and
work/entry-probe-stock-proxy-missing-20261104-1. Future physical instrumentation
must distinguish the parent switch boundary from child entry and storage
validation; proxy completion alone is insufficient.

The proxy system runner now accepts an explicit launcher build receipt rather
than silently using the older composition launcher. The exact installed
50,640-byte launcher (SHA-256 0be95032...) passes both list/Graphics/list/exit
and manager-stop-during-Graphics scenarios through the original appproxy.
Evidence: work/installed-launcher-stock-proxy-20261104-1 and
work/installed-launcher-stock-proxy-stop-20261104-1/system-probe.json. Real
Sony libc/process execution is used; display/touch are interposed C fixtures,
the catalog contains one fixture app, and the real SpiderApp transition,
device inputs, mounted user filesystem and RF ownership are not exercised.
These passes do not supersede the physical Homebrew failure. They establish
that this exact external ELF can execute and complete its UI/process lifecycle
under the stated conditions; further physical observation must cover the
original player-to-manager boundary and real device/storage calls.
An explicit stderr-only launcher entry-trace profile now marks twelve startup
and return boundaries. Its original-proxy fixture run validates their exact
order (work/launcher-entry-trace-proxy-20261104-1/system-probe.json). The
diagnostic ELF is50,672 bytes; disabling tracing rebuilds the installed
50,640-byte 0be95032... ELF exactly. This is local observability infrastructure,
not a physical fix: stderr capture on the player remains unimplemented and no
diagnostic deployment or firmware package was made.
The next local diagnostic is a separate12,104-byte C supervisor, reviewed under
work/launcher-capture/1793776873486635033/REVIEW.md. It captures the traced
launcher stderr and child exec/wait outcome into a preallocated nonce-matched
4096-byte user file, with a4000-byte payload ceiling and finite polling budget.
Exact ARM/stock-libc guest tests pass normal child exit, missing exec,
closed-stderr hang, excess output, missing mount, child/log symlink and nonce
rejection, and one-shot seed reuse refusal. A RAM volume and synthetic mount
listing remain fixtures. No device deployment has occurred; execution requires
separate approval. Parent-side blocks and storage-preflight refusal remain
unobservable from that file alone. No new UPG is generated.
The combined exact supervisor/traced-launcher path now also runs through the
unchanged original appproxy and completes list/Graphics/list/exit, with all
twelve stage markers and child status0 read back from the4096-byte file.
The guest uses an actual separate RAM mount for /contents; an explicit C
stdio fixture substitutes its mount-table line with the expected VFAT identity.
Thus filesystem separation, stock-stat64 decoding, pipes, process control and
bounded capture execute, but neither real VFAT nor the physical APF transition
is qualified. The first combined runner failed its assertion because it treated
post-exit console replay as live child stderr; that failed receipt is retained.
Current evidence is work/launcher-capture-stock-proxy-20261104-3/system-probe.json.
The separate device-execution request was declined in favor of offline work;
no temporary files have been installed on the player.
Temporary capture installation/restoration now has a default-preview PowerShell
tool with pinned identity and hashes, retained original, staging and trace
preservation. Offline fixture tests pass preview non-mutation, install/readback,
duplicate-install refusal, exact restoration/cleanup and rejection of an
unknown original. Evidence: work/launcher-capture-installer-test/
20261104T074922662Z/report.json. The fixture replaces USB evidence in a private
copy; no production device action has run. The user has chosen not to run this
physical diagnostic at present.

The most recent physically tested (failed) follow-up candidate is
work/managed-firmware-review/1793753766311600338/DIAGNOSTIC-REVIEW-ONLY.UPG,
46,808,968 bytes, SHA-256
`de4a233023e4855cf4d94cd5a048f8c3aefaa40f86928724c718de4e32a3f1b1`.
Complete manual-test materials are under
work/startup-candidate-materials/1793753885679084559. All33 copied files were
read back and hash-verified. No automatic flashing or device write occurred;
this candidate failed the physical follow-up and is not a public release.

That failed follow-up contained two experimental changes. Native command3 delegates when the
SDK is verified idle and has no wireless authority, rather than consuming exit
after wireless prepare_stop refuses. The Settings controls61/62 now obtain the
count from the native list2 descriptor and synchronize both the original backing
range and widget constructor/update count. The native Settings text branches
associate these controls with list2. Other controls retain their original
arguments, stack and register state. Complete original GUI rendering remains
unverified; do not claim that a list-query result proves physical visibility.

Offline validation: nine wireless prepare-glue cases (including idle/unbound
completion and live/unbound refusal), seven original non-wireless cases,
240 original/corrected list-constructor and backing-range cases, exact-library
cold commands6/7, original-loader execution of the exact wrapper/library with
a modeled player payload, and final UPG/inventory checks pass. The earlier
64-case owner/native/sleep routing run retains its original source scope; it
is not relabeled as a new follow-up pass. Firmware preparation requires matching
cold-DSO, native-exit and exact Settings-count evidence.

Installer, kernel, initrd and updater behavior remain Sony's. There is one player
body; reverting only the declared count adapter reconstructs the earlier player
body exactly. The supervisor program segments are unchanged. Whole-root regular
file growth remains295,868 bytes across22 changed paths, unchanged from the
startup-working candidate; allocation, bad blocks and physical free margin are
not established by that inventory. Existing external apps, accounts, ROMs,
saves, pairing keys and packet-number journals must be retained.

Earlier startup failures and their immutable packages are retained. Renaming
AppList ID1 breaks SpiderApp lookup; current layouts preserve it. Failed
self-name lookup alone does not suppress the two replayed registration events.
The failed first cold-fix DSO also incorrectly consumes unbound command7;
original main-loop message dispatch precedes the SDK binding anchor, making
that ordering possible. Current code delegates cold commands6/7. Individual
causal contributions to the user's stalled boot are not separately proven.
See KNOWLEDGE.md and ignored physical-validation/build evidence for scope.

The generic QEMU stock-root environment cannot yet reach the original GUI:
InterDSP is absent. A handle-only probe reaches channel/task setup and repeated
DSP READ, then times out. It is not a physical-stall reproduction or a complete
stock/custom boot comparison.

The installed SDK refresh consists of Pet 0.4.0-dev.2, ESP-NOW Chat 0.1.0-dev.3,
Graphics and Pocket FM 0.1.0-dev.22, WiFi Terminal 0.1.0-dev.23, and managed
launcher 0.1.0-alpha.2+managed-radio-review. Changed payloads received higher app
versions; byte-identical rebuilds retained their versions and installed files.
The launcher recognizes the actual Chat contract and retains legacy launch paths
for ordinary apps. Original-libc ARM, handoff and managed-process tests pass with
modeled RF/manager boundaries. Post-install audit reports 17 valid apps, zero
rejected entries, zero inventory failures and no source/installed version gaps.
Only launcher/application package paths were written; account, ROM, save and
firmware paths were excluded. Temporary device staging was removed, and old
package copies plus compiler/update records remain in ignored work/sdk-app-refresh.
Actual UI, RF/account and sleep/USB acceptance of the refreshed apps is separate.

Language switching belongs to the original Settings interface in the current
built-in-localization profile. The external Language app is retired from the
active release catalog and player setup composition. Its source and SDK-migration
baseline remain historical references. The user's installed legacy package was
moved intact outside the app scan; all 17 remaining installed apps pass catalog
and package-integrity checks. Release assembly now selects built-in resources,
and a source-built localization test confirms the Settings selector and omission
of the legacy app/packs from setup. Existing old firmware may lack this Settings
entry until the user installs the prepared new firmware. No X1060 firmware was
flashed by this cleanup.

Core2 alpha.7 has now been flashed with explicit user authorization and no
application backup, as requested. The installed partition table matched the
reviewed layout; OTA metadata selected app0. Only the application at 0x10000 was
written, and esptool verified its hash. A subsequent USB status query reports
alpha.7, LCD initialized at 320x240, and an unpaired radio with no player session.
This qualifies application write/boot and reported display initialization, not
visual interaction, RF delivery or the X1060 control link. Private deployment
evidence is retained under work/core2-remote-deploy. After reconnection and Sony
USB/disk identity checks, all eight paired external files were installed once on
the exposed user volume and verified by hash. No existing destination or PN
record was overwritten. X1060 has not been flashed or run the new service; the
next step is the user's manual operation of the paired original FWUpdater.

Native browse-path review found two functional gaps after the first library UI
integration. BUSY is an asynchronous provider state, not a terminal page result:
the remote now continues the admitted read at most once every 100 ms, with a
two-second continuation window and no command/radio-request replay. Core2 alpha.7 allows a five-second
reply window. Stop prevents further browse steps; terminal timeout is cached.
The real client/owner stream checks cadence, completion, duplicate caching and
timeout, and the actual ARM service/managed SDK chain passes BUSY -> ready with
all five mode packets. Media/RF remain fixtures. Separately, the native Settings
offer used READ|CONTROL only; it now explicitly includes BROWSE. The supervisor
accepts exactly legacy READ|CONTROL or READ|CONTROL|BROWSE, retaining rejection of
insufficient grants. The four-session/sleep chain passes with the new offer.
Core2 alpha.7 builds and retains its frozen artifacts; no device was accessed.
Existing packaged alpha.6 materials are retained and are not passes of these new
sources. A separate fresh alpha.7 set now includes the updated service, explicit
browse grant and supervisor grant handling. Component, exact-wrapper/Sony-loader,
root inventory, final UPG and mixed-input rejection checks pass. Its diagnostic
UPG is 46,805,960 bytes, the external first-use set is 296,916 bytes and system
regular-file growth remains 295,896 bytes. No real device has been accessed or
installed; physical capacity margin, RF, sleep/wake and actual native playlist
semantics remain unqualified. The pending read-only device-identification request
has not been treated as authorization.

The store's remote_list/catalog are application listings, not player music data.
A separate library_wire app protocol
now encodes authenticated bounded browse requests and one full metadata item per
reply, including opaque identity, UTF-8 title/artist/album, duration, revision and
pagination. Request fields match the existing player SDK views; no new Moma/SQL
connection is added. Host sanitizer and Sony-libc ARM codec tests pass roundtrip,
malformed UTF-8, authentication/reserved-field rejection, unchanged failed output
and unsupported replies. The941-byte reply fits the radio client maximum but
requires a larger MCU receive slot than the old status-only buffer. Service
dispatch now calls the existing SDK browse API through a session-bound ledger.
Exact duplicates reuse the cached reply; changed/stale requests and reentry do
not read again. The actual radio client/owner stream passes signed request -> SDK
browse -> signed reply and duplicate-read suppression on host sanitizers and
Sony-libc ARM; provider data and RF remain modeled. Metadata padding is
canonicalized, and an unencodable item returns a protocol error instead of
stopping the remote. Existing five-mode service integration also passes its
regression. Core2 alpha.6 now compiles the larger receive slot, correlated library
client and read-only metadata browser for Tracks/Playlists/Queue with explicit
unsupported/stale/empty/timeout states. Playlist Open/B navigation and revision-
bound previous/next queries are implemented. Host sanitizer and Sony-libc ARM
client tests cover late replies, wrong sessions/requests/revisions, timeout,
clock regression and serial exhaustion. No automatic library polling/retry is
added. UI/provider behavior remains physically unqualified. The
previously frozen diagnostic package is unchanged; its source receipts are now
historical and must not be relabeled as passes of these newer service sources.
The newer service has since passed the four-session/sleep-restart ARM chain and
real managed-owner pre-start refusal/retry chain. Both retain modeled RF/native
sleep evidence. A separate fresh paired supervisor/host/layout/UPG and first-use
set have now been built for Core2 alpha.6, leaving older packages retained.
Component and mixed-input refusal checks pass. The revised UPG is46,805,968 bytes;
system file growth remains295,896 bytes and the external first-use set is296,812
bytes. Neither candidate is hardware qualified or installed; actual browse views
and repeated physical sleep/USB/RF behavior remain open.

The exact C system-start wrapper and SDK library from the current managed layout
now pass an isolated ARM guest loader/exec check with Sony's loader/libc. The
system case uses the real /usr/local paths, preserves PID/argv/name/cwd, inherited
manager descriptors and original preload, removes old test grants and refuses
host-anchor readiness against the modeled payload. Other bootstrap regression
cases also pass. Reviewed-host runs retain timestamped output and clean JSON.
The SpiderApp body is a fixture and the guest kernel is not Sony's: this does
not establish physical boot, GUI execution, RF or sleep acceptance. Current
candidate bytes are unchanged by this additional test.

Private first-test materials now retain a complete updater directory, reviewed
diagnostic UPG, exclusive first-use external set, frozen Core2 alpha.5 images and
RAM-only USB pairing command in one ignored work directory. Updater EXE/DLL/INI
match a separate retained extraction; the original INI/version checks are not
changed. A file-hash manifest and proposed acceptance order are included. The
directory contains private keys and must not be published. ready_to_flash remains
false pending the explicit first-test decision and physical qualification; no
updater, serial port, network session or device write was executed.
Material preparation also verifies the cross-artifact chain: firmware layout to
compiled supervisor, supervisor to external owner/service/configuration, and
external transport keys to the pairing proposal. Negative tests reject mixed
owner, configuration and key hashes before creating a material directory. The
current private set passes this additional check; candidate firmware bytes are
unchanged. This prevents accidental mixed-version assembly, not physical faults.

A private managed diagnostic UPG is now generated for local review only:
46,805,968 bytes. Two builds are byte-identical. Original UPG roundtrip is pinned,
installer/kernel/initrd are byte-preserved, final UPG decrypt/repack checks pass,
and every final root inventory change matches the reviewed layout/localization
inventory. Regular-file growth remains295,896 bytes. Source/input hashes are
retained in ignored work/managed-firmware-review. ready_to_flash remains false:
physical partition margin, boot/RF/sleep/USB acceptance and recovery are not
qualified. No updater was opened, device accessed, candidate installed or package
published. The original installer formats system storage, so preserving it does
not make interruption or a failed first install recoverable.

A private first-use external set now freezes all eight verified runtime, driver,
key and scoped-PN inputs, totaling292,136 bytes. Preparation rechecks component
source receipts, hashes and pairing/PN linkage without device access. The manual
Install-RemoteFirstUse.ps1 entry binds the no-overwrite transaction to Sony
USBSTOR identity, explicit disk serial, WALKMAN/FAT32 and free-space checks; its
target is fixed to HOMEBREW/data/wireless-remote. A PC-side attempt marker blocks
unreviewed repeat attempts. Syntax and synthetic transaction tests pass; Windows
CIM/device installation is not physically qualified or executed. Matching system
firmware, controller provisioning and current-device acceptance remain separate.

The PC-side first-use directory transaction is implemented in RemoteFirstUse.psm1.
It accepts only the eight expected runtime/radio/key/PN files, validates hashes,
refuses reparse paths, stages under the same parent, flushes/readbacks files and
commits with a no-overwrite directory move. Existing destinations always refuse,
even if identical. Ownership callbacks run before and during writes. Local
synthetic tests pass duplicate refusal, cleanup after ownership loss and a
commit-time destination race preserving existing data. It is not yet bound to
the physical WALKMAN identity/mount checks or a device installation plan, and no
device has been written. Partial/uncertain device writes still require explicit
review rather than replaying first-use seeds.

Fresh pairing PN proposal preparation now derives independent TX/RX scopes from
the recorded player/controller identities and AES-128(PMK,API-LMK). It creates
two80-byte first-use records in a new one-use PC staging directory and refuses
to reuse that directory. Existing device journals remain untouched. Actual C
storage interoperability passes host ASan/UBSan: read zero, reserve1..1024,
reject duplicate provisioning and retain1024. Tests use synthetic temporary
records, not the private pairing proposal. Directory entries are collected before
mutations so rename does not cause repeated traversal. Exclusive no-overwrite
device installation is still required; these seeds must never be restored after
the keys have been used. No ARM/storage-device or physical RF qualification is
implied by this PC interoperability test.

Existing private physical logs provide consistent Core2 and X1060 station
identities. A fresh matching XWRUN002 pairing proposal has been prepared locally
from those recorded addresses, with new independent transport/authentication
keys. It has not been installed or confirmed against currently connected devices.
The supervisor and full host now rebuild with that proposal, and component review
classifies it as unqualified-private rather than synthetic-fixture. The paired
resource layout and full root inventory were refreshed; file growth is unchanged.
No old keys or PN records were read into the proposal, overwritten or reset.
The managed owner's resume-only counter path still requires deliberate scoped
PN provisioning for new keys before actual RF startup; pairing files alone do
not establish that prerequisite. No device access or firmware package occurred.

The current Core2 alpha.5 source builds successfully. Each new Core2 review now
retains verified firmware.bin, bootloader.bin and partitions.bin copies alongside
its receipt, rather than referencing only mutable PlatformIO output. The current
application image is1,410,864 bytes. No serial device was opened or flashed;
the physically accepted alpha.4 interaction does not qualify alpha.5 or its
new-session handshake. Controller availability has been requested for the next
explicit hardware stage; current work remains PC-side.

Private pairing preparation now supports XWRUN002 only after validating a fresh
source-built native mode-reader host and its library identity. The reusable
supervisor accepts that modern host review; the finite laboratory review format
is retained. A private five-mode supervisor build passes its ARM entry checks.
The actual service/player-host integration also passes all five mode cases with
modeled media/RF. This is not physical mode acceptance. Updating the supervisor
builder invalidates older supervisor source receipts. A fresh full managed host,
paired resource overlay and root inventory have now been rebuilt with XWRUN002.
The supervisor keeps an independent mode-host receipt/library snapshot, avoiding
dependence on the host builder's mutable output directory; that snapshot's library
hash matches the rebuilt host. Component review passes and the full file-payload
delta remains295,896 bytes. Pairing is still a synthetic fixture, not an installed
controller identity; sustained RF and physical lifecycle acceptance remain open.

The composed managed profile passed a local component-identity review of
the current player ELF, host library, reusable supervisor, real managed RF owner,
service and configuration. Core system file payload growth is222,316 bytes;
this excludes localization/menu resources, the launch wrapper and filesystem
allocation. It is not a whole-root capacity result. The configuration remains a
synthetic fixture, so this is not an installable or hardware-paired candidate.
The review also inventories the compiled user-volume radio dependencies:
sd8686.bin125,960 bytes and helper_sd.bin2,516 bytes, plus a separate32-byte
session.keys and persistent pn directory. It does not read keys, reset packet
numbers or claim those inputs exist on the device. Their current lab paths still
need deliberate package integration. No UPG or device action was produced.
The owner path change was followed by a fresh supervisor/player rebuild and
component-identity review. That current review passes with the formal data leaf;
the pairing configuration is still synthetic and no installable package exists.
`build_remote_owner.py --data-leaf wireless-remote` now compiles both immutable
candidate paths and key/counter traversal for the same user-volume directory.
The120,716-byte managed ARM owner passes Sony-libc entry and non-Sony-root
refusal checks with this layout. Legacy builds default to espnow-test. No key or
counter migration occurs; preserving existing PN state remains mandatory.
The isolated ARM process chain also passes real-owner startup-refusal and retry
with the formal data layout and forwarded ownership capability. It runs the
actual supervisor, service and owner binaries, but rejects before RF on the
non-Sony root. This proves cleanup/retry, not successful radio startup. The
supervisor now also accepts the exact formal user-volume runtime directory,
/contents/HOMEBREW/data/wireless-remote/runtime. The same real-owner refusal/retry
chain passes from that location, preserving config.bin unchanged. A fresh full
host rebuild uses this supervisor; pairing, complete overlay/capacity accounting
and physical acceptance remain outstanding.
The system-layout builder can now reuse the current reviewed managed host and
include its pinned supervisor. The review-only overlay contains one SpiderApp,
the162,172-byte SDK library,6,464-byte C exec wrapper,27,376-byte supervisor and
the modified AppList.conf. Those five paths add228,862 regular-file bytes over
the original rootfs, or196,040 bytes over the selected localization input. These
are different baselines. Other localization/menu resources and filesystem
allocation remain excluded, so neither value is a whole-image capacity margin.
The generated tree is under ignored work, has no installation script or UPG and
is not ready for device use.
The full proposed root inventory comparison subsequently exposed missing paired
Settings wording resources in that initial overlay. The composition now retains
its resource-review path, and the layout builder verifies and includes that exact
resource overlay; absence of provenance refuses generation. After rebuilding,
the complete localization-input-plus-managed-overlay inventory differs from the
original at22 paths and adds295,896 regular-file bytes. This supersedes the
five-path accounting as a total file-payload estimate. The1KiB/4KiB file rounding
models still exclude filesystem metadata/reservations and physical flash state.
No allocated filesystem, partition margin or hardware safety is established.

The full owner runtime now passes sanitizer and Sony-libc ARM checks for mode
revocation or authority timeout while a transmission remains pending. Data
permission closes first, cleanup ownership remains valid, and completion must
precede modeled stock restoration/power-off and the final receipt. A cleanup
failure retains ownership and produces no success receipt. RF, clock and stock
effects are fixtures in these tests; physical shutdown timing is still open.

A player-independent wireless mode/ownership core now issues exclusive leases,
retains old ownership while mode changes drain, refuses new-mode admission until
verified off release and latches uncertain retirement. Explicit bootstrap/repair
and preexisting stock Wi-Fi adoption do not run hardware operations. Host
sanitizers and Sony-libc/LinuxThreads ARM guest tests pass, including stale lease,
foreign-thread and forked-copy refusal. The actual core is now in the remote
backend ARM chain, including mode-change and early-stop cases; off/native evidence
is modeled. A private connected-datagram capability transport now passes actual
cross-process host sanitizer and Sony-libc ARM guest tests, separating Settings
selection grants from consumer acquisition grants. Its client decoder rejects
stale/malformed replies without changing output; client release or death cannot
claim hardware-off. Installed authority registration, native mode UI and original
Wi-Fi interception remain unfinished. This is not an installed global mode service.

The private nonblocking mode client now passes the actual cross-process channel
chain through query/acquire/release and modeled verified retirement, with host
sanitizers and Sony-libc ARM execution. Wrong-generation and reused-FD refusal
preserve output and do not close foreign descriptors. It owns no thread, timer or
hardware operation. Native queue/capability provisioning is not installed yet.

The private Settings transaction now maps native rows explicitly to policy modes,
keeps highlight/cancel local before confirmation, waits for qualified owner
retirement after confirmation, and refuses stale pages. Host sanitizer and
Sony-libc ARM guest cases pass. It is not bound to the stock callback yet.
The compiled native confirmation callback candidate passes75 ARM instruction
cases and has a matching private transaction endpoint. An optional source-built
ELF/DSO composition now pairs its guarded callsite with the actual SDK dispatcher
and mode core. Combined ARM cases cover successful selection and unbound,
foreign-thread, changed-code and changed-pointer refusal. Tagged replies prevent
an unpaired getpid return from becoming success. Production authority binding,
three-choice display composition and real page feedback remain unfinished.

The original WLAN switch encoding is now replayed:4 initialization and144
apply/cancel cases establish property6/0x600 values0=enabled,1=disabled and no
write for selection2. A separate source-built display-only three-choice probe
prepares a140-byte payload and resource overlay with26 ARM cases, zero ELF
growth and blocked confirm/cancel persistence/network actions. It is not a UPG
or device-qualified rendering/touch result; the authoritative three-mode system
and actual native GUI selector remain unfinished.

The original stock Wi-Fi scan/power-preparation paths now pass96 ARM replay
cases. Public states3/4 skip a new power-on request; scan can later power off
those states, and its completion ignores power-off failure. Thus a power-on-only
hook and scan-completion-as-off-proof are insufficient. Wrapper/caller locations
are recorded in sdk/WIRELESS.md. Native execution context and full scan/connect
admission/retirement interception remain unfinished; no device action occurred.
Original factory/FSM execution now checks53 routes, and184 router cases prove
which operations enqueue to the Wi-Fi pthread worker versus dispatch directly.
Scan/power/connect normally use the worker; selected cleanup/cancel events can
use a direct path. A GUI-owned policy cannot simply be called in all RF wrappers.
Cross-owner admission/cancel integration and hardware ordering remain unfinished.
The original power-off replay now includes lower-level failures and eight chained
daemon+wrapper executions: stop/unload failures propagate16 and retain daemon
state, unlike the higher scan completion. This supports using the original
shutdown result plus ownership/state checks for retirement, with no daemon edit.
Physical cleanup and the installed retirement adapter remain unqualified.
The private native-owner lifecycle adapter now links queue admission to the mode
core, reuses a single stock lease, stops once on drain and retains ownership until
trusted retirement. Host sanitizers and Sony-libc ARM tests pass queue/retirement
failure, natural shutdown and preexisting lease adoption. It retains no native
message/payload pointers. Actual original-router/cancel binding is not installed.
The second seven-group wireless configuration FSM now passes1,142 original
table-routing cases in addition to the primary53 cases. WPS prepare/PIN/Vista/
PBC and cancel wrappers are located separately from registration-only changes.
Admission cannot cover only scan/connect or indiscriminately reject every stock
configuration event. Actual WPS execution/admission and queue binding remain
unfinished; no device action or firmware package was created.
Eighteen original WPS wrapper cases now establish that PIN/Vista/PBC registration
still runs after prepare returns16; preparation-only admission is insufficient.
The private mode channel now supports a READ-only view of an existing native
lease for a worker, without transferring or releasing actual ownership. Actual
cross-process and Sony-libc ARM tests cover denied mutations, drain revocation,
retirement and view-close preserving native ownership. Installed worker capability
provisioning and RF callsite binding remain unfinished.
The private native-worker permission boundary now passes real pthread host and
Sony-libc/librt ARM tests: exact lease matching, GUI-thread refusal, revocation
and silent-authority timeout. It creates no worker/timer/background polling and
uses the verified monotonic clock bridge. Timeout retains actual ownership.
Stock worker provisioning, callsite binding and lock ordering remain unqualified.
An isolated RF callsite candidate now composes460-byte source anchors, ten BL
changes covering eight RF operations, a guarded native worker-entry pointer and
the original GUI router call and four owned-cleanup entries.
Forty-eight ARM cases run original wrappers through anchors and the C receiver,
checking refusal, image gate, arguments, results and r7/errno preservation.
The optional paired profile now registers the RF receiver through the actual SDK
shim and compiles worker permission/TLS and generated code/callsite guards. Its
43-case ARM combination passes, along with the default seven-case regression.
Real pthread host/Sony-libc ARM tests cover independent TLS binding and destructor
cleanup. Worker entry now attaches a constructor-prepared delivery endpoint;
the GUI router bridge now triggers publication after authority binding. Conditional
startup qualification is now compiled; hardware startup, native retirement and locks remain unqualified, so the build
still reports no fully provisioned runtime.
Same-worker renewal now validates a fresh strictly newer native lease/view before
replacing TLS. Real pthread host/Sony-libc ARM tests retire/reacquire at the
authority, renew the worker and reject old/relabelled capabilities; failed
replacement preserves the original view. Automatic receiver bootstrap is now
compiled; software startup bootstrap is implemented and no physical cycle was performed.
SCM_RIGHTS delivery now passes real pthread host/Sony-libc ARM tests for initial
adoption and renewal, invalid offers, GUI self-adoption and received-FD cleanup.
This exposed and corrected the LinuxThreads per-thread PID distinction: native
binding uses kernel socket peer credentials for the GUI, with separate worker
PID/thread ownership. Fixtures now use the actual producer GUI PID and reject
wrong peers/forked copies. Real pthread host/Sony-libc ARM tests now also cover
automatic receipt/renewal and destructor FD balance. Native worker-entry ARM
tests preserve the original worker argument/body and reject modified bootstrap.
The actual private publisher now creates/reuses/replaces observation views and
publishes each lease once. It is compiled into the SDK, whose owner hook handles
queries before player work and flushes a just-pending reply. Original-loop ARM
tests check tick dispatch/errno; real pthread host/Sony-libc ARM tests exercise
the actual backend through two automatic publications and FD balance. Original
GUI RF-request-triggered publication is now composed and checked for event/argument
preservation and original delegation. Real pthread host/Sony-libc ARM cycles use
the actual request handler for acquisition/publication and modeled retirement;
backend close refuses retained native ownership. The original worker now gathers
one read-only software-closed observation and generation; the GUI automatically
qualifies the original cached On/Off byte and binds authority.128 boot condition
cases, parser/error fixtures, four actual cached-getter cases and host/Sony-libc
ARM tests pass. The channel chain covers WBS1 auto-binding, rejected/Off startup
and request/renewal. Status/modules/entropy/flag identity remain fixture inputs.
Early GUI requests now coalesce only authorization demand until binding; original
messages/tasks are not retained or replayed. Worker-only initial offer waiting
and QUERY validation have separate bounded phases, with no GUI wait or duplicate
query after valid delivery. A test-link poll marker forces the early race in real
pthread host/ARM tests; Off/failed startup still grants nothing. Retirement now
requires the full exact key, rejects old completions and closes the retired view
without idle socket polling. Whole boot latency, actual native retirement, lock
ordering and physical RF remain unqualified; no device/package action is implied.
Original power-off results now feed a fresh exact-lease drain/failure observation
and WRO1 notice. GUI retirement requires native success, public closed state and
four unloaded modules; stable scans and old notices cannot release new ownership.
Host/Sony-libc pthread chains cover actual notice delivery, native error, masked
module failure, later qualified receipt, retained FAILED state and FD balance.
The original BusyBox unload replay proves later rmmod failures can be hidden by
the stock script's let/status sequence, so native success alone is insufficient.
The worker seals its old key before successful notice and cannot touch hardware
through queued old data/cleanup afterward. A fresh lease replaces that sealed
context; accepted notices are not repeatedly resent. Native GUI cleanup also
respects ownership. Owned/refused/sealed cleanup and independent ESP ownership
tests pass. The shared module parser now also protects the optional ESP owner
power-off policy, including reported-off/residual-module refusal; host/stock-libc
controller/runtime tests and the finite owner build pass. The original script
is unchanged. Proactive native stop initiation, never-started
leases, full mode UI and physical RF/lock qualification remain unfinished.
The candidate is analysis-only, has no UPG and is not ready for device use.

Wireless mode is now an explicit separate source contract: the remote backend
requires an existing ESP-NOW selection, cannot select it, and retires when the
policy view changes away. Off/Wi-Fi/unknown refusal, normal remote stop retaining
ESP-NOW selection and a modeled switch to Wi-Fi pass the ARM chain. Generic
radio restoration/power-off/release lives under platform/wireless; the remote
wrapper only delegates. The original WLAN enable entry/page is located and its
12 native routing cases pass. The actual three-mode menu and authoritative
cross-process/native Wi-Fi handover are not implemented; see sdk/WIRELESS.md.

An analysis-only native Settings routing profile now appends Wireless Remote
after the retained Japanese settings and Language. Its source-built68-byte
callback and localized labels pass190 native list-selector cases and13 route
cases, with zero ELF growth and no undeclared changes. The paired opt-in host now
checks callback/list/pointer fingerprints and routes that anchor to the original
owner's one-request queue. Fifteen anchor scenarios, actual queue/cancel/foreign
thread tests and ten stock-loader bootstrap cases pass with modeled boundaries.
The concrete backend is exercised through this queue in the ARM chain; production
auto-binding, state/progress UI and original RF admission remain unfinished.
No firmware package or physical GUI acceptance is created by this profile.

The supervisor now supports direct adoption of a trusted SDK player descriptor
without a player exec/startup rendezvous. The actual supervisor/service/SDK-host
ARM guest chain passes direct delivery, generation/grant rejection before owner
startup, and the old rendezvous regression. RF and playback are modeled. This
removes a transport dependency on player startup. The concrete Settings launch
backend now uses this path; production GUI auto-binding and native admission
remain unfinished.

A private C supervisor launch/reap component now passes host sanitizer tests
and the actual supervisor/service/SDK ARM guest chain. It uses a fixed exec path,
explicit prequalified admission, capability transfer, bounded RAM logging and
nonblocking reaping; failure does not become an off/ready claim. Rejection,
inherited environment/FD cleanup, descriptor reuse and abnormal child exit are
checked. It is not automatically bound in installed Settings. Actual SpiderApp atfork/SIGCHLD and UI
timing, generation/profile renewal and native admission remain unfinished.

The internal stock-power-off helper and remote-specific restoration/power-off/
fin adapter pass host sanitizers and stock-libc ARM926 tests. They refuse active
or borrowed stock Wi-Fi, require explicit exclusive admission and retain the
manager on uncertainty. The generic controller's previous restore/reconnect
regression also passes. The finite RF owner has an explicit `--power-off-exit`
build profile selecting this policy; its default behavior is preserved. The
actual owner runtime/gate/IPC test also passes the power-off policy through
inflight TX, cleanup and completion receipt, including cleanup failure refusal.
That profile uses operator-confirmed lab admission, not global native ownership.
Original Settings integration, production admission, physical power-off and the
complete remote switch remain unfinished. No new device deployment is implied.

The private player host can now drain an ordinary SDK service without exiting
Sony playback, then accept a strictly newer generation after complete release.
Four stop cycles pass host sanitizers and original-libc ARM execution, including
commands after reopening and1000 idle dispatches without reopening native handles
after each stop. A separate generation-scoped stop callback can retain STOPPING
until external retirement is confirmed; a failure latches FAULT and refuses
rearm. Native-exit dependencies without that explicit stop contract are refused;
faults/native exits remain non-rearmable. This is not
yet the complete remote Settings switch or RF power-off path.

The built-in localization profile is now source-built independently of retained
candidate binaries. It enables the native Settings language row and embeds the
completed English/Simplified/Traditional STX resources alongside Japanese. A local
localization-only UPG passed unpacking, unchanged-component, translation and
archive-metadata checks. Its regular-file growth is98754 bytes versus stock
(106496 bytes with4KiB file rounding, excluding filesystem metadata). It has not
been flashed and does not contain player SDK startup activation. A separate
source-built SDK composition and paired ARM host pass with the same built-in
Settings base; ELF length is unchanged. Joining SDK startup and the persistent
remote Settings/lifecycle policy into the final installer remains unfinished.
External-language unmount involvement is a hypothesis, not an established cause
of the reported black-screen wake failure; physical sleep/wake acceptance remains
pending. Existing Core2 input-navigation acceptance is unchanged and does not
qualify the new firmware or five-mode radio link.

The system-preload bootstrap profile now loads the SDK without granting a remote
session and clears inherited one-shot grant variables before exec. The native
Sony loader/ARM guest test covers10 cases, including this profile, original
SpiderApp argv0, PID, cwd and inherited file descriptors. The payload is an
identity probe, not the full stock GUI. `tools/prepare_player_system_layout.py`
prepares a review-only root overlay with one SpiderApp, the paired DSO, a small
C launcher and one executable-field change in AppList's default application.
It adds103504 regular-file bytes over the localization-only build, without an
extra player copy. This overlay has no remote Settings action, controller grant
or radio activation; it is not a complete remotely controllable firmware and
does not produce a UPG. Original manager launch and hardware acceptance remain
pending.

The guarded player host now has limited physical acceptance on the X1060:
the real ARM client received a READ-only session, obtained a VOLUME-only valid
snapshot and closed successfully. A separate explicitly CONTROL-authorized run
observed one native volume step and one inverse step restoring the starting
value, then received a close receipt. Both one-shot overlays detached and the
original player path was SHA256-verified again. No candidate-player/probe process
remained after the first handoff. A later separate read-only physical observation
reached PLAYING with track identity, title/artist/album, five notifications and a
successful close receipt. Media browsing, sleep/USB and the complete wireless
remote remain unqualified by those player-only runs.

The Cardputer LCD development front end0.1.0-alpha.1 was written through the
ESP32-S3 ROM path after the user declined backups. The explicit3MiB app partition
fits the image. Serial reports LCD initialization,240x135, ESP-NOW initialization
and an8-quarter-dBm TX limit; the user confirmed the idle screen displays normally.
That display-only milestone did not connect player data or keyboard control.
Cardputer alpha.3 subsequently booted with status-receiver and keyboard code;
its serial version/LCD/radio initialization were verified. A full isolated ARM
guest now passes the actual supervisor, service, player SDK host, duplicate
PAUSE suppression and retirement chain, with media and radio effects modeled.

The first finite physical remote attempt staged user-volume inputs, paired the
Cardputer with fresh RAM keys and requested a cooperative return to Sony through
the one-start wrapper. UART observation did not record an active player session.
Device logs are still required to locate the failure and verify owner retirement
and post-run overlay status. Do not treat the elapsed window as proof of cleanup
or end-to-end RF success. No firmware was flashed or system partition written.
Temporary executable/key cleanup must wait for actual process/ownership checks;
the originals and retained evidence must remain available for that check.

2026-10-30 physical encrypted TX now passes eight byte-exact nonempty
X1060-to-Cardputer payloads through 1470 bytes, using the observed ESP-IDF profile.
A second native process reused the same key and durable user-volume PN records;
the Cardputer peer remained installed. Its eight payloads also matched exactly,
with PN reservations continuing from 10241 rather than restarting at one.
Both runs completed ten MAC transmissions, exited and restored authenticated
Terminal access. Zero-length transmissions completed at MAC level but did not
produce Cardputer receive callbacks; application delivery is not supported by the tested standard peer. Bench0.1.3
fixes its null-zero callback guard but does not change that physical result;
standard IDF5.5.1 itself returns ESP_ERR_ESPNOW_ARG for a zero-length send.
This proves process-restart persistence, not arbitrary power-loss behavior.
The alpha.2 worker uses XNOWdev.14. Native encrypted RX also authenticated twelve 1470-byte packets from Cardputer;
the first decoded payload SHA-256 matched the original exactly and authenticated
Terminal access returned after stock restoration.
full encrypted bidirectional/lifecycle acceptance remains open. SDK alpha.7 is
an older source snapshot and does not yet export this physical-profile update.

Alpha.3 adds RX resume without reprovisioning. Two physical native RX processes
using one key and the retained Cardputer peer authenticated1470-byte messages;
the validated user-volume replay record advanced from19 to38. Both restored
Terminal access and first-message digests matched. This establishes receive
continuation across a native process restart, not over-air replay rejection or
power-loss safety. Alpha.3 is installed separately from the older test workers.

SDK0.2.0-alpha.7/XNOWdev.12 incorporated the plaintext-broadcast compatibility
fix and explicit receive authentication/broadcast flags. Native consumers must
be rebuilt for the extended receive structure. Host/original-libc ARM endpoint,
secure-owner and partial-pipe tests pass; no installed apps or firmware change.
Encrypted over-air interoperability and full hardware qualification remain open.
Earlier SDK release evidence below remains historical, not retagged as alpha.7.

The experimental [SDK](sdk/README.md) adds a source API, three starters and two
maintained development examples. Host/ARM fixtures and clean-bundle builds are
computer-side evidence. No new SDK hardware acceptance was performed by this
migration. Callback-profile state IO defaults to denied until ownership is
qualified; native services retain the existing app policies.
SDK publication is independent of the firmware/app release composition below.

The original-player SDK analysis host now attaches a validated single-item
selection adapter to its broker and advertises PLAY_ITEM only after attachment.
GNU link, host thread/IPC regressions, original-loader PID interposition and
original anchor/provider instruction checks pass. These are offline component
tests: SpiderApp has not booted with the complete service, and native media,
sleep/USB and physical playback acceptance remain open. No firmware or published
SDK archive changed. See the [player client guide](sdk/PLAYER_CLIENT.md) for
admission versus observed playback and explicit pending-command polling.

Private analysis builds now also offer a managed host profile, optionally with
the native engine-control adapter. It opens no legacy listener and requires a
trusted original-owner caller to deliver an authorized connection/generation.
Host/original-libc ARM tests cover public-client controls, observations/events,
media browsing, descriptor delivery, real reader drain and one-shot continuation;
native media/playback remain modeled at those integration boundaries. An explicit
native-prepare analysis profile now pairs its composed exit bridge with the
production PID/context/policy code; original manager descriptor delivery, complete
SpiderApp startup, event ordering and hardware acceptance remain absent. These
profiles are not firmware packages or installed services.
An original-manager guest test also confirms a direct resident-class C child
registers under its configured ID and survives a Home mode1 exit/relaunch with
one stable PID and the same sysmgrd parent as Home. This is a headless-consumer
execution candidate, not an SDK grant/delivery path or physical qualification.
The missing-resident negative probe fails before Home startup: original sysmgrd
panics at ApfDaemonCore.c:998 when its resident executable is absent. Directly
registering removable external apps as boot residents is therefore rejected.
The failed report remains failure evidence; no firmware or device configuration
was changed by this guest-only test.
The separate registered-resident normal-exit probe passes: after receiving its
APF registration reply, the C client returns zero, sysmgrd continues and Home
completes the launcher round trip. Missing executable and successful registration
followed by normal exit are therefore distinct paths. Restart, abnormal exits,
SDK drain and physical lifecycle remain unqualified.
The registered-client exit-code23 negative probe triggers the same original
manager abnormal-termination panic and fails the Home round trip. Successful
registration alone is not failure isolation; ordinary SDK errors must not become
nonzero exits of a manager-owned resident. No production resident is enabled.
Request2 now launches a normally exited resident again in the original-manager
guest. Initial reply timeouts are addressed in the C Home fixture by servicing
the separate notification socket during all synchronous replies, preserving
lifecycle events in a bounded queue. Four fresh runs complete two registrations
and the Home round trip. This is a fixture correction and original-manager guest
evidence, not a deployed SDK connection path or physical acceptance.
The resident-SDK profile now combines original-manager launch, an ARM managed
host and a separate public ARM SDK client in the same generic kernel guest.
Controls, observations/events, all media views, selection polling and session
close pass alongside the Home round trip. Both SDK processes use Sony libc;
player/media are models and descriptor authority comes from a fixture fork shim,
not production original-manager authorization or a live SpiderApp provider.
An opt-in inherited-delivery adapter now invokes the real managed-host offer
from its qualified owner dispatch using a trusted startup's connected Unix
datagram endpoint/generation/grants. It is one-shot, default-off and canceled by
native exit; no listener or client discovery is added. Actual host/broker/reader
drain tests pass under Sony libc in the generic ARM guest, and the full
managed/engine/native-prepare DSO links. Trusted device startup, complete GUI
execution and physical controls/media remain unqualified and uninstalled.

Production selection/reader code also passes real detached-worker creation,
replacement/cancellation, source loss and drain/destruction using original Sony
LinuxThreads0.10/libc2.3.3 in an isolated generic ARM Linux2.6.32 guest. Native
media/GUI results remain modeled; this does not qualify Sony's kernel or hardware.

The combined public SDK client and broker/selection/readers now also pass as two
separate processes in that ARM guest, using original socket/clock/thread APIs.
Readiness, controls, observed changes, browse and selection polling, single
submission and graceful shutdown are checked; player/media/GUI remain modeled.

The opt-in C exec bootstrap and actual player DSO also pass registration as ID1
and launcher/graphics/launcher/return switching through original sysmgrd and
appproxy in the isolated ARM guest. The Home payload is a C protocol fixture;
devices and state volumes are simulated/RAM. The unchanged bootstrap-disabled
baseline also passes. This does not establish full SpiderApp startup, playback,
sleep/USB behavior or physical acceptance, and produces no firmware package.

Source composition now includes the queue's Met anchor alongside current
Homebrew feedback/error and language-cache edits. Its checked zero slot precedes
the language payload and avoids the standalone trampoline's Homebrew overlap;
the combined edit adds zero ELF bytes. Guarded ARM dispatch and mutation rejection
pass for both layouts. Whole-player execution and installation capacity remain
separate open checks; this is an analysis-only ELF, not a flashable release.

Current SDK0.2.0-alpha.6 adds explicit espnow-owner source services, including
managed handoff, generic binary IPC and full owner runtime. The public consumer
passes original-libc ARM926 execution and C++ header syntax. This neither updates
installed apps/firmware nor qualifies full ESP-NOW hardware operation. Original
platform/APF/USB/sleep, protected hardware admission and standard encrypted peer
interoperability remain outstanding. The standalone XNOW archive remains dev.11.

A concrete crypto compatibility gap is now confirmed at the source boundary:
native management nonce10 differs from ESP-IDF's espnow software branch nonce00.
The actual S3 RF/hardware profile is not yet determined. Native MIC verification
remains enabled. Generic CCMP and journal tests do not establish encrypted ESP-NOW
interoperability; resolve this before attempting an encrypted compatibility claim.

SDK0.2 adopts the16 existing apps through native services. The user reports
successful testing of prior local builds; exact personal package identities
were not supplied. Function bodies, formats and policy are retained. Same-path
CI compares runtime and resources, with only identified non-loadable GCC file
markers normalized in memory. This is new offline evidence, not a new physical
acceptance report. ESP-NOW was excluded from that original migration.
SDK0.2.0-alpha.2 now adds optional generic ESP-NOW services separately; the
underlying XNOW library passed a bounded physical bidirectional exchange and
stock restoration. See [ESP-NOW SDK scope](sdk/ESPNOW.md).
See [native service adoption](sdk/SERVICES.md).

Baseline: VERSION 0.1.0-dev.17, Japanese 1.11 platform, one physical NW-X1060.
NW-X1050 is a target without an equivalent device report.

| Area | Established | Still unverified |
| --- | --- | --- |
| Firmware | Matching extraction, component hashes and original reconstruction | General installation/failure recovery safety |
| Root filesystem | Live 148 MiB partition, ext2 read-only root | Arbitrary new-image installation and bad-block handling |
| Native execution | Terminal UI, authenticated commands and launch credentials | Every app and all Home/USB/sleep paths |
| Terminal | Live pinned TLS, root shell, reconnect, command output/exit status | Long stress, forced-stop and full cleanup lifecycle |
| Localization | Four-pack design and offline cache tests | Candidate 12 physical sleep stability after candidate 11 incident |
| FM | Native 76-108 MHz implementation, offline checks, Si470x live binding | Exact chip ID, RF/audio and restoration on hardware |
| Wi-Fi | Existing connection, route, DNS and public ICMP | Cold-connect/helper ownership and QQ HTTPS on player |
| QQ Music | Native feature implementation complete: QR login, collections, artwork, source download, tagged MP3 import, progress/cancel and Wi-Fi/clock preparation | Continuous real-account/new-download/device conversion/import/Sony recognition/playback hardware acceptance |
| Other apps | Source and builder-specific offline checks | App-specific hardware qualification |

The physical clock was observed in January 2008. The terminal's exact pin does not
qualify ordinary HTTPS certificate dates. Latest QQ work includes Cookie/HTTP
compatibility and manual retry handling; an old service response is not a permanent
diagnosis. Do not rotate identities or import cookies to evade unexplained errors.

Source-based CI now builds an experimental firmware profile, fourteen app packages
and an explicit GitHub Release repository snapshot. See RELEASES.md for publishing
and prerequisites. These are computer-side builds: no firmware was flashed or new
hardware qualification inferred from old reports.

## Application cohesion

Project version 0.1.0-dev.21 gives all sixteen maintained apps local metadata,
artwork, versions and build entries. tools/build_app.py is the shared entry point;
public release composition uses it too. All sixteen completed offline ARM builds
and full-package inventory/resource checks during migration. The launcher review
version is 0.1.0-dev.19 and consumes external presentation.bin. Unknown-ID rendering,
malformed/link/FIFO fallback, metadata and native market list/version checks pass.
See APP_SPEC.md for commands, formats and the generic remote-icon limitation.
No device was accessed or firmware built for this maintenance.

## Aqua Link experimental demo

The `glass-marble` app now uses a calm 32-column volume-conserving surface and
one goldfish, with 120-byte AQF3 snapshots and millimetre viewports. Alpha.6 fixes
the camera-up/USB-left Mosaico display compensation at 270 degrees, following
physical user confirmation after runtime rotation and gravity recalibration.
The main task has 16 KiB stack; the former alpha.2 3584-byte task was smaller than
its at least 6224-byte compiler call-site frames and physically restarted.
Rendering and simulation are separate; ARM rendering uses a smaller buffer,
speed-oriented compilation and snapshot interpolation. Original particle source
and failure evidence remain distinct from the calm revision.

XNOW dev.16 adds complete owned packet-span transfers, rejects malformed
sub-minimum RX spans and refuses binding a backend from a different boundary.
Direct guard tests reduce 1208-byte RX remote operations from 3322 to 322, without
claiming a physical throughput figure. Host sanitizers, original-libc ARM tests,
controller/crypto/instruction fixtures cover their stated boundaries. The foreign
integration fixture now includes the complete receive-flags and span ABI.

The X1060 app and managed launcher were installed on verified exposed user
storage. Mosaico images were written and byte-readback verified; user feedback
confirmed recovery from restart and improved connection/flow, with display
orientation corrected using 270-degree rotation. The user subsequently confirmed
alpha.6 on both endpoints and normal flow after upright recalibration. Initial
reference posture remains significant; long load, HOME/USB/sleep and full recovery
remain separate from those bounded observations. See [Aqua Link](apps/GLASS_MARBLE.md).

The native mode drain now proactively posts the original coalesced disable event,
retries queue backpressure and handles cleanup-only adoption for a lease that
never began RF. Original queue ARM execution passes five cases; the real-thread
mode-channel chain passes normal and never-admitted retirement scenarios. A
post-dispatch checkpoint preserves the original result and skips image hashing
for unrelated events. This remains an offline candidate: the native three-mode
display, original setting synchronization and sleep/USB/app-exit handover still
need composition and hardware qualification. No firmware package was generated.

The paired wireless initializer now obtains a tagged current-row reply from the
GUI-owned mode authority and posts the original selection event after stock page
initialization.120 ARM initializer cases pass with modeled UI accessors and
reply targets; mode-policy refresh/drain refusal passes host sanitizers and a
Sony-libc ARM guest. This is session state, not persistent ESP-NOW mode storage.
Original Wi-Fi flag synchronization now delegates to the original confirmation function after successful SDK apply; device rendering and physical handover remain unqualified.

The optional RF preparation bridge now quiesces wireless ownership before
continuing command3 preparation. A GUI-loop poll revalidates the native view and
waits for qualified retirement, then follows the existing SDK resource decision
or empty-session factory continuation. Seven wireless-preparation ARM cases and
seven ordinary-profile regressions pass, including deferred empty/active session
paths. Radio retirement and native component effects remain modeled. Sleep/USB
entry identification and physical manager scheduling are still unqualified.

A production C command6 bridge now waits for reversible radio retirement and
SDK service stop before invoking the original coordinator with fresh local
output. Nine ARM C/view/coordinator cases pass. The optional RF build now
redirects guarded callsite0x71f5c through the existing PID/prepare anchor and
pumps the adapter from the GUI owner loop; command3 remains separate. Native command7 entry and post-APF-result observers are now paired: the52-case
ARM suite covers successful next-cycle reentry and failed activation retaining
refusal. The18-case C lifecycle suite and72-case original APF confirmation replay
also pass. Native manager/radio scheduling remains fixture supplied, so this
analysis profile is still not a flash candidate.

Opt-in automatic Remote Settings binding is now composed by `--remote-profile`
from a validated reusable supervisor review. It registers OFF after original
SDK dispatch and bypasses idle OFF polling. The automatic factory ARM chain
passes three sessions, foreign-generation isolation, mode handover and native
exit; native readiness/radio remain modeled.19 readiness cases and52 main-loop
route cases pass. A fixture profile was used for local composition, not an
installable radio profile. Native sleep/USB and real-owner/device qualification
remain incomplete; no firmware package was generated.

## Native sleep deferral (offline analysis)

Original manager/client instruction checks establish prepare notification3 and
command18 acknowledgement, including the active Main3/4 branch that bypasses
Root command1. An acknowledgement reply is not a wake signal: a non-final app
can receive its reply before sleep starts. See KNOWLEDGE.md for the bounded
notification conversion and recovery branches.

`sleep_retirement.c` sequences admission quiesce, radio retirement, SDK stop,
context revalidation and one original acknowledgement. `sleep_host.c` calls the
production SDK/wireless APIs. Shared owner-issued epochs avoid conflicts with
command6 handoff. Five sanitizer/freestanding ARM scenarios and the actual
supervisor/service/SDK ARM chain cover pending resources, wrong owner, stale
context, uncertain retirement, process reap and duplicate acknowledgement.
Native validity/ack and RF evidence remain modeled in that process-chain test.

`sleep_native.c` qualifies all four direct Main ack callsites0x614f0/0x61648/
0x61940/0x61c5c using pinned
getter/ack hashes, Main state, APF sequence and Root/tracker snapshots. The ARM
binding cases execute the original getters and acknowledgement client. Loader identity,
initial state, radio/SDK retirement and transport remain fixtures in that check.

The explicit `--native-sleep-analysis` host build composes an acknowledgement anchor in
existing RX padding at0x4d8900, redirects the four Main calls, dispatches requests
through the qualified PID shim and polls deferral from the owner loop. Before
owner binding it retains original acknowledgement fallback. After binding,
unqualified/foreign/pending requests suppress premature acknowledgement. The
standalone anchor's eight ARM checks cover handled/fallback behavior, register
and stack preservation, exact byte reversal and zero ELF growth.

The composed host library links successfully. An earlier56-case owner-anchor ARM
snapshot passed, including sleep request routing, modified callsite refusal, foreign-owner
refusal, pre-binding stock fallback and owner-loop polling. Sleep begin/poll are
counter fixtures in that routing suite; the production native binding and actual
process-retirement chain have their separate checks described above. This is
not a single full native/RF/suspend execution.

An earlier idle-fallback snapshot passed six targeted owner-anchor ARM cases.
When the wireless authority has never bound, the owner shim retains stock ack
only if the owner-side resource check confirms no live SDK sessions,
offers, broker resources or native-exit preparation. Unbound authority with a
busy SDK still suppresses acknowledgement. The resource check is modeled in
this routing suite; its production resource checks are separate SDK evidence.
The earlier56-case snapshot is not relabeled as a pass of this newer revision.

This option is disabled by default and is not selected by firmware packaging.
Recovery observers in `sleep_native.c` are now paired in the analysis option:
command15 callsite0x71e6c delegates through the existing preparation bridge,
and the original Main restore action is wrapped at0x4d8940. The wrapper runs
the original action first and preserves its result before observation. Combined
anchor occupancy is96 bytes with zero ELF growth. Twelve targeted owner-anchor
ARM cases pass, including both new observer routes; their begin/complete bodies
remain counter fixtures in that routing test. Original Main command15 completion executes3/4 ->3/1 in its bounded ARM
check. The private recovery logic requires an acknowledged sleep, matching
owner/context, command15 entry, successful original action completion and a
later stable Main3/1 sample before releasing the wireless handoff. Twenty-two ARM
binding cases cover missing/rejected recovery, sequence rollback, legitimate
native-query sequence advancement, changed Root state, USB busy and pending
wireless retirement. Radio resume remains modeled in that native binding test.
The actual SDK/factory/supervisor/service ARM chain now passes four distinct
remote sessions, including sleep retirement followed by a fresh generation and
successful control. Stale generation/lease operations cannot stop the new
session; a foreign application's active radio lease delays recovery without
being revoked. The production host resume adapter calls native recovery
validation before releasing the handoff and clearing the old retirement gate.
Native recovery proof and RF/off remain fixtures in the process-chain check;
other recovery branches and physical repeated-session acceptance remain open.
The non-owning Main2/2/APF-inactive branch retains stock acknowledgement when
the player's SDK resources are independently idle; it does not retire a foreign
application's radio lease. `xw_player_host_resources_idle` shares the generation
resource predicate without granting admission or consuming a generation. The
process chain verifies busy during a live session and idle after retirement even
while wireless player admission remains closed.
The composer verifies the complete direct-BL inventory in the pinned text before
patching. Original Main transitions2/1 ->2/2 and3/7 ->3/4 execute in the bounded
completion check; deferral tolerates only those qualified post-action changes.
Native binding scenarios also run another acknowledgement after successful
recovery, using a fresh shared epoch and the updated APF sequence. Indirect-call
coverage and physical event timing are not established by this inventory.
Native scheduling, real RF/off, physical sleep,
USB interactions and recovery remain unqualified; no flash package is produced.

## Real RF owner migration

The real power-off-exit owner builds as a180-second qualification profile with
Sony-libc entry/refusal checks; it remains explicitly unsuitable for persistent
native Settings use. `owner_admission.c` now consumes a trusted READ-only mode
view and exact lease. Six sanitizer/Sony-libc ARM cases cover grant matching,
revocation, transport loss, fork refusal, observation-only close and stale grant
reuse. The helper owns no timer, thread or radio operation; cached permission
requires caller refresh and the managed stop channel. Factory descriptor
provisioning now exists: the factory creates a READ-only view of the exact
remote lease, reuses it across repeated launch admission and disposes it after
qualified process retirement. The four-session ARM chain queries the real
factory view before and after recovery, rejects stale generations and verifies
cleanup. Opt-in supervisor forwarding now passes the connected view and exact
lease through fork/exec to the radio-model child. Four ARM sessions (including
sleep/restart) query the actual authority before test traffic; the legacy
three-session path also passes. The connection has one reader/serial stream;
parent diagnostics do not consume delegated replies. Start failure and normal
close clear borrowed metadata without closing the factory-owned view. The full
automatic/sleep/view-forwarding host library also links, using the reviewed
supervisor flag to enable forwarding. The actual owner's `--mode-view-required`
qualification build now consumes the inherited view before any RF initialization.
Three Sony-libc user-emulation entry cases cover matching, mismatched and revoked
reply fixtures; all refuse before RF on the non-Sony root and produce the
never-started receipt. The legacy finite owner also retains its entry checks.
Clean pre-start refusal now has a typed outcome: only a verified startup-failure
receipt/EOF plus the pinned service1/owner69 exits produces supervisor70. The
mode-view parent treats that as disposed rather than ready, and two real-owner
ARM refusal/retry cycles pass with no RF initialization/control. Normal four
session/sleep and legacy three-session process regressions pass too. Periodic
mode refresh is now compiled into the real owner:200ms refresh and1000ms stale
DATA revocation, with supplied-clock cadence/timeout/regression/channel-loss
cases passing host sanitizers and Sony-libc ARM. Cleanup ownership remains
separate. Timing defaults still need physical calibration.

The opt-in managed-session owner has no fixed60/180-second run window, requires
mode-view/power-off retirement and follows parent stop/pipe lifetime. It builds
with the original fixed-layout clock bridge and passes two real-owner
startup-refusal/retry cycles in an isolated ARM guest. Sustained RF operation,
revocation-to-power-off timing, battery/standby and physical sleep/USB acceptance
remain open; no hardware qualification or flash package is implied.
No device was accessed and no RF was started by these checks.
