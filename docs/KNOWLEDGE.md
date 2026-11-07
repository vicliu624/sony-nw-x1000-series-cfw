# NW-X1000 platform knowledge

This is the durable handoff for Japanese NW-X1050/NW-X1060. Read STATUS.md and
HARDWARE.md alongside it. Other Sony families and international NWZ-X images are
comparison inputs, not compatibility guarantees.

## Firmware identity

### QEMU startup boundary

The generic Versatile ARM926 guest now displays the original Japanese Sony UI
and accepts portrait touch. The exact original AppList is essential: its
cnmgr_daemon unblocks the original Home client's connection-manager FIFO open.
A minimal AppList is insufficient even after graphics initialization succeeds.
Original SpiderApp, sysmgrd, appproxy and libraries remain unchanged. The separate
PC preload adapts selected libc device calls and an empty OpenMAX registry;
no native menu states or queue events are injected by the viewer. See
[the QEMU guide](QEMU.md) for preparation, models and controls.

The GUI profile uses synthetic RAM state/platform configuration, unplugged USB,
idle power, a numeric NC control cache, silent mixer/beep controls, the original
framebuffer ABI and touch decoder. Framebuffer mmap must accept SpiderApp's
5MiB mapping, although its display pages are smaller. Sony RGB565 pages must be
converted into the actual generic CLCD bitfields; assuming the generic device
is RGB565 produces incorrect colors. Cached component lookup tables avoid
three software divisions per pixel on ARM926. The timer bridge uses the stock
two-word clock ABI, not a modern time64 structure. The touch device exposes a
latest shared snapshot, not a lossless edge FIFO. The local UART transports
coordinates into that model. A fresh guest has no populated media database;
the original startup-error notice can be dismissed to Home. Do not attribute
that notice to the database merely because the catalog is empty.

The silent mixer must accept sound-effect PLAY0x40046115, STOP0x6116 and
SYNC0x6117 without dereferencing an argument when its effect controller is
absent, matching the pinned GPL driver's early-return branches. STOP/SYNC are
argumentless requests. Rejecting SYNC previously terminated the original AudioC
caller. The bounded model test passes host sanitizers and Sony-libc ARM926;
it provides no sound, DSP or complete media startup.

- NW-X1000_V1_11.exe: 46849232 bytes; SHA-256
  25c8290dbac1065809f39332614491958ef7c93ce6e2e67e8cb5f815009a5a81.
- UPG: 47001096 bytes; SHA-256
  002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b.
- Japanese DES-equivalent key 466c8cd0, marker daefe603, KAS
  695c6b954088447c718f0873b8354c8a. This weak-container key search is not a break of
  a modern public-key signature scheme.
- Components: installation script, kernel, initrd, gzip rootfs. Check marker,
  count, lengths and exact reconstructed bytes, not just tool exit status.
- Kernel SHA-256:
  6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645.
- Rootfs gzip SHA-256:
  c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5.

Official source catalog:
https://oss.sony.net/Products/Linux/Audio/NW-X1050.html. It explicitly includes
Japanese X1050/X1060. Provenance belongs in sources; proprietary inputs stay local.

## Boot and application management

### Additional native choice pool experiment

The page composer emits a generated caller/guard profile. Private guard code
in runtime/platform/player/remote_page_guard.c verifies compiled page/metadata,
the Settings callback pointer, menu registration and unchanged Root layout,
with a separate view-helper fingerprint set. The optional host_hook dispatch
checks allowed caller, host readiness/reentry, GUI owner and image before its
private request adapter; errno is preserved. A weak unavailable adapter cannot
start a service. Normal getpid fallback and old non-page profiles remain intact.
tools/test_remote_page_guard_dispatch.py executes the composed page through
the actual PID shim/dispatch/guard and owner binding. Backend/thread/loader
identity and unavailable AudioC are fixtures; all code-span mutations, foreign
owner, unbound source, old toggle callsite and PID/errno cases pass. Evidence:
work/remote-page-guard-dispatch.log. The ordinary builder does not enable/link
this optional branch yet; actual adapter/observer/Wi-Fi entry wiring is pending.

The standalone native page composer now keeps Root/Pcs at156 and emits a
194-state AppMenu table in mapped padding. Current checked slots are code4d7000
and metadata4d8a00,576/920 bytes. It redirects only the Settings callback and
declared AppMenu table/count/initial-group words, with full byte-revert and
unchanged ELF header/segment checks. Original Root limits are required unchanged.
The constructor patches736e4 to count194 while preserving stack initial193;
reinit patches73698 count194 and736a4 initial193. Both table literals change.
tools/test_composed_remote_native_page.py executes both paths and verifies
group193/substate1, actual JP row lookup for Remote, entry/ready/cancel/ready,
stock selection delegation and refusal when the request bridge is unpaired.
Original startup initializer body, request and GUI boundaries are fixtures.
No paired DSO/view observer or firmware package is implied.

Current view prototype ties ownership to the original AppMenu context:
736c0 reads its pointer at6833fc, constructor736d0 uses static object683400,
and17ca18 returns group/substate. Begin requires0202 and active Settings97;
end requires Remote group194. Acknowledge/observe requires0202, active97,
all layer states0/3, no active29 or draw/slot work, and unchanged identity.
The unit test constructs the original context, uses the original state setter
for source/destination fixtures and dispatches4a0116 through the actual FSM.
Waiting0201, wrong destination, transitioning layers and stale epochs refuse
restore. Twenty observe/restore cycles pass with exact Root/view bytes. Evidence:
work/native-choice-view-menu-ready.log. Scene/layer/event ordering and code/
resource/owner qualification are fixtures; asynchronous hardware is unqualified.
No observer or ordinary-Wi-Fi entry guard is installed in production yet.

