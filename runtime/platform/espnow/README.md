# X1000 ESP-NOW research

Goal: a native X1060 communication library interoperating with an original
ESP32-S3 Cardputer over actual ESP-NOW Action frames. TCP/UDP is only a
development control channel and never counts as ESP-NOW qualification.

The radio bridge and native library passed a bounded physical bidirectional
96-byte exchange with application ACKs and stock Wi-Fi restoration on one
X1060/Cardputer pair. See [exact identities and limits](VALIDATION.md).
Stock command 0x0098 is rejected in the inspected dispatcher. See
../../../docs/RF_HARDWARE.md for the internal Action handler and evidence limits.

## Storage contract

All player binaries, configuration and optional logs belong on verified
`/contents/HOMEBREW/` user storage. Never persist to root, `/var`, `/db`, `/ep0`
or `/tmp`. Receive queues and temporary packet buffers are bounded RAM objects.
The inventory helper writes only to stdout; the computer records its output.
Any future player persistence must use the existing mount/device identity,
symlink, capacity and USB ownership checks and fail closed without a fallback.
No diagnostic entry may flash, patch a driver, write registers or silently
change wireless mode/channel. Hardware experiments must be explicit.

## Peer

`cardputer/` builds with PlatformIO espressif32 6.12.0 / Arduino. It targets the
original Cardputer's ESP32-S3, not ADV. The current serial laboratory firmware
does not initialize the LCD or keyboard. Commands: `status`, `send`,
`channel 1..13`, `peer xx:xx:xx:xx:xx:xx`, `observe on/off`. Transmission is manual, unencrypted
and limited to a 32-byte marked probe. It creates no AP and has no IP fallback.
Receive callbacks enqueue bounded observations; formatting happens in loop().

Keep original flash backup and generated images in ignored work/. Do not publish
device backups, private network information or development identities.

## Current hardware evidence

The earlier Cardputer0.1.3 raw peer ran on the original model via COM17. Three marked
ESP-NOW probes produced Sony category255 automatic Action replies with matching
sequence/token fields. This proves an over-air path, not an X1060 app transport.
Read-only native inventory and fixed radio code reads also ran on X1060.
The shared xnow_frame.h codec is C/C++ framing only. Hardware integration of the
host/radio payload bridge was subsequently tested in the native exchange worker;
touchscreen app lifecycle integration remains incomplete.

tools/test_espnow_full_link.py now connects the actual shared C chat/mailbox
implementation to compiled radio Thumb execution and the shared C peer protocol.
It checks simultaneous96-byte messages (including UTF-8 fragment boundaries),
modeled drops/duplicates, clock wrap and absent-peer timeout. RF, RTOS helpers
and word-IO timing remain modeled; the native C side runs as a host shared
library, not as the Linux player app. This is stronger integration evidence than
isolated codecs, but it is not an over-air or driver-timing qualification.
The absent-peer case leaves a published mailbox request pending after timeout:
unconfirmed does not mean cancelled, and a later peer poll may transmit it.

Chat peer0.1.0-dev.2 is now installed on COM17; the original full flash backup
and known-running raw0.1.3 image are preserved under ignored work/. Esptool
verified the written application hash. A physical serial smoke test passed
96-byte submission, one-outstanding-message refusal, absent-peer unconfirmed
timeout, invalid-channel and oversized-line rejection, and discovery reset.
It remained unpaired and idle, with no increase in RX queue drops; MAC counters
are not application acknowledgements. A subsequent reboot returned it to the
clean waiting state. This is not native X1060 app-to-app or LCD visual acceptance.
The explicit PC test tools/test_cardputer_chat_live.py is separate from all
offline builds and writes only to a new ignored work/ directory.


## Radio prototype and candidate

`build_radio_bridge.py` compiles `radio_bridge.c` for the radio CPU, separate
from the Linux ABI. It produces an analysis ELF under work/espnow-radio-bridge.
It targets the fourth large packet block at c000a190..c000a8fc. This requires
the same image to reduce that pool from four to three blocks, split startup
zeroing around the reservation and change the management callback veneer.
Never load this payload into the stock four-block image at runtime.

tools/prepare_espnow_radio_candidate.py prepares a RADIO-only local candidate
and original fallback files under work/. It does not install, reload a driver,
create a system upgrade package or touch a player. The candidate's reduced
buffer capacity has only bounded exchange evidence; it has no throughput or soak
qualification. Matching reload/restoration passed the explicit lab test.
Compiled-code tests substitute RTOS helpers and do not prove radio operation.
The fixed32-byte mailboxes are an experimental poll-driven design.

