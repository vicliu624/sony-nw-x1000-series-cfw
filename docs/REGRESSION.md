# Offline regression checks

Run checks from the checkout root using the prepared Linux/WSL environment.
They do not connect to a player, install apps, flash a controller or generate a
firmware update. Keep device acceptance separate from these results.

These aggregate groups require the full research checkout. In an extracted
source SDK, use the bundled `tools/test_sdk.py` and service-client checks; the
archive intentionally omits private firmware-integration fixtures.

The source-layout GUI entry/return check requires private reviewed inputs and
an explicit matching Home screenshot. Run `tools/test_stock_homebrew_system.py`
as described in [QEMU](QEMU.md). It is separate from the modeled component
checks: success requires the original manager to launch the synthetic child
and return to the rendered menu. It does not qualify the real launcher or RF.

```sh
.venv/bin/python tools/test_firmware_regressions.py
```

The runner executes independent checks sequentially and keeps every exit status
and log under `work/firmware-regressions/<run>/`. It continues after a failure so
one broken group does not hide another. The final result fails if any check
fails or if checked source changes during the run. A compilation warning is not
silently converted into a failed or successful hardware result.

## Groups

| Group | Coverage | Command |
| --- | --- | --- |
| `host` | Link negotiation, Core2 peer adapter, TX headers, guarded scalar/bulk IO, old-client HELLO compatibility, shared receive, media ownership, broker admission and IPC wakeups; no Sony inputs or network | `--suite host` |
| `lifecycle` | Native app handoff, policy/channel IPC, sleep preparation/recovery and explicit shutdown | `--suite lifecycle` |
| `sdk` | Callback runtime, individual native modules, C/C++ public clients, managed IPC and adoption audit | `--suite sdk` |
| `remote` | Original guarded player bindings, status/control, artwork scheduling/reader, receiver correlation and counter persistence | `--suite remote` |
| `integration` | Root/Core2 encrypted link with actual owner pipes; full service/factory/SDK process chains for shared/exclusive sleep and shared pairing | `--suite integration` |
| `layout` | Source layout, relative includes, Python parsing, English docs and links | `--suite layout` |
| `workers` | Media-client ownership, cleanup failures, validation workers and broker drain | `--suite workers` |
| `artifact` | Actual reviewed ELF owner/engine binding, paired library identity and native menu composition | `--suite artifact --host-review work/<review>/build.json` |

Repeat `--suite` to select several groups. `--output` accepts only a new directory
under `work/`; it never overwrites an earlier result. Test-specific reports keep
their own source hashes and validation limits. The aggregate source inventory
is additional provenance, not a replacement for those receipts.

`test_shared_owner_retirement.py` combines the actual Root stop wrapper and
full controller. It checks delayed drain, both native connection states,
channel-change stop, receive/sleep/release order and retained ownership after
cleanup failure. `--expect-skipped-cleanup` records the old premature RELEASE
defect and must not pass against corrected source. `test_remote_retirement_summary.py`
executes the actual summary writer and parent reader, including legacy and
truncated input. Neither test establishes physical USB recovery.

Each new aggregate retains `checked-source.zip` and its SHA-256 alongside the
report. It contains exactly the inventory's checked source/configuration bytes,
including uncommitted files, so a later edit cannot erase the tested version.
It is not a complete build environment or source SDK: original Sony inputs,
toolchains, generated libraries and hardware evidence are not included.

Root-inventory review and packaging share `compose_root_inventory`. The declared
tree includes implicit parent directories with their mode/ownership, preserves
replacement-file ownership, and rejects file or symlink ancestors. Final package
inventory must match that complete tree; new directories are not exempt from
review. The corresponding synthetic unit tests create no firmware or image.

Pushes and pull requests run the host subset in CI and retain this evidence.
The subset is excluded from the default full run because its cases already
belong to `remote`/`workers`. It does not replace ARM, SDK or integration groups.
Firmware packaging is a separate manual workflow option, disabled by default.

The artifact group consumes the explicit current host receipt and checks its
source and binary hashes. Its anchor case uses the fully composed player ELF
with the production core owner/provider/engine binding path; it does not rebuild
a simpler image and call that a composition pass. Loader identity and dependent
effects remain fixtures, and RF/native callbacks are outside that case. A GUI
diagnostic can independently observe the existing read-only binding exports;
neither check establishes native radio or hardware readiness.