AppMenu has two registration paths.73694 reinitializes with count193 and initial
group193;736d0 constructs with count193 and stack initial group193. A future
count194 patch must preserve initial group193 in both paths. Table literals
are736bc and73714. Changing a shared count/initial value to194 would open the
new Remote module during startup. State-table growth does not solve or permit
Root view-array growth. Ordinary Wi-Fi category154 has no selection-table record
in the95-entry table at3f611c; do not assume every UI state needs a menu-list
record. Evidence: work/native-menu-context-getters.log and
work/native_remote_category_probe.py (read-only local inspection).

The private native_choice_view prototype now wraps reversible existing-control
properties with owner/epoch and completion checks. Original active lookup
0x2a824 scans four layer contexts at Root+0x2ff8+i*0x2e94 and compares their
control IDs via0x36224;0x36224 simply reads the first word. Poll restoration
also requires Root draw count+8 and slot flags to be zero, the same pool/view
identity and borrowed count/SID, and an explicit matching completion epoch.
These are prototype predicates, not physical ordering qualification.
tools/test_native_choice_view.py executes that original query and property
helpers; it covers active layers, queued drawing, wrong owners/epochs, changed
view/SID/code, and20 exact restore cycles with fixture state/acknowledgements.
No resources or original objects are freed by the helper.

One actual ready-post site is0x2d21c. It follows layer checks using0x365b4
(reads layer+0x2e2c), but has multiple branches including a layer-ID -1 path.
Do not infer global renderer quiescence from the event alone. The live
20106 request routes through GUI handler0x55544 in normal GUI substates;
startup state4 ignores it. Handler selects control29 path0x55830 or Settings97
path0x55a18 and returns substate7. Evidence:
work/native-view-completion-inspect.log and work/native-control-transition-inspect.log.
The completion source/epoch and close ordering are not yet connected to the
private view helper; its test acknowledgements remain explicitly supplied.

Resource13901 now has a local228-byte SWD derived from13900 with title7310
and existing On/Off255/256. Original10a544 resolves sid139-01, opens/maps/parses
it and returns exact UTF-16 text for local rows0/1 and title key0x400 in all11
wording contexts. Evidence: work/remote-choice-resource-check.log. File/stat/
mapping/libc and STX context remain fixtures; this does not qualify rendering.

Original73608 is not a parent-stack pop: it writes group56/substate4, queues
530009/5a0106 and changes the category; state56 initializer943d4 invokes playback
service4aa60 and posts430101. Do not bind it as Remote's Settings-back helper.
Cancel/apply-success now queue20106(control97,row11), set category2, return0201
and await4a0116 before interactive0202. The actual FSM replay confirms this
ready sequence. A separate event4a011b playback callback retains73608's stock
route; its playback-service leaf is modeled. HOME is distinct. Active Root view
removal and the safe point for restoring borrowed choice properties remain
unproven. Earlier category-pop fixture passes did not establish these semantics.

An alternative existing-view property experiment now executes original Pcs
allocation, getters/setters and binding on control29: choice count3->2->3 and
provider pointer restoration leave all view bytes and modeled Root bytes exact.
Original SID getter0x10e850 reads descriptor field26 live; a mapped-memory
13900->13901->13900 roundtrip works without extending Root arrays. Getter
0x10e858 instead reads field27 (value2), passed by original0x2abbc through
0x13be4's pointer array at context+0x5ec0. The pointer set at view+0xa8 by
0x10a1d4 is therefore a provider-context pointer, not the numeric SWD SID.
Do not substitute a resource ID as that pointer. See
tools/test_native_choice_reconfigure.py and work/native-choice-reconfigure.log.
This verifies reversible property mechanics only. SID13901 is an experiment,
not a verified loaded resource; active rendering, view ownership and close/
restore timing still need qualification before sharing an existing view.

Do not promote Pcs156 based on pool capacity: the original Root view-pointer
array starts+0x2b18 with156 eight-byte slots. Slot156 is+0x2ff8. Original code
0x2a9b4/0x2a9b8 constructs that same address as another stock object, then
calls0x36224; it is not spare pointer storage. Root registration0x2ac38 passes
156, with an initialization loop bounded by0x9b. Descriptor table4e692c also
has literals at0x2aaf0,0x2acd0,0x2d7ac, in addition to Pcs registration. A
relocated157-entry table and a pool pass alone do not extend Root storage or
all consumers. Evidence: work/remote-page-registration-refs.log and
work/remote-ui-views-inspect.log. Native-page prototype control156 is replay-only;
production needs a qualified dynamic/existing-view route or a complete audited
storage change. No unsafe count-only patch is included in a firmware builder.

UI states are separate: the original wrapper0x73694 registers193 descriptors
from pointer table0x3f55d8. Entry1 (state2) points0x41120c, the Settings module;
entry153 (state154/0x9a) points0x4052e4, the wireless confirmation module with
initializer0x88400 and confirm callback0x88494. Its descriptor references a
transition-byte table, callback table, event-index table and optional initializer
table. Adding Pcs control156 alone does not register a UI state or callback.
tools/inspect_native_settings_states.py inventories the pinned descriptors and
registration instructions. This is static evidence, not UI-state allocation or
navigation qualification. The injected Remote return0x0201 differs from the
stock unknown-row fallback0x0202; do not call these equivalent stay-on-list
results without replaying the original state engine.

The original FSM0x17c608 now reproduces the route loss: group2/substate2
selection event0x4a0111 followed by callback0201 enters group2/substate1;
navigation0x4a0101 and subsequent selection route to original ignore handlers
0x74510/0x7377c. Returning0202 keeps navigation and repeated selection active.
The source callback now returns0202, with its paired code digest and exact
composition identities updated after a one-byte callback delta check. The
complete host compiles at work/player-settings-substate-fix-20261105-1/build.json.
tools/test_remote_settings_state_transition.py --host-review ... also executes
the candidate's actual Remote callback through the original FSM, while supplying
row lookup/request results and intercepting the navigation leaf. This proves
event routing, not rendered navigation or a complete On/Off page. The legacy
callback still enqueues an action on selection; replace it with explicit page
open/query/apply/cancel behavior before calling this UI complete or shipping it
as the intended remote Settings solution. No UPG is generated for this step.