The current420-byte bridge validates the full XNOW header and treats exact
PING0/token0/zero-body packets as TX clocks only, preserving unread DATA/ACK
snapshots. Ordinary probes and messages still publish RX. The candidate under
work/espnow-radio-candidate-poll-filter matches the current generated native
header; the earlier work/espnow-radio-candidate is preserved as historical input.
Use --candidate explicitly with tools/test_espnow_radio_candidate.py. Never pair
an older candidate with a newly built native code-identity guard.

## Native C interface

The local reusable ARM archive is built by build_library.py. See [Library
guide](LIBRARY.md). It emits libxnow.a, C/C++ public headers, a no-device example,
source/ABI/radio fingerprints and an experimental SDK ZIP under ignored
work/espnow-native-library/<VERSION>/. The chat app now links this archive.
Minimal and whole-archive ARM926/Sony-libc consumers pass without device calls;
C++ header/C-symbol linkage is host-tested, not ARM-C++ or RF qualification.
No Sony libraries, full firmware, private device data or ROMs are packaged.

Library0.1.0-dev.2 includes xnow_control.h/.c, connecting policy actions to the
original manager, guarded asynchronous jobs and native verifiers. It is an
owner-process backend, not a UI loop or a deployed service. Missing guards refuse
initialization. stop invalidates link access, waits for pending jobs to drain,
then restores; uncertain child/client ownership cannot be reported finished.
The application still does not activate this path. The earlier SDK0.1.0-dev.1
is preserved separately; public structs are not a stable binary ABI.

Library0.1.0-dev.3 fixes a false stock-verification rejection found on hardware.
The original11e0 routine reclaims low17304..18000, including startup scatter
inputs. These mutable boot bytes are now excluded; the stable276-byte code/pool
initializer/callback digest remains pinned to original input. The revised
--stock-verify, channel GET and pool GET passed on the player without SET.
The failed292-byte verifier and observations are preserved as evidence. No
custom-radio loading or native app exchange was tested at that stage. The later
0.1.0-dev.8 worker exercised these paths; see VALIDATION.md.

xnow_mailbox.h/.c provide portable send publication, radio queue status and
latest receive-snapshot operations over a qualified word-I/O adapter. They
perform no file writes, allocation, installation or raw address access.
The native adapter has bounded physical acceptance through the explicit lab
worker. No automatic touchscreen-app installer/lifecycle is qualified.

Send publication, radio queue acceptance and peer/application acknowledgement
are different results. Publication errors can be uncertain and must not trigger
automatic retransmission. A receive snapshot can be overwritten; the API reports
known missed snapshots and rejects torn reads. Callers serialize access.

Relevant offline checks:

- tools/test_xnow_frame.c and tools/test_xnow_mailbox.c: host/sanitizer fixtures.
- tools/test_xnow_chat_boundaries.c: busy queue timeout across clock wrap,
  uncertain publication without retry, ACK pressure and conflicting fragments.
- tools/test_xnow_mailbox_arm.py: ARM926 with pinned original libc, mock backend.
- tools/test_espnow_radio_bridge.py: actual compiled radio Thumb, mocked helpers.
- tools/test_espnow_radio_reservation.py: stock pool allocation/release instructions.
- tools/test_espnow_radio_candidate.py: candidate startup, reservation and callback.
- tools/test_espnow_channel_handler.py: original driver48-byte builder and radio
  command switch/GET; SET RF helpers substituted, pre-dispatch gates excluded.
- tools/test_xnow_channel.c and tools/test_xnow_channel_adapter.c: codec bounds,
  native session/candidate guards and readback uncertainty with mocked IO.
- tools/test_espnow_radio_admission.py: original8078 prologue/whitelists and12
  seeded-state cases; only response copy substituted.
- tools/test_espnow_driver_admission.py: relocated original Linux ioctl entry,
  sixteen seeded adapter-state combinations; stops before hostcmd execution.

## Session transaction policy

xnow_session.h/.c serialize the intended radio transaction for the future native
runner: preflight, acquire a stock manager client, inspect its public state,
explicitly disconnect if allowed, unload, load, wake and verify the candidate,
then perform original RF initialization and configure the channel. Stopping or
a partially failed mutation requests stock unload/load/wake/verification/RF-init
and reconnection before releasing the manager client.
The policy itself has no operating-system calls and is not yet wired into the
chat app or a driver loader. It does not qualify those platform operations.