Mode-write coverage runs the original ARM request/settings instructions and the
actual guarded native adapter. The service integration sends all five choices,
duplicates every wire request and requests the same mode again, checking that
each explicit intent runs once and produces a fresh authenticated observation.
The full supervisor profile checks the opt-in RAM-only `XWRUN003` delivery while
the persisted pairing record remains `XWRUN002`. Legacy HELLO compatibility
compiles the real seven-operation client from commit `161a3d5`; CI must retain
that Git history. These checks do not establish engine completion or hardware
persistence.

Radio-image checks are separate from the default groups. Build a fresh
`prepare_shared_wifi_image.py --rx-diagnostics --bulk-commands` review, then run
`test_espnow_full_radio.py <radio-build>`, `test_radio_bulk_command.py
--radio-review <radio-build>`, `test_radio_full_rx.py --radio-review
<radio-build>` and `test_radio_completion_hook.py --radio-review <radio-build>`
sequentially. The last two share a fixture build directory. Also run
`test_radio_command_capacity.py`: it executes original ingress instructions to
demonstrate why requests over 1,500 bytes overwrite a live event object. The
bulk guard checks count actual adapter calls but model the device; they are
not a physical throughput measurement.

## Native lifecycle cases

`test_native_environment.py` executes the private environment module on host
sanitizers and ARM926 with the original libc. Explicit filesystem/radio/crypto
models cover stock/candidate qualification, shared-root versus cold loading,
restoration without user storage, symlink/device checks, exact key reads,
fresh/resume separation and retained security callbacks. Logging failure after
counter reservation remains uncertain; it cannot undo or repeat the reservation.
These checks do not establish real mount ownership, cryptographic primitives or
FAT durability. The full owner/caller checks cover the composing entry separately.

Owner retirement checks run the actual shared-sleep restoration caller with
real observer datagrams and a retained cooperative owner gate. Host sanitizers
and original-libc ARM cover expired data, stable/draining/failed policies, stale
queued replies, replacement leases/descriptors, fork copies, timeouts and native
restore errors. Power effects and clock progression are fixtures. The separate
startup check retains the original data timeout and fresh-reply requirement;
cleanup permission never becomes data permission.

Startup checks also execute the Remote and pairing prepare callbacks after
modeled slow security/peer work. READY requires a new correlated parent reply;
queued old replies, stop, denial and query expiry cannot publish readiness.
The managed receive-prepare check executes both actual shared prepare branches:
discovery and encrypted operation must acquire the scoped interface membership;
nonshared profiles must not. Socket failure, peer/security failure, stop and
parent denial retain the appropriate cleanup state and cannot publish READY.
The separate filter check executes release before shared-sleep restoration and
lease release, including idempotence and close failure. These socket effects
are modeled; they do not establish physical encrypted-frame admission.
The full-owner stop-boundary profile uses actual pipes, gate, controller and
endpoint code. Callback stop must prevent later command/completion/receive
stages; encrypted cancellation can retire before configuration finishes, while
a callback error remains recorded. Native radio/driver effects are modeled.

Running-observation checks execute the actual owner-loop admission and step
prefix with real local datagrams and modeled slow work. A completed admitted
round needs a new parent reply before continuing. Queued old replies, policy
failure, replacement leases, stop, runtime errors and clock regression cannot
resume data. Fast rounds retain one existing clock sample per round and the
ordinary query rate; idle observation expiry remains unchanged. The modeled
duration is not a physical latency measurement.

The remote group includes the original in-process binding checks: CtrlInfo
clone/reference release, provider observation, GUI and engine requests, volume
and independent-process refusal. These execute the corresponding original ARM
instructions with explicit pool, mutex, IPC and hardware boundaries. They check
wrong-owner/code refusal, stable-session consistency, unchanged outputs on
failure and admitted versus uncertain commands. They do not establish audible
playback or physical remote operation. Each binding run keeps a new result
directory instead of overwriting its previous report and executable.
The flagless GUI check executes the complete state/request matrix. Its
`--engine-provider` and `--direct-only` profiles are narrower, mutually exclusive
subsets; neither reports a complete matrix. Unknown options and conflicting
profiles are refused before compilation, and an empty selection cannot pass.

The qualified input-wait test includes a transition with no SDK socket: it must
advance within the existing 200 ms owner-progress budget, preserve shorter
native waits and leave foreign callers untouched. The application bridge's
read-only progress hint is checked after real interception and after forwarding;
it must not remain active once its work is complete. These scheduling checks do
not establish native device retirement or physical elapsed-time guarantees.