Original Pcs registration accepts a supplied157-record table and its existing
176-slot pool constructs an added two-choice descriptor while all original156
constructor records remain byte-identical in the ARM replay. The experiment
copies the table into a verified empty mapped RX span at0x4d8f00, appends a
clone of descriptor29 with counts/capacity2 and experimental resource90000,
and invokes original registration/allocation/constructor code. It does not
patch startup registration, load the new SWD, register state-machine callbacks,
or qualify return navigation. A new Pcs control ID is not automatically a new
UI state; those mappings must be traced separately. No ordinary firmware
builder includes this experiment. See tools/test_remote_native_page_pool.py
and work/remote-native-pool.log. The shared replay helper now takes explicit
table/count arguments while defaults remain the original156-record case.

### Homebrew regression boundary against retained earlier roots

One locally reproduced regression is the resource-free, bound-radio exit path:
host_prepare_bridge.c previously demanded an empty Sony pending-token list
before calling Sony prepare, even when the SDK owned no resources and radio
retirement succeeded. With a pre-existing native token, the ARM replay consumed
the request without entering0x112fc. Resource-free delegation now verifies
code/Root/owner identity, SDK emptiness and radio retirement without treating
Sony's own pending work as SDK ownership. Deferred radio completion rechecks
these identities and emptiness; reappearing SDK resources refuse continuation.
Owned SDK paths retain the original strict native snapshot/drain checks.
tools/test_player_prepare_dispatch.py --wireless --finalize-original covers
immediate delegation, radio-delayed delegation and resource reappearance.
The before failure is work/idle-sdk-native-token-before.log; the current result
is work/idle-sdk-native-token-after.log. Pending/native side effects and host
ownership remain fixtures; this reproduces a concrete bridge defect, not the
physical freeze. The full composed library builds at162,364 bytes, unchanged
in file size, under work/player-idle-native-token-fix-20261104-1/build.json.
No UPG has been generated or physically tested for this correction.

The retained candidate8/9/10 root archives and physically failed999846fd UPG
have byte-identical AppList.conf, including application0x30001 and the external
launcher command. Candidate9/10 and the failed payload both use mode1 at
0x4d61c0. The native name-query and switch-call words at0xb04f8,0xb0500 and
0xb0554 also match. This rules out a change to those particular bytes, not a
downstream application-switch failure. Candidate8 used mode0; do not generalize
the mode1 finding to all earlier candidates.

The failed package replaces the direct6,457,376-byte player entry with a
6,464-byte exec wrapper, relocates its single player payload, and adds the
162,364-byte preload library and27,376-byte remote supervisor. Five previously
direct calls to0x112fc at0x718e0,0x71aa4,0x71cd8,0x71e6c and0x71f5c now target
0x4d7fc0. GUI routing at0x10958, worker dispatch at0x3b9e4, activation confirmation
at0xb0624 and the main-loop anchor at0xff3c also change. These are distinct
regression boundaries; unchanged Home entry instructions do not qualify them.
Executable segments contain literal data as well as instructions.

Use tools/review_homebrew_regression.py with --earlier-root, --current-upg and
a new --output under work/. It reads artifacts only, validates the UPG container
and full gzip stream, reports file identities and decodes declared boundaries.
Current evidence is work/homebrew-working-current-comparison/candidate10-boundaries.json.
The user reports earlier Homebrew worked, but the exact retained candidate's
physical acceptance is not inferred from a package audit. External launcher
changes are a separate variable absent from root inventories. No full physical
freeze reproduction, fix, or firmware qualification follows from this inventory.

### Actual native wireless choice resource

On/Off control0x1d's original Pcs descriptor has resource field26 equal13900,
which resolves sid-139-00. It is not the parent WLAN page sid-100-00. Its
choice labels are local tid0/tid1; an added third row requires local tid2 on
sid139. Adding tid12 to parent sid100 leaves this row missing, matching the
physical third-choice000/@en report. Generic STX presence alone is insufficient.
The composer now supplies title, Wi-Fi, retained OFF and ESP-NOW mappings on
the actual page. Control0x1d's static fields21/22/32 (count/capacity/final count)
must all accommodate3, not just a runtime parameter count. Test original Pcs
record construction and the resource files emitted by the same build together.
This does not establish measured RF state or driver compatibility.

### Unbound command3 must not persist exit state

Before host_ready, the command3 dispatcher previously called
xw_player_host_note_native_exit, permanently setting native_exit_seen in the
managed service even though no SDK owner/service existed. Later binding does
not clear that flag; resources_idle, settings and session APIs then report
CLOSED. An exact pre-fix DSO test under Sony's loader observes the flag change
on a direct unbound command3 call. This establishes a state-poisoning defect,
not proof that the physical boot delivered that command before binding.

The corrected cold branch delegates stock and preserves errno without marking
SDK exit, matching cold commands6/7. Bound/owned exit processing is unchanged.
The optional --cold-exit-contract on test_player_cold_dso.py reads the private
flag using symbol-relative offsets from the exact DSO, and checks the command
does not mutate it. It does not execute original GUI startup or establish the
physical event order. Never reset the flag after an actual bound native exit
as a substitute for fixing the unbound call site.
The same exact-DSO test now binds a supplied initialized player through the
actual managed-service dispatch and queries its actual resource-idle API.
The pinned historical DSO refuses after the cold command; the fixed DSO reports
idle. Provider initialization and the real startup ordering remain fixtures/
unknown, respectively. This establishes the downstream API consequence without
claiming the physical freeze has been reproduced.