Only public states3 (ready) and4 (connected) are currently admitted. A connected
session requires explicit disruption permission. Cold power-on and sleep/USB
handoff remain unimplemented. The executor must drain every outstanding worker
before reporting completion; cancellation acknowledgement is insufficient.
No timer may silently release ownership while a Sony call is still outstanding.
Restore failure retains the lease state and requires explicit recovery retry.
The runner must separately revalidate user-volume files, hardware identity and
USB ownership before mutation. No fallback system-directory writes are allowed.

tools/test_xnow_session.c injects failures and cancellation at every startup
stage, checks serialized completions, and injects failures at every restoration
stage. These are policy tests, not stock-daemon or hardware restoration tests.

xnow_loader_job.h/.c implement the load-action process adapter. They execute
only the original loader, sourced by /bin/sh, with fixed candidate or stock
firmware paths and an explicit clean environment. Inherited overrides such as
wlan_file, fw_dir and driver_dir cannot select another module or system path.
The adapter admits only an outstanding load/unload/wake/RF-init action with an acquired lease;
polling drains its child before returning a result. It does not kill an ongoing
module operation on a UI timeout. There is no public installation CLI and no
chat wiring yet. The mount/USB/IPC guards and full owner-process/runner
integration are still required before a usable session can start.

tools/test_xnow_loader_job.c runs real fork/wait with execve substituted and
checks fixed arguments, environment isolation and child completion. The
hash-bound original-loader replay in tools/test_espnow_stock_loader.py confirms
success, existing-module, two-retry success, ten radio failures and ten SDIO
failures. Its shell is host bash, not the player's shell/kernel. In particular,
an existing sd8xxx module can make the loader return0 after insmod failed: always
verify the actual loaded radio code/pool, not just exit status.

WAKE runs xnow_sd8686_wake in its child, avoiding a blocking ioctl in the UI
controller. It sends original private deepsleep0 with a128-byte buffer, then
queries deepsleep2 and requires the exact original off-space reply. The ioctl
handler can mask a failed SetDeepSleep result, so a zero syscall result is not
sufficient. The next action still verifies the candidate before configuration.
This only checks the driver's deep-sleep state, not every radio power-save mode.
Failure is uncertain and takes the session's original-image restoration path.
No production app invokes this path yet; the mount/USB guard and full runner
remain incomplete. tools/test_xnow_control_adapter_arm.py runs mocked IO tests
under ARM926 QEMU with pinned Sony libc, including wake success, retained sleep,
malformed query replies and session refusal. Host wrappers cover both fopen and
the modern32-bit-header fopen64 redirect; no actual radio ioctl is executed.

UNLOAD and RESTORE_UNLOAD execute original wlanapi.sh unload in a child with no
user-supplied arguments/environment. Original rootfs has no wlanapi.inc override.
This branch does not invoke stop/killall, initialize networking, write NVP or
create/clean command pipes in the seven replayed cases. It closes eth0 if up,
then removes sd8xxx, mp200_sdio, wlan_pm_register and wlan_pwr_ctrl in stock order.
The fixed PATH includes usr/local/bin because stock iwconfig is located there.

Original error bookkeeping can lose a later rmmod failure. After the script
child drains, the native adapter therefore reads /proc/modules and requires
all four exact names absent. A nonzero script result with all modules absent
also meets that postcondition; a zero result with a remaining module does not.
Tests cross both exit results with both postcondition results. This snapshot
does not prevent a Sony service from reloading modules afterward. Exclusive
manager/daemon ownership and live unload/restoration are still unqualified.

## Original RF initialization

Loading modules alone omits the original w8_proc_init setup. xnow_rf_init.h/.c
now run the same fixed native-tool commands in a worker child: nvp zr11/1,
iwpriv setregioncode, iwpriv tpccfg0, wlanconfig pa_cfg_ext_set from original
/etc/hostcmd.conf, and iwconfig txpower15. WAKE and code verification precede
these steps. Stock restoration also wakes/verifies/reinitializes before reconnect.
No tool command is assembled as shell text. The original NVP region table is
41/10/30/30/30/30/30/10; FF follows the stock41 fallback. Unexpected/oversized
NVP output fails before later commands, rather than guessing a region.