Native wake cases set the original transition-pending flag at command15 entry
or completion. The qualified one-shot callback must be retained, duplicate
completion rejected, and radio rearm held until the flag clears and the native
view is stable. An intervening exit cancels recovery permanently for that epoch.
These cases execute original getter/acknowledgement instructions, with initial
state, SDK/radio responses and IPC modeled; physical wake remains separate.

Snapshot-dispatch coverage includes original mode1 states6/7, which ignore the
warm-switch capture request and emit no completion. Its constructor and ignored
return paths execute without a substitute callback. Accepted states stop at the
serializer entry. This contract prevents an unconditional mode0 byte patch from
being mistaken for a qualified application switch; see the
[native lifecycle](reference/STOCK_LIFECYCLE.md).

The production mode policy/channel test checks these distinct paths:

- Native Wi-Fi survives application handoff, with and without a custom borrow.
- A custom borrow must retire before application handoff completes.
- No disable/reconnect event is manufactured for an intact native connection.
- Sleep drains the same native lease and waits for its verified retirement.
- Application and sleep entry/resume methods reject the wrong transition kind.
- Explicit stop still drains and requests native shutdown.
- Stale epochs, lease reuse and foreign active consumers remain rejected.

`test_stock_wireless_lifecycle.py` separately executes original wireless callback
instructions. `test_player_handoff_bridge.py` executes the production application
bridge and original coordinator with supplied SDK/radio completion.
`test_sleep_native.py` exercises original state and recovery checks. These tests
cover different seams; none alone proves the whole physical transition.

Application cancellation cases change Root or guarded code during radio/SDK
waits and inside a stop callback. Cleanup must continue on its owner, while
forwarding and command7 rearm stay rejected even after the old view returns.
The `test_player_service_drain.py --host-wrapper --handoff-revocation` integration
case starts real broker readers and a generation-scoped retirement callback.
Host sanitizers and an ARM system guest with original LinuxThreads require the
readers, descriptors and callback to retire, preserving the borrowed Sony
backend. Native view and radio effects remain models.

The integration group also exercises five distinct shared-Wi-Fi remote sessions
around an actual C sleep gate: the custom borrow drains before modeled native
off evidence, acknowledgement occurs once, stale recovery is refused, and a
new native lease/remote generation restarts without accepting the old lease's
retirement. The exclusive sleep path and pairing with delayed readiness remain
separate cases. These execute real local IPC/processes with native state/RF
evidence modeled; they are not physical sleep/wake tests.

Exit cancellation cases revoke the native continuation during reader drain,
during independent retirement, while radio retirement is pending, during its
completion callback and when adopting an already started drain.
They require resource closure even if the original view later becomes valid,
while proving the revoked callback is never called. Failed close and dependency
paths retain fault handling. Drain-only cases reject unquiesced or unstarted
cleanup, preserve the original epoch on duplicate requests, and still poll the
independent dependency if SDK cleanup already finished. The full Remote factory
case follows production ordering: cooperative child retirement precedes SDK closure, and only confirmed
generation retirement releases its logical borrow.

A fresh native-exit retry case uses the actual host wrapper and RF-enabled
preparation bridge. After proved cleanup it rejects the wrong command, Root,
owner, code and radio proof, then allows a new qualified command3 to delegate.
Admission remains closed. Original code/radio views are fixtures here; the check
does not execute Sony's finalizer or establish physical USB recognition.

The `--host-wrapper --exit-after-sdk-drain` service-drain profile enters native
exit after real SDK readers have closed but an ordinary generation-scoped
retirement poll is still pending. The actual RF-enabled preparation bridge
must attach to that completed SDK drain and execute the separate native-epoch
dependency. Revocation during that dependency must finish cleanup, reject the
old continuation and permit only a later qualified exit to delegate. Native
views/radio completion remain models; no original finalizer or USB hardware
executes. Lower-level cases reject completed-looking drains with an error,
retained backend/player or open admission, and prevent duplicate closure.

The `--native-exit-forward` and `--native-exit-forward-fault` host-wrapper profiles
exercise the actual preparation bridge and SDK readers through its normal resume
callback. Only the coordinator call target is replaced by a test function; the
remaining bridge source is unchanged. The successful path must record delegation,
retain a read-only completed-resource proof and delegate a later original exit
without repeating the callback. SDK admission stays closed and foreign-thread
queries fail. A modeled coordinator error must retain fault handling and refuse
delegation. A reentrant request inside the coordinator call is held without
repeating the callback; later qualified requests use the completed proof.
These profiles do not execute the original finalizer or physical USB.