### Native exit continuation is separate from admission

Original command3 first executes readiness getter109a8(root,1), reading
Root+0x50. If zero,112fc returns without issuing any module preparation. Do not
replace that getter with an unconditional success in exit tests. Once ready,
nonzero module tokens are registered by original48a14; completion11250 removes
them through48a78. With two supplied tokens an unknown token leaves the table
unchanged, one completed token does not finalize, and only the last reaches
10ee4. Current ARM dispatch tests execute the getter and registration/removal
instructions; readiness values and module responses are fixtures and the
finalizer body is intercepted. They do not prove physical initialization,
module completion or process termination.

After a resource-free unbound-radio exit was delegated once, native_exit_seen
made the ordinary resource/admission query return CLOSED. A second command3
therefore missed the empty-SDK fallback and became HELD. The exact DSO test
reproduces first-return0/second-HELD with a supplied initialized player and no
radio authority. Original GUI repetition/ordering is not established by that
direct-call test.

The internal native_resources_idle query now checks owner, retained-exit state
and actual session/broker/worker/prepare resources without treating the mere
admission-closed flag as a resource. Only the existing no-radio-authority
command3 fallback uses it. Ordinary resources_idle, offers and generation
admission continue to reject native exit. Owned/draining/faulted resources and
deferred prepare are still refused; this grants no new session or RF lease.
Actual-DSO repeat and managed-service empty/live tests check both sides.

With an already-bound verified-OFF wireless authority, the first empty exit
also closes admission and retires a particular wireless epoch. Repeating the
full setup would fail quiesce on CLOSED or use a stale new epoch. The bridge
now remembers successful empty factory delegation and rechecks empty SDK
resources, owner/root, code identity and the same wireless retirement epoch
before allowing another original preparation call. RF refusal still holds;
owned/deferred SDK exits are not converted into this empty fallback. A host/
ARM test executes the real bridge and managed service with modeled Root/image
validation and OFF response; it proves the state-machine defect and same-epoch
handling, not physical shutdown timing or radio-off hardware evidence.

Automatic wireless bootstrap must also respect the managed player's lifetime.
wireless_auto now refuses original_exiting before image/boot observation or
authority construction. This includes the initial not-yet-bound managed owner;
that refusal is not latched as a failed bootstrap, so a later active owner tick
can initialize. An exiting player cannot acquire a new authority in a later
main-loop tick after an earlier empty-exit proof. Tests execute the real auto/
mode-policy code with supplied lifecycle and OFF observations; the existing
cross-process mode-channel tests still pass with an explicitly active owner.
This is a software lifetime rule, not proof of measured RF power or a live
occurrence of that race on the physical player.

### Proxy completion does not prove child entry

The current Home argument adapter uses APF mode1 (quit/relaunch). The legacy
check_home_parent.py switch-client path explicitly asserts mode0 and follows
command6/7 deactivation/reactivation, so it does not qualify the current native
exit path. test_current_home_switch_mode.py executes the current payload's
selector/default branch at0xb0510, adapter branch at0xb0518, argument adapter
and original client0x2681e8. It observes request header
[1060,0,1,6,55,0x30001,1,0]; the mode0 control differs at word6. Completed
name lookup and active APF client state are supplied, while locks/transport and
the success reply are modeled. Preflight, manager retirement, original GUI
startup and the physical switch remain outside the adapter-only case.
The optional --failed-firmware case now starts at0xb0464, reads the exact
installed-launcher ELF header through modeled file operations, then executes
original name-query construction and the original manager parser/lookup using
AppList bytes from the pinned failed de4a2330... package. It resolves0x30001
and constructs mode1 switch sequence1. APF active state and switch acceptance
remain supplied, so this is not a live manager or process-exit qualification.
The native bounded string copy0x339720 executes directly: its success return
is0, not the destination pointer returned by libc strcpy. Do not substitute
the latter in this parser/client path.

The actual hook's ordinary getpid also matches original libc in a worker made
with Sony LinuxThreads in the generic ARM guest. The test must run as a normal
child of a PID1 supervisor; adding pthread_create to the old PID1-only fixture
did not reach the comparison. This excludes a PID mismatch in that tested
loader/thread arrangement, not all possible original GUI/loader arrangements.

The original appproxy calls execvp at0x9638; on failure it obtains errno and
exits the fork child with that value at0x9644..0x964c. Its monitor at0x94e8
reaps children with waitpid(-1, status, WNOHANG). A normal proxy exit must not
be interpreted as a successful external executable or UI session.

Generic ARM system tests now cover the exact entry probe through the unchanged
proxy: a valid RAM mount-list/file fixture produces the marker; a real guest
proc mount list makes the storage check refuse without a marker; an omitted
child executable also leaves the trace unchanged. All three cases complete
registration/activation, return proxy status0 and remove proxy endpoints.
Only the first marker proves probe entry. These tests use a C manager peer,
not the original SpiderApp/manager switch or Sony hardware. In particular,
an unchanged physical trace plus a subsequently responsive menu cannot
distinguish pre-entry failure from probe validation refusal.

Evidence under work/: entry-probe-stock-proxy-20261104-3,
entry-probe-stock-proxy-refusal-20261104-2 and
entry-probe-stock-proxy-missing-20261104-1 (system-probe.json in each).

### Native Settings row count

The corrected display count is also checked against original selection-index
instructions: set category2 through0x74668, then read indices through0x74634.
The12-item composition yields original entries0..9 followed by Language
0xf80000 and Remote0xfd0000. This explicitly supplies category state and does
not establish real page activation, touch routing or scrolling.