The PA label selects command007e with EnablePA0 (power adaptation, not a claim
to turn the physical amplifier off). The path provides no NVP-write operation
and avoids the full load script's conditional MAC-cache write. Each native
tool is waited/reaped and any failed stage stops later setup. Tool success is
not independent RF/calibration or proprietary-tool side-effect qualification.
The parent guard must validate the original tool/config hashes first; that
production guard is still incomplete. The app does not invoke this path yet.

Stock-script replay adds14 initialization cases. tools/test_xnow_rf_init.c
checks mapping, exact argv, each stage failure, bounded output and restoration
phase guards with exec substituted. tools/test_xnow_rf_init_arm.py repeats the
process/pipe/wait tests with pinned Sony libc under ARM926 QEMU; tool execution
remains substituted. No region, PA or power command has been issued on X1060.

## Original connection-manager client

xnow_manager.h/.c call original libcnmgr init/state/disconnect/prepare/connect/fin
from one owning controller process. Calls can block on original daemon replies;
they must never run on a UI thread. Only matching session actions are admitted,
with a mandatory original-RAM-IPC guard. The adapter retains its client through
radio operations and reconnect, requires public state3 after disconnect and4
after reconnecting with an opaque copy of the original current configuration,
then releases. A failed init/fin is uncertain:
no blind repeat is allowed. Process mismatch, reentry and unsolicited disconnect
are refused. This client is not an exclusive lease against other Sony clients.
Library 0.1.0-dev.5 provides xnow_manager_stock_ipc_guard: it checks the
original /tmp RAM mount and five existing FIFO endpoints without creating files.
It is not exclusive radio or USB ownership. App owner-process wiring remains
incomplete.

Library0.1.0-dev.4 captures the official1004-byte target-connect configuration
when INSPECT sees a connected session with explicit disconnect permission.
Capture failure prevents disconnect; its stock result cannot masquerade as
public state4. Reconnect supplies that unchanged RAM copy to cnmgr_connect,
using the original API's ordinary request7 path rather than NULL/request12;
vendor provider-specific branches remain inside that API. The buffer may contain
credentials: never log/serialize manager or controller objects. It is wiped
before fin, including uncertain-fin cases. Host and original-library/daemon FIFO
fixtures verify byte preservation. The configuration-query half passed on the
player with intact bounds and public state4 before/after. A subsequent explicit
stock-only rehearsal on the NW-X1060 completed one disconnect/current-config
reconnect: state4 -> state3 -> state4, connect result0, another state4 check after
ten seconds, fin0 and done0. A fresh authenticated Terminal command verified the
worker had exited, the stable stock fingerprint, channel8 and four free stock
pool blocks. The helper's SHA-256 was
6652356c8c4255c8d7aed7a103cfcf174334511d47ead24b0df1d15e6c7815c7.
Its bounded journal was on user storage; the opaque configuration stayed in RAM.
This qualifies one ordinary current-configuration reconnect, not driver reload,
custom radio restoration or an ESP-NOW payload exchange. Error4 also follows
original ERROR-set failures, not only
cancellation, so the old failed journal does not identify its cause by itself.

tools/test_xnow_manager.c checks API order, guards, failed preparation and
uncertain fin with substituted effects. tools/test_espnow_manager_lifecycle.py
executes original daemon handlers: IP-stop then WLAN-disconnected returns state3;
WLAN-connected then IP-ready returns state4. Internal daemon states2/8 differ
from those public states. tools/test_xnow_manager_stock_transport.py runs the
actual native adapter under ARM926 QEMU with unchanged Sony libcnmgr/libpthread,
real redirected PC FIFOs and original daemon instructions. Replies are delayed
until modeled events complete; the client remains retained until reconnect.
Radio actions are explicit placeholders and driver/AP effects are modeled.
This does not qualify physical radio reload or explain the earlier lost Terminal
connection. The successful physical rehearsal used the current-configuration
path; it did not repeat the earlier failed NULL/default-config path.

## Physical RF initialization preflight

Library 0.1.0-dev.7 adds the explicit
xnow_control_init_stock_rehearsal constructor. After capture and disconnect
(or inspection of an already disconnected state3), it enters the existing stock
restoration chain: unload, stock load, wake, stock verification, RF initialization,
current-config reconnect if originally connected, and release. It does not load
the candidate, open its mailbox, set a channel or enter chat READY. It retains
the same mandatory external guards and uncertain-worker/repair behavior.
Host tests cover connected/disconnected entry, refusal of an unauthorized
disconnect, verification failure and failure/retry at each of the four worker
stages. `tools/test_xnow_manager_stock_transport.py --stock-reload-rehearsal`
runs this constructor and controller with original Sony libraries, FIFO IO and
daemon instructions under ARM926 QEMU; module/RF operations and AP events remain
modeled. No physical driver reload is qualified by these tests.