`test_remote_observation_chain.py` connects actual managed client/server IPC to
the service's sampling callbacks, sender, worker and authenticated receiver.
Live-channel BUSY/UNAVAILABLE replies produce unknown fields without ending the
session; unchanged unknown state emits no repeated status, and a later valid
observation restores it. Backend IO errors stop with a close receipt; transport
EOF closes the client and remains distinct from a live observation. Media/RF
effects and worker scheduling are models, while request deadlines use the
original libc monotonic clock. This does not qualify native GUI timing or RF.

The artwork-transfer profile generates a valid JPEG fixture and sends it through
the actual background reader, broker, per-READ cache binding, managed IPC,
remote service, authenticated message codec and controller image client. The
first modeled native read returns BUSY; demand after backoff must recover and
the assembled JPEG must match byte-for-byte. RF/native media values remain
modeled and no pixels are displayed on a physical Core2 by this check.

Service lifecycle checks also require independent image-cache bindings for two
READ grants, zero-epoch refusal and atomic output when a grant is revoked during
read. Client checks cover missing identity, late replies during a pause, bounded
cache restarts, local send refusal, monotonic read serials and paused-job expiry.

Worker ownership checks inject early callback refusal, a failed read followed by
close failure, a successful read followed by close failure, queued cancellation
failure and thread-start cleanup failure. The same five cases run with actual
Sony LinuxThreads in an isolated ARM guest using dynamically initialized opaque
pthread storage. Native media resources remain modeled. A close failure must
retain the client and prevent publication/drained status; adopted-client retries
must occur on the adopting worker. The group also checks audio/source validation
and normal broker cleanup using the shared task implementation.

Artwork reader cases isolate optional thumbnail type/read failures from a valid
full cover, including partial thumbnail data and original file-reader EOF.
Clone allocation and invalid-count failures must stop without fallback; a later
missing attribute cannot erase a prior I/O result. Async cases allow a fresh
zero-offset I/O demand after backoff while continuation and protocol failures
remain cached. No background retry thread is introduced. Optional local JPEG
codec checks require an explicit private image and local M5GFX sources and are
outside the default suite.

Broker checks exercise a pending queue close through the actual public player
client. Commands, polling, browsing, direct artwork and provider attachment must
be refused while outputs and original playback state remain untouched. A fresh
binding may resume work only after cleanup completes; the borrowed original
player remains open throughout.

The remote group reproduces a dropped state update followed by an idempotent
command and checks one explicit refresh with one hour of idle silence. Its
combined control/artwork case completes an 85,474-byte authenticated transfer
after an accepted-but-unconfirmed control goal expires. Command timeout, peer
response and observed playback are checked independently.

Worker checks request stop from the sender, library reader, pre-sample producer,
snapshot reader and cover producer. Direct requests and cooperative flags must
block every later producer while close remains pending. Reentry stays refused;
the first accepted reason and a late producer error are retained independently.
SDK/radio methods in this ordering fixture are modeled; separate integration
profiles run the actual service and authenticated sender.

Owner-wait checks use actual select/pipe readiness on the host and with Sony
libc under ARM. The original-only baseline leaves an SDK request pending during
a 60-second wait. The adapter must wake for reads and reply writes, retain native
ready counts/bits, ignore duplicates/out-of-range FDs and preserve errors.
The ARM callsite test executes the wrapper and original input-reader instructions;
thread/image/caller/reentry mismatches delegate unchanged. A separate original
loader/preload test verifies `select` binding and `__select` delegation with real
foreign I/O. These are distinct seams, not full GUI/RF qualification.

The real managed-host drain profile fills an actual socket send buffer, queues
another request and verifies write-only interest while the reply is blocked.
After draining the peer, it requires read interest again and no descriptors
after service close. This runs on host threads and original LinuxThreads in the
isolated ARM guest. Shared-factory checks additionally validate the live mode
observer descriptor/interest throughout activation, transfer and retirement.

## SDK checks

`test_sdk_services.py` links every native service module independently, then
builds an external custom-main service consumer. Aggregate linking alone can hide
a module's missing dependencies. `audit_sdk_adoption.py` verifies maintained
consumers use public service imports and dependency contracts. Its optional
`--check-logic` mode is for an unchanged SDK migration against pinned baselines;
later app features cannot be declared byte-equivalent to those old baselines.
Do not rewrite a baseline to make intentional changes appear unchanged.