The Settings selection table at0x3f611c and Pcs display descriptors are separate.
The original Home selection code derives the Settings item from the Home table,
then generates event0x20106 with page/control0x61 at0x73954. Pcs registers156
records of132 bytes at0x4e692c through0x10e754. Original getter0x10e53c indexes
that table; control0x61 (decimal97) has resource5000 (sid-050-00), count fields21
and32 equal10, and capacity field22 equal49. Control0x62 has resource5001 and
count11. Nearby records52/53 also contain11/10 but are not these Settings pages;
do not identify a descriptor by matching the numbers alone.

The failed de4a2330... player still constructs a ten-item Settings object even
though its selection table returns twelve entries. The faithful replay uses the
original Home selection, Pcs registration, descriptor reads, manager/pool init
(0x109524), pool allocation and object construction (0x10e558/0x1095e0). It does
not inject a count/control query result or replace the constructor. Japanese
classification is supplied, memcpy/memset and queue delivery are modeled; pixels,
full startup and live input remain outside this test.

The current PC composer changes only the JP descriptor's two4-byte fields at
0x4e9b84 and0x4e9bb0 to the enabled native list2 count. Capacity49, the other155
descriptors and all executable instructions remain unchanged. Reverting those
two fields reconstructs the input exactly. Across baseline, corrected and failed
player images,468 original object-construction cases reproduce10 for the failed
image and12 for the corrected image. This is native widget-data evidence, not a
complete QEMU GUI or physical menu acceptance.

The superseded176-byte adapter at0x4d8e00 redirected media-list constructors
0x12ae8/0x12c64. Its240 synthetic cases passed but did not establish that Settings
used that path. It is removed from current runtime source and builds; exact
sources are retained in ignored .tmp/superseded-settings-counter-20261104. Old
reports retain their old source hashes and must not be relabeled as fresh passes.

### Initial activation before SDK binding

For native command3 exit, no wireless authority plus a verified resource-free
SDK must also delegate the original exit. Otherwise wireless prepare_stop
returns DENIED and the bridge holds the native transition without completing
it. The idle/unbound regression in tools/test_player_prepare_dispatch.py
--wireless fails before correction and passes after it, executing all nine
original coordinator component boundaries and completion. The live/unbound
case remains blocked. Host ownership/resources and component effects are
modeled; this is not yet a physical Homebrew-entry fix acceptance.

The RF-enabled PID shim must delegate coordinator command7 while host_ready is
false, as it does cold command6. Initial native activation must not be marked
HANDLED before the SDK can own a handoff. The patched call at0x71cd8 executes
through the production shim in tools/test_player_host_anchor.py
--native-rf-gate --cold-routing-only: the unbound activation case fails before
the correction (zero original coordinator calls), then passes after it.
The initial activation path is a separate case from a real managed handoff's
command7; retain the latter's owner/state checks. These instruction fixtures do
not establish physical scheduling or prove the full database stall resolved.
tools/test_player_cold_dso.py additionally loads the exact reviewed complete
SDK DSO under Sony's original loader/libc in a generic QEMU kernel. The test
derives the hidden dispatcher offset from that exact ELF, invokes unbound
commands6/7, and checks stock-delegation return, errno and unchanged unbound
state. Ordinary getpid remains correct. This direct-dispatch test is separate
from original patched-callsite execution; neither is a full original GUI boot.
The optional --failed-firmware input is pinned to the physically failed first
cold-fix UPG. Its negative control expects command7 to return HANDLED and thus
records a reproduced defect, never a boot pass. Private UPG preparation requires
--cold-dso-review for the corrected exact library; negative-control evidence or
evidence for a different library is rejected before packaging.
Pinned instruction-order checks in tools/check_player_initial_loop_order.py
show the main loop dispatches messages at0xff28 (0x106c8) before reaching the
SDK-binding anchor at0xff3c. Root event class0x42 routes through0x10970,
0x10660 and0x71530 to the original Root dispatcher. Its activation action sets
command7 at0x71cd4 and calls the coordinator at0x71cd8. Thus a queued activation
can precede the first SDK binding; the real event contents/readiness and timing
of the reported stalled boot remain unobserved. This strengthens the ordering
rationale without claiming full physical reproduction.
The corrected private candidate d1d2b6c0... subsequently reached the original
main menu according to the user's NW-X1060 test on 2026-11-03. This validates
one startup attempt, not each individual correction's causal contribution or
ongoing sleep/USB/RF stability. Preserve the failed packages and negative-control
evidence; keep later hardware observations separate from offline build reports.

### Remote lifecycle: sleep notification boundaries

For the pinned Japanese 1.11 SpiderApp, the original APF registration assigns
slot3 to `0xecb8` and slot2 to `0xf090`. Original ARM receive/Root replay confirms
that a supplied slot3 notification in the tested active Root state posts
`0x420013` and selects coordinator command1. The zero-reason slot2 fixture posts
`0x420014` and selects command11. These are bounded branches, not a complete
sleep/USB classification: `0xf090` selects other events for request reasons,
subreasons and the original USB query, and can take a direct alternate path.

Do not treat `0xb17c4` as a verified system-manager sleep acknowledgement. Its
original callee is `0x263974`, which invokes media-layer routines and can abort
on their failure. Static decompilation does not establish a manager IPC ack.
The separate sysmgrd ARM check establishes that `0xb1f8` clears supplied pending
client IDs and only invokes the sleep path after the last pending client clears;
the application-to-manager transport between these boundaries remains unproved.
Likewise, Root completion `0x10ee4` for command11 posts `0x41000d` and an internal
`0x420607` event; that event alone does not prove RF retirement or suspend safety.