Before driver reload testing, a read-only physical `nvp zr 11 1` returned the
original multi-line zone dump: ZONE 11, offset 00000, byte 00, a one-byte read
count and an ok footer. The region maps to 0x41. The live MD5 hashes of nvp,
iwpriv, iwconfig, wlanconfig and /etc/hostcmd.conf matched the extracted original
rootfs. Library 0.1.0-dev.6 now parses this complete bounded output instead of
the earlier synthetic four-token fixture. ARM tests cover the actual format,
all eight region indices, FF, malformed headers/counts/footers, extra data and
failure at each initialization stage. These tests substitute tool execution;
the physical check read the zone only and did not set radio parameters.

## Launcher cleanup boundary

The current launcher app_process.c sends SIGTERM, waits100 nominal20ms ticks,
then kills the unreaped app process group. The host-process test
tools/test_xnow_launcher_shutdown.py reproduces both a250ms cooperative cleanup
that completes and a5000ms cooperative cleanup killed after about2.1 seconds.
This is an observed launcher limit, not measured radio-restore timing.

Do not wire a blocking radio restore into chat shutdown and assume its stock
calls will finish inside that window. No global watchdog change, detached
radio-restoration bypass or automatic candidate activation has been installed.
A qualified shutdown-coordination design or separate controlled laboratory
entry is still required before enabling the session runner on the player.

The loader also requires a fresh caller guard before fork; a missing or failed
guard refuses to launch. The production mount/USB guard is not implemented yet.
xnow_file_check.h/.c supply its read-only file verification primitive: exact
size (bounded to1MiB), SHA-256, independently supplied device identity, regular
file/single-link checks, no symlink directory components, and fd/path identity
checks before and after reading. No directory or file is created. The guard
must call this with build-bound digests, not a manifest supplied by the device.
Passing a root-device identity would not prove user-volume placement; the mount
observer must establish the correct identity separately.

tools/test_xnow_file_check.c tests corruption, truncation/extension, wrong device,
symlink files/directories, hardlinks, FIFO and noncanonical paths. The ARM variant
tools/test_xnow_file_check_arm.py executes the same checks on PC temporary files
under ARM926 QEMU, using pinned Sony libc and the stock stat bridge. It does not
prove real USB ownership, unmount exclusion or absence of concurrent writers.
Checks are snapshots; the runner still needs exclusive lifecycle ownership and
revalidation at each destructive boundary, including original-image recovery.

## Stock-only physical reload lab

Build runtime/platform/espnow/build_stock_reload_lab.py to prepare the explicit
Terminal laboratory entry point stock_reload_lab.c. It pins the original rootfs
input, generates hash/size records for14 original files and five BusyBox links,
and refuses the optional wlanapi.inc override. --check verifies the read-only
root, files, stock radio fingerprint and existing RAM IPC. Mutation requires the
explicit --detach-stock-reload-lab --charger-confirmed arguments; the charger
condition is an operator statement, not USB hardware attestation. The detached
worker journals only bounded phase/status records on verified user storage.
Repair failures retain the manager client; SIGUSR1 requests an explicit retry.
Do not restart a worker just because its network observer times out.

The first physical stock-only attempt passed unload, stock load, wake and stock
verification, then stopped at RF initialization with worker result69. The user
restored connectivity through Sony's UI. No candidate image was loaded. A native
read-only region_read_lab.c probe reproduced the failure: nvp's104-byte stdout
omits the ok message present in the merged PTY transcript. Library0.1.0-dev.8
accepts the complete stdout dump with its exact read-count fields and successful
child exit; it also accepts the merged transcript. The corrected native pipe
probe passed on the player with region0x41. Full reload/reconnect qualification
still requires a new controlled test; the old retained worker must be accounted
for first. The original root inputs and live radio fingerprint remain matching.

Full ESP-NOW development now targets the complete requirements in
[the acceptance matrix](../../../docs/ESPNOW_FULL_STACK.md). New plaintext wire
codec and command-doorbell experiments are distinct from the old physical
chat baseline; no full-stack completion is claimed.