The repository catalog check keeps the Settings-managed remote consumer out of
foreground app discovery and preserves every public release app. SDK creation
must refuse its existing source directory instead of installing a template there.
These checks also run in the ordinary CI unit-test discovery step.

The SDK group also runs the managed player example against a separate sanitized
host with the ARM client using Sony's loader/libc. Each of the six CLI controls
must send exactly one matching operation/value. Snapshot, watch, all four media
views, eleven argument refusals and confirmed session close are separate checks.
This is a modeled service contract, not an installed-player or RF acceptance.

`test_sdk_app_equivalence.py` is a separate clean-CI check. It temporarily
substitutes baseline source and refuses a dirty local checkout. Do not bypass
that guard to run it in an active development tree.

For source archive qualification, build a fresh local SDK archive with
`tools/package_sdk.py` and pass it to `tools/test_sdk_bundle.py`. This extracts a
clean SDK and prepares its own pinned libraries. Reusing an old `work/` directory
does not establish source-only reproducibility. An SDK archive is not a firmware
update and supplies no device authority.

## Artifact-dependent checks

Some checks require an explicit immutable build receipt. For example,
`test_shared_wifi_auto_off.py --host-review <build.json>` executes a specific
analysis library's deferred native confirmation. It does not check the current
source merely because its input receipt is recent. These checks are separate
from the default source-only groups and must report their input hashes. Run
the artifact group explicitly with:

```sh
.venv/bin/python tools/test_firmware_regressions.py --suite artifact --host-review work/example/build.json
```

Never relabel an old pass after editing source, claim QEMU as RF qualification,
or hide a required input error as a skipped success.

Managed owner/service artifacts require current child build receipts as well as
the supervisor's identity. A current parent cannot hide stale child source.
Root-overlay receipts retain those transitive inputs, so later source edits
invalidate the overlay instead of silently packaging an older background worker.
Mutable configuration is data and is not treated as a code build receipt.

The integration group includes
`test_remote_supervisor.py --automatic-factory --owner-view-forward --shared-wifi --native-exit-bridge`.
This connects the actual native-exit interceptor and owner tick to the Settings
factory, supervisor/service processes, SDK session drain and wireless policy.
It requires custom children/readers and the shared borrow to retire, then holds
an explicit native OFF result back for additional owner turns. The original
coordinator is permitted exactly once only after that result; subsequent native
preparation remains delegated while new SDK requests remain closed. Native
Root/image checks, radio OFF and the final coordinator are explicit fixtures.
The test does not execute original finalization or a physical USB driver.

`--native-owner-wait` extends that profile with the actual native bootstrap,
SCM_RIGHTS offer, original-LinuxThreads worker, permission query, TLS sealing and
retirement-notice IPC. A condition gate releases the initial worker query after
the GUI publisher step, immediately before a one-second native-style select.
The query must wake that wait before its 200 ms deadline. A separate gate holds
the sealed retirement notice until another wait starts, which must report the
actual notice descriptor ready. The adapter exposes no fabricated native input.
Only boot/RF state, queue scheduling, Root checks and the final coordinator remain
fixtures. Host instruction checks additionally cover native query, reply-write
and notice interests through the qualified select wrapper.

`--application-handoff` adds the actual command6/7 bridge to this process chain.
It closes the Remote generation and SDK readers, preserves the exact original
Wi-Fi lease, supplies a matching APF return and confirms a fresh worker query
under that same lease. A new Remote generation must then start and retire through
the normal permanent-exit path. The test uses modeled Root/APF memory and replaces
only the native client getter/coordinator call targets; it does not execute the
original playback-state capture, display/input release or appproxy target. This
checks the C handoff contract without qualifying complete Homebrew entry/return.

`measure_layout_ext2.py` separately checks the complete root allocation in local
ordinary files, using matching immutable capacity/layout receipts. Its input
validation, superblock accounting and inode/symlink verification have unit tests.
It does not belong to device tests and cannot qualify installation. The model
uses dense regular-file blocks, counts filesystem overhead and excludes reserved
blocks from its reported ordinary margin; see [system footprint](SYSTEM_FOOTPRINT.md).

## Hardware acceptance

The physical acceptance list is in [status](STATUS.md). It includes cold start,
ordinary Wi-Fi continuity into Homebrew, repeated HOME return, actual remote
controls, five play modes, cover display, screen-off/sleep and USB ownership.
These need a deliberately selected, reviewed composition. Do not ask users to
flash every passing component check as a new experimental update.