Reproduce the bounded checks with `tools/check_app_sleep_callbacks.py` and
`tools/check_sleep_prepare_ack.py`. `tools/check_sleep_completion_boundary.py`
also executes original actions `0x61500` and `0x619d8`: the first calls media
completion, obtains the environment and continues through `0xf5c8`; the second
updates an environment field, calls media completion and posts `0x42001a`.
Those external callees are intercepted in this check. Static inspection of
`0xf5c8` shows additional original state queries and queued events, not a proven
terminal manager acknowledgement. Native sleep/wake integration must preserve
the original reason-dependent paths and qualify the actual acknowledgement and
resume boundaries before enabling remote-session reentry. No hardware suspend,
USB ownership or automatic remote restart is qualified by these checks.

The Main completion dispatcher is now replayed for all ten supplied mode/state
pairs with both completion events (`tools/check_sleep_completion_dispatch.py`).
In mode3/state4, command11 completion `0x41000d` selects `0x618a4`, not
`0x61500`. That action calls media completion, reads the environment USB field,
then takes `0xb0268` for zero or `0xb0464` for nonzero. The corresponding
command1 completion `0x410006` selects `0x61c44`, which performs environment and
media restoration before `0xb03e8`. Mode2/state2 selects `0x6159c`/`0x6163c`.
These mode numbers are fixture identities, not independently named power states.

`0xb0268` calls the APF client `0x267d50(client,0)`; `0xb03e8` calls `0x267e28`.
Original ARM packet checks (`tools/check_sleep_client_packets.py`) establish
requests `[24,seq,appId,19,55,0]` and `[20,seq,appId,18,55]`, respectively.
Twelve cases cover client-state admission, successful/rejected manager replies,
sequence advancement and the second client's success-only field8 update to2.
Transport and locks are fixtures. This identifies the original application-side
IPC boundary; the manager opcode19/18 consumers and real suspend timing still
require correlation before composing wireless retirement into this path.

Manager-side correction: do not label the two producer paths as sleep and wake
from their GUI event names alone. Handler literals following `0xee98`, checked
against known opcode1 (`0xf75c`) and7 (`0xfb1c`), place opcode18 at `0xffb0`
and opcode19 at `0x1001c`. The former calls `0xb1f8(core,request.appId)`;
the latter calls `0xd860(core,request.word5)`. Original registration instructions
`0xecc0..0xed68` now execute and verify both installed table entries.
`tools/check_sleep_manager_packets.py` executes `0xffb0` with
two supplied pending application IDs: the first request clears only its own
pending entry, and the final request reaches the original S3 write path. The
reply retains opcode18. Application ID (word2) is distinct from peer endpoint55
(word4). Physical power, initial manager state and pending list remain fixtures.
The corresponding producer reply fixtures now preserve their actual opcode.
This contradicts an earlier inferred prepare19/wake18 interpretation; integration
must use verified manager semantics, not those provisional labels. The same
check executes three command19 rejection cases: manager states3/4 return0x1d03,
and state2 with parameter3 returns0x102, without a power write. Its admitted
request path is separately bounded below; this is not a restoration acknowledgement.
Three admitted command19 cases now execute the original handler/core transition
with parameters0/1/2 from supplied state2. They store the parameter at core+0x51a8,
set core state6, reset fields+0x51ac/+0x51b0 and reach `0xae68(core,0)`, then
reply successfully. Adapter, timer and list-notification helpers are intercepted;
no power write occurs in this bounded execution. `0xae68` enumerates application
IDs through `0x11858` and forwards selected IDs to `0xa4d8`, whose delivery path
still needs correlation. Do not call this admitted transition a wake completion
or assume it is the sleep preparation broadcast. Its state6 transition differs
from the state3 pending-client sleep-ack path.

The sleep preparation producer is now bounded separately in the same manager
check: registered command17 (`0xff48` -> `0xd6d8`) from supplied manager state1
executes original transition to state3, `0xa968` pending-list construction and
`0xa7c8` callback emission `[3,0,0]`. Two supplied app IDs/statuses produce pending
IDs1/2; callback transport, adapter and timer remain fixtures. This establishes
notification3 as sleep preparation at the manager callback boundary, not wake.
The separate original SpiderApp receive/Root replay maps notification3 to
command1 at callsite `0x719ec`; Main command1 completion selects `0x61c44` in
mode3/state4 and its `0xb03e8` wrapper produces command18. These checks identify
the prepare/ack direction across the two binaries, but do not run their actual
IPC together or qualify a wake/rearm boundary. The slot2/command11 path must not
be used as a substitute for this verified preparation route.

`tools/check_sleep_client_manager_chain.py` now connects original SpiderApp
client `0x267e28` to original sysmgrd handler `0xffb0` in two ARM emulators,
passing generated request/reply bytes rather than success reply fixtures.
The same manager retains two supplied pending IDs across both exchanges: the
first acknowledgement leaves state3 with no power request; the second reaches
S3/state4, and both clients consume the original manager's opcode18 replies.
In-memory transport, initial client/manager state, policy, locks and power remain
fixtures; full GUI preparation, native IPC and wake are not executed.

Remote software admission now rejects Root commands1 and11 in both the full
qualification and no-I/O fast state sample. Existing automatic supervision can
therefore request cooperative stop after observing those states and cannot start
a new remote there. Nineteen ARM readiness cases cover both refusals. This is
an admission correction only: it does not yet defer the original preparation
acknowledgement until radio retirement or qualify wake/rearm timing.

The callback replay additionally covers notification0 with supplied Main3/6,
Root2/3, zero flags and helper responses. Original slot0 `0xe68c` posts
`0x420017`; Root action `0x71bc0` checks the original tracker and chooses
command5 at `0x71c20`, not an assumed command2. Slot4 `0xea18` posts the already
known deactivation event `0x420015`. Neither callback has been qualified as a
complete wake/rearm boundary. Do not restore remote ownership from receipt of a
generic status notification or from these provisional mode labels.

Important active-player branch: notification3 with Main3/4 bypasses Root command1
and directly queues `0x410006`. The original receive/callback replay now covers
this branch with no coordinator call. Therefore the Root-command admission
correction alone cannot stop remote service before every sleep acknowledgement;
integration must also cover the shared Main acknowledgement boundary. Do not
claim that intercepting only callsite `0x719ec` handles normal playback sleep.

Original command5 completion emits `0x410001` (executed in
`check_sleep_completion_boundary.py`). Thirty Main dispatch cases now include
this event: Main3/6 selects the default action, while Main3/5 selects `0x61ca8`,
which again checks USB/policy before requesting manager19 or another application.
This does not establish a wake completion. Whether the original manager18 reply
returns before or after physical resume still requires the kernel/manager timing
contract; the in-memory client/manager chain does not supply that proof.

Never use return from the application's command18 call as a wake signal. The
retained-manager chain explicitly proves that a non-final acknowledgement
returns while other pending apps remain and no sleep has started. Separately,
`tools/check_kernel_sleep_wrapper.py` executes the shipped `mp200_pm_sleep`
wrapper (`0xc003a148`) for modes1/2/3 and success/-EAGAIN: the selected mode is
set during its synchronous call to `pm_suspend` and cleared after that call
returns, with the result preserved. `pm_suspend` itself is intercepted, so this
does not qualify physical wake or every proc-write path. Neither observation
authorizes automatic RF restart after an arbitrary acknowledgement reply.

`tools/check_manager_power_restore.py` executes original core event handler
`0xb80c` from supplied manager state4 with internal event `[2,1,0]`. It reaches
state1, calls original timer wrapper `0x13c54` (intercepted) and emits internal
callback `[2,1,0]`. Power-event production and callback transport remain fixtures.
The internal callback kind must not be equated with APF wire opcode2 without
executing the manager's notification conversion; this is not yet an application
restoration or remote rearm contract.

Notification conversion is now executed by
`tools/check_manager_notification_wire.py`: original observer `0xf298` creates
the broadcast queue envelope and original worker `0xf0fc` generates the20-byte
APF message. Three cases preserve the internal words exactly, including
`[2,1,0]` -> `[20,0,2,1,0]` and prepare `[3,0,0]` -> `[20,0,3,0,0]`.
Queue operations, one registry port and transport are fixtures. Thus the
state4 restoration case above reaches APF notification2 with reason1; it must
not be conflated with the reason0 slot2/command11 fixture. Original `0xf090`
routes reason1 to event `0x42001f`, whose complete recovery remains unqualified.

The application callback check now consumes the wire words generated by that
manager report (rather than independently inventing reason1). Original receive,
slot2 and Root action produce coordinator command15 at callsite `0x71e6c` from
supplied Root2/3. Forty Main dispatch cases include its completion event
`0x410010`: Main3/4 selects `0x61a1c`, Main2/2 selects `0x61540`, and other tested
states select the default action. Static inspection of `0x61a1c` shows media
completion, an additional queued event, environment updates and `0xf5c8` status
continuation. None of these observations qualifies radio rearm before those
subsequent events and component operations finish. The callback check requires
the locally regenerated manager notification report as an input.

The original LinuxThreads runtime reports distinct kernel getpid values in GUI
and pthread workers. Do not require their PIDs to match. Native wireless worker
binding validates the trusted GUI-created Unix socket's SO_PEERCRED identity and
records the actual worker PID/pthread_self separately, including fork-copy
refusal. Current descriptor-delivery ARM tests exercise this difference using
the producer's real GUI PID; synthetic modern-thread assumptions are insufficient.

Original category6/item0x600 is a cached byte read by void function0x37f5c,
not a status-returning NVP transaction. Values0/1 mean wireless enabled/disabled;
other values are not repaired by the new startup path. Read-only software-off
qualification runs on the existing Wi-Fi worker and is delivered to the GUI;
it must not be represented as physical power measurement or complete boot timing
qualification. See sdk/WIRELESS.md and tools/test_native_boot.py.

The original wlanapi.sh w8_proc_unload can hide later rmmod failures: its let
condition changes `$?` before err is saved. Original BusyBox ARM execution with
mocked commands confirms the first driver error propagates while later driver
errors can return success. Do not equate cnmgr_power_off success/state alone
with complete unload. Native retirement also checks the four module names and
requires a fresh exact-key DRAINING/FAILED observation; stable scan completion
and thread exit are not retirement evidence. See tools/test_stock_wlan_unload.py.

Read-only physical partition check during remote SDK development: root total
150306816 bytes, used 113545216, free 36761600, available 29003776 (reserved
blocks explain the difference). `/var` available 2895872, `/db` 200552448 and
`/ep0` 2904064 bytes. These are point-in-time values, not installation capacity
guarantees. Original BusyBox `df` can omit `/dev/root`; use the Device Info
verified legacy statfs adapter rather than inventing a modern statfs layout.
`tools/build_device_space_probe.py` builds a fixed-path, read-only diagnostic.
The temporary physical probe was executed on exposed user storage and removed
immediately; `/` remained ext2 read-only. Recheck before subsequent device work.

Normal boot enters /etc/init.d/gemini, /usr/local/bin/sysmgr.sh, then
sysmgrd -r /usr/local/bin/moc_repairer.sh /etc/AppList.conf. Special ID1 is
SpiderApp and ID2 Responder. Class 0x0001xxxx denotes resident services,
0x0002xxxx common apps, and **0x0003xxxx proxy-routed apps**.

```text
0x00030001 * /contents/HOMEBREW/launcher/app --native
```

The third token is both executable and lookup name; remaining tokens are arguments.
The special ID1 token must remain `SpiderApp`. Replacing it with a wrapper path
breaks the original name service: the native parser/lookup returns 0x111 for an
existing `SpiderApp` request even when ID1 exists under the new path. Preserving
the payload's PID, argv0 or kernel name cannot repair that configuration lookup.
The revised review layout keeps `/usr/local/bin/SpiderApp` as the wrapper and
relocates the single actual payload to `/usr/local/lib/x1000-player/SpiderApp`.
Both retain the SpiderApp basename. The original absolute `/usr/lib/omf` RPATH
is independent of the payload location. Native lookup and exact-wrapper loader
checks pass; complete physical cold startup remains unqualified. See
tools/test_player_startup_identity.py. Requests now include both the original
Responder capture and a freshly replayed SpiderApp registration-event query.
Original client instructions generate the latter after consuming manager
registration frames; transport and scheduling remain modeled. Both requests
fail with the renamed token and resolve ID1 with the preserved layout, in both
tested manager states (20 comparisons). This does not establish the full
database-completion timing or reproduce the physical stalled boot.
Continuing the original client after the failed lookup still emits 0x420011
and 0x420023 and returns to receive, matching the preserved-name run. See
tools/test_player_registration_identity.py. Do not infer a missing activation
notification or a proven startup fix from the name-service error alone.
Do not duplicate the executable in argv. The star follows manager credentials;
it does not create root permission. Root was observed through the current manager,
proxy, launcher and terminal configuration.

The original root child path sets GID, clears supplementary groups and sets UID
before exec. Known helpers: 0x15f14 and 0x15ed4. Modeled successful child paths do
not close inherited descriptors; manage ownership explicitly.

Home has conditional ten/nine-item maps. List modes and Home functional states
are different; numeric modes alone do not identify a model/region. APF slot4 /
0x420015 / command3 finalization differs from slot6 / 0x420024 / queued command6.
Command6 handoff can retain the process/root context and later return through
command7; it is not interchangeable with command3 finalization or proof of kernel
suspend. Original return replay registers an asynchronous GUI worker and emits
0x420034 with token0x207, then0x410009 and APF activation acknowledgement. Command6
also emits0x420034, with token0x206. Never rearm a drained wireless owner from the
shared event ID alone; validate lifecycle epoch, command/token and original
completion context. The current permanent-stop adapter is command3-only. Original bounded
activation replay records command6 coordinator caller0x71f5c and command7
caller0x71cd8. Existing patched sites0x718e0/0x71aa4 both pass command3;
command7 entry must not be treated as completed restoration.
Activation events 0x20303/0x580101 synchronize battery state, not display ownership.
The wireless component0x3b498 handles command6/7 by writing its internal
context+0x20 flag via0x3b404 and returning no pending token; this is not power-off
proof. Helper0x3b41c can post0x4c0005 when cached Wi-Fi is enabled and must not be
used as a shutdown helper. See test_stock_wireless_lifecycle.py and sdk/WIRELESS.md.
APF operation8 queries USB; operation7 is battery-related. Preserve original
asynchronous coordination rather than replacing it with a fixed delay.

## ABI and libc

Kernel: 2.6.10_dev-mp201, ARM926EJ-S/ARMv5TEJ, MontaVista GCC3.4.3 lineage.
Direct ARM syscalls require the verified OABI SWI immediate convention. Modern
r7+svc0 and ELF flags alone do not establish compatibility.

Native app builders use original libc startup and /lib/ld-linux.so.3. Pinned
SHA-256 inputs:

| File | SHA-256 |
| --- | --- |
| libc.so.6 | 5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812 |
| ld-linux.so.3 | 2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de |

They resolve to libc-2.3.3.so and ld-2.3.3.so. Stock pthread is LinuxThreads;
repeated task RSS is not independent physical memory.

Modern headers may redirect ioctl, fcntl, time and socket functions to absent
time64/C23 symbols. Use narrow existing bindings, not incompatible aliases.
runtime/store/target_abi.h and the stat bridge decode original 96-byte stat data;
do not give it a modern struct stat. Preserve legacy signal-return conventions.

## Storage, installation and recovery

Live root is mtdblock/1, ext2 read-only. mtdblock/2 is vfat read-write at /contents.
/var, /db and /ep0 are separate partitions; /tmp is RAM-backed. Root partition
capacity is established on this device, not as a universal installation guarantee.

The original updater formats root before unpacking. It has no automatic rollback
to the previous rootfs. Its visible-storage free-space check does not establish
expanded rootfs fit. Recovery remains a separate unresolved guarantee. Do not
infer safe flashing, bootloader commands, pads or shorts from software extraction.

An app must validate the mounted user device, directory identity, symlinks, free
space and USB ownership. A path or flock alone does not exclude a USB host.
Stock library databases can involve /db; audit destinations before refresh.

## Hardware and network boundaries

See HARDWARE.md for actual nodes and bindings. Opening a read-only device can
initialize hardware: radio open is one example. A GET name is not a side-effect
audit. Driver names do not independently identify precise silicon revisions.

Wi-Fi uses eth0, with original route/DNS configuration. /etc/resolv.conf points to
/tmp/resolv.conf. Original firewall policy is INPUT DROP, OUTPUT ACCEPT, with
loopback/ICMP and ESTABLISHED/RELATED exceptions. Only the inbound terminal needs
a temporary TCP2323 accept rule; outbound QQ HTTPS does not.

The observed 2008 device date matters for ordinary TLS and QQ timestamps. Terminal
pin validation is different from public CA/date validation; do not disable checks.

## Evidence discipline

Instruction replay can verify a wrapper with hardware/services still simulated.
QEMU user/system tests, local TLS servers, file readback and physical RF/audio
tests establish different things. Bind results to exact inputs and artifacts.
Superseded detailed notes live in ignored .tmp/history/docs; generated evidence
stays local. Active documentation records durable facts and outstanding questions.
