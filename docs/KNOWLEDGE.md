# NW-X1000 platform knowledge

Technical reference for Japanese NW-X1050/NW-X1060 on Sony 1.11. Use
[architecture](ARCHITECTURE.md) for ownership, [status](STATUS.md) for current
acceptance and the relevant app guide for user behavior. International NWZ-X
images and A910/A820 research are comparison inputs, not compatibility claims.

## Firmware format and identity

| Input | Size / SHA-256 |
| --- | --- |
| `NW-X1000_V1_11.exe` | 46,849,232 bytes; `25c8290dbac1065809f39332614491958ef7c93ce6e2e67e8cb5f815009a5a81` |
| Original UPG | 47,001,096 bytes; `002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b` |
| Kernel | `6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645` |
| Rootfs gzip | `c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5` |
| Original SpiderApp | `80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85` |

The UPG contains installation script, kernel, initrd and gzip rootfs components.
Japanese DES-equivalent key: `466c8cd0`; marker: `daefe603`; KAS:
`695c6b954088447c718f0873b8354c8a`. Rockbox's Sony format research/tools establish
the weak-container route; this is not a break of modern public-key signatures.
Validate marker, count, lengths, checksums and byte-exact reconstruction.

The source catalog at https://oss.sony.net/Products/Linux/Audio/NW-X1050.html
explicitly includes Japanese X1050/X1060. Proprietary binaries remain local;
pinned public provenance belongs under `sources/`.

## Linux and ABI

Kernel: `2.6.10_dev-mp201`. CPU: ARM926EJ-S/ARMv5TEJ. Original toolchain lineage:
MontaVista GCC 3.4.3. Direct syscalls require the verified OABI SWI immediate
convention. Modern r7 plus svc0 and compatible-looking ELF flags are insufficient.
Device extensions use C/C++ and necessary startup assembly; Python is PC-only.

| Original library | SHA-256 |
| --- | --- |
| `libc.so.6` -> libc-2.3.3.so | `5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812` |
| `ld-linux.so.3` -> ld-2.3.3.so | `2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de` |

Stock pthread uses LinuxThreads. Summing each task's RSS does not measure
independent physical allocations. Modern headers may redirect ioctl, fcntl,
time or sockets to absent time64/C23 symbols. Preserve the narrow libc, clock,
stat and signal bridges. `runtime/store/target_abi.h` and the stat adapter decode
original 96-byte stat data; do not pass a modern struct stat to old libc.

## Startup and process management

Sony's original manager, AppList, appproxy and SpiderApp own boot/application
transitions. The native Homebrew entry uses that path, then an external launcher
discovers apps on verified user storage. A source wrapper or an app executable
is not a replacement init system or an early recovery interface.

Keep the special AppList lookup token `SpiderApp`; a wrapper pathname is not an
equivalent registration. Stock LinuxThreads workers also have distinct kernel
PIDs. Exact identity, notification, acknowledgement and recovery bindings are
collected in [stock lifecycle reference](reference/STOCK_LIFECYCLE.md).

The private player integration executes controls only on the original owner
thread and after image/readiness checks. Do not dispatch native GUI work from a
radio or database worker. Original GUI publication helpers are not generic
cross-thread queues. Keep errno, registers, original return values and callback
completion rules intact.

Unbound/cold command 3 must delegate without persisting a CFW exit flag. Closing
admission after a real exit is different from owning outstanding resources.
Repeated native preparation may continue after admission is closed; using the
ordinary admission predicate as its continuation gate can consume the stock
transition indefinitely. Never reset a real exit flag to work around this.

An invalidated native continuation must not abandon an already authorized SDK
drain. `REVOKED_DONE` means SDK and independent cleanup completed without calling
that continuation; it is distinct from an uncertain cleanup fault. The generation
can be retired while admission stays faulted. Only a new original command3 with
fresh owner/code/Root/radio proof may delegate afterward. No old continuation,
exit flag reset or new service grant follows from this retirement result.

Original command 3 reads Root +0x50 through readiness getter 0x109a8. If zero,
coordinator 0x112fc does not prepare components. Nonzero tokens register through
0x48a14 and complete through 0x11250/0x48a78; only the final valid token reaches
finalization 0x10ee4. An unknown token must not remove another component's work.
Do not replace readiness with unconditional success in a test.

## Application handoff and sleep

The dev.32 Homebrew argument adapter at `0x4d61a0` requests APF switch mode1
(`mov r3,#1` at `0x4d61c0`). The original manager converts that request to
notification4; SpiderApp callback `0xea18` posts `0x420015`, which enters
command3 preparation. A command6-only preservation fix does not cover this entry.
Mode0 instead produces notification6, callback `0xeb9c`, event `0x420024` and
the queued command6 path in active Root modes. The explicit
`--warm-homebrew-analysis` build profile selects mode0 without changing the
original manager. The private `native-ipc-01` diagnostic includes that profile;
the user reports fast Homebrew entry/exit and uninterrupted Wi-Fi. The exact
image and remaining physical acceptance are recorded in [status](STATUS.md).

Mode0 also requires the original playback-state capture service to complete
before command6 preparation. Its mode1 states6/7 ignore the capture request.
The GUI-only guest reproduces this with both the composed entry and the
unmodified Sony browser; a visible Home screen alone is not media/lifecycle
initialization proof. The state matrix and exact path are documented in the
[native lifecycle reference](reference/STOCK_LIFECYCLE.md).

Application command 6, activation command 7 and sleep recovery are separate
contracts. The CFW application bridge stops player-dependent custom work before
forwarding Sony's original coordinator. It must return from the intercepted
action before invoking that coordinator on a later owner-loop tick.

The wireless component at 0x3b498 handles command 6 with 0x3b404(1), setting
context +0x20. Commands 7/21 clear the flag. These paths return token zero and
post no RF operation. An application switch therefore does not require native
Wi-Fi shutdown. CFW preserves the exact valid native Wi-Fi lease after custom
borrowers retire. Forcing disconnect here prevents Homebrew network apps from
using the existing connection.

Sleep preparation instead waits for qualified radio retirement and SDK drain
before native acknowledgement. Resume validates matching owner, epoch, native
state, successful original completion and sequence progression. Application and
sleep methods reject each other's transition kind. Screen blanking alone is
not proof of completed sleep or a reason to revoke an active remote session.

Command15 entry and completion are one-shot observations, separate from resource
admission. A qualified observation is retained while the original transition
flag is pending. Radio/SDK rearm still waits for that flag to clear and a fresh
stable owner, APF sequence and Root view. A subsequent exit cancels recovery;
clearing the exit indication later does not revive the old recovery attempt.

Once a qualified permanent exit stops SDK admission, loss of its native Root
view does not cancel the already-owned cleanup. Radio retirement continues on
the same epoch. After confirmed radio retirement, SDK readers, channels and
registered dependencies drain without retaining a native continuation. A radio
or close failure remains a fault; elapsed time is not retirement evidence.

Activation events 0x20303/0x580101 synchronize battery state, not display ownership.
APF operation 8 queries USB; operation 7 is battery-related. Preserve original
asynchronous coordination instead of substituting fixed delays.

## Original menu resources

Private C callbacks and object-layout constants live in
`runtime/platform/sony-settings/`; `bindings.h` names the Japanese 1.11 native
function addresses, controls, events, object fields and wording IDs. Composed
Remote states are derived beside their group in `native_page.h`. Choice-row
confirmation and question Yes/No results are distinct value domains. These bindings remain
hash-qualified implementation bindings. They do not provide a public GUI SDK
or replace live owner/resource checks. Remote policy stays in its consumer.

The pinned menu descriptor contains state stride at byte 0; action-row count at
halfword +2; callback count at +4; event-map count at +6; action/callback/event
pointers at +8/+12/+16. States are one-based: interactive state 2 uses action
column 1. Action values are zero-based callback indices. Do not add one.

The stock MAC menu group 155 has 23 callbacks. Selection-based pairing clones
the table into checked mapped padding, appends callback 23, raises its count to
24 and replaces only the relevant no-op result for event 0x4a012e/state 2.
Remote group 194 is separately registered; Root/Pcs capacity remains 156.
Question control 43 uses temporary SID13904 and restores14400; deletion uses
SID13903. These are private resource bindings, not general SDK APIs.

The original choice list reads the loaded SWD through wording accessor 0xec518.
Dialog helper 0x10a544 alone does not cover it. Bound-peer wording checks the exact
Remote SWD path and row; other calls execute the displaced original prologue.
Stored-binding IO/uncertainty must not be displayed as an absent peer.

The native Settings list's count, descriptor actions, callback routing and
wording allocation must agree. Enlarging a resource alone does not add a usable
menu entry. Builders validate mapped padding, overlapping edits, source hashes,
unchanged ELF headers and complete byte reversion.

Private addresses and instruction digests are implementation bindings. Keep them
in the reviewed adapters; app developers use typed SDK results instead.

## Player, media and artwork

PLAY/PAUSE enter AudioC request 0x440027 from qualified stable owner state. Direct
engine call 0x27d6a0 can leave the GUI actor unchanged. Reported playback state
requires both original GUI and CtrlInfo agreement. Next/previous use their
reviewed adapter. Admission is not completed playback; no automatic replay of an
uncertain side effect is allowed.

Native objects follow original reference ownership. Copy CtrlInfo/metadata/IDs,
release owned handles, and never retain borrowed native pointers in background
jobs. Queue order comes from the active Met sequence, not the catalog's row
order. Workers consume immutable copied queries and their own adopted clients.
Source replacement, sleep and USB must drain those clients before finalization.
Detailed ABI and source-submission ownership are in [player integration](sdk/PLAYER.md).

Native blob EOF 0x220f is successful end-of-image, translated from filesystem
EOF 0x401. Retain bytes returned with it; other read failures remain errors.
The guarded original PIC/APIC UTF-16 alignment fix and image transport are
separate from physical decoder/display acceptance; see [artwork](apps/REMOTE_ARTWORK.md).

## Radio and network

Start silicon/control research with [RF interfaces](RF_HARDWARE.md). The
[DTV HAL](reference/DTV_HAL.md) reference consolidates initialization, status,
transport and factory-path findings; [SD8686 bindings](reference/SD8686.md)
separate Linux, radio and ESP32 address spaces and their evidence. Factory SMPL
is a Boolean and the known physical mapping is acoustic memory; neither is an
unresolved raw-sample lead.

Wi-Fi uses `eth0` with stock route/DNS configuration. `/etc/resolv.conf` points
to `/tmp/resolv.conf`. The original firewall has INPUT DROP and OUTPUT ACCEPT,
with loopback/ICMP and established/related exceptions. WiFi Terminal temporarily
opens TCP2323; outbound QQ HTTPS needs no inbound rule.

ESP-NOW is a system transport capability independent of player control. Router
association is unnecessary, but peers must share the observed channel. Public
SDK modules, private shared-radio integration and installed capabilities have
different scopes; see [wireless lifecycle](sdk/WIRELESS.md).

A read-only device open can initialize hardware. A GET name, driver name or
connection-manager closed state is not a complete side-effect/silicon/power
audit. Use independent matching retirement evidence. Sony's unload script may
mask later rmmod failures; verify all radio modules are absent before claiming
software retirement. Measured standby/RF power remains a hardware test.

Shared endpoint drain must return STOPPING before executing manager RELEASE.
The Root wrapper uses that intervening owner turn to close receive membership
and restore any sleep state it changed, while the native manager lease is still
held. Draining and releasing in the same controller call skips this outer
cleanup. `test_shared_owner_retirement.py` executes the actual wrapper and full
controller to check that order, including failures and channel-change stops.

Preserve TLS hostname, CA and time checks. A wrong device clock affects ordinary
TLS and QQ timestamps. Terminal's explicit certificate pin is a different trust
mechanism, not permission to disable validation for other clients.

## USB connection interface

The JP1.11 `icx1087_usbconn.ko` and Sony GPL `icx1087_usbconn.h` define three
ioctls: GET_CSTAT (`0x80046701`), ALLOW_ACC (`0x40046702`) and PROHIBIT_ACC
(`0x40046703`). Ordinary connection states include 0 (disconnected),
4 (start-connect) and 1 (connected); 2 is firmware update and 3 is MTP.
The driver masks a connected status as disconnected while access is prohibited.
A zero status alone therefore does not establish user-volume ownership.

Connection changes coalesce into one pending poll notification. The original
poll callback consumes that notification and returns `POLLIN | POLLRDNORM`;
GET_CSTAT does not consume it. The optional [QEMU USB model](QEMU.md#usb-connection-observation)
checks these operations against the original ARM module. It models notifications,
not USB host enumeration, a gadget controller or physical ownership.

## Storage and installation

On the measured unit, live root is read-only ext2 on mtdblock/1; mtdblock/2 is the
read/write vfat user volume at `/contents`. `/var`, `/db` and `/ep0` are separate
partitions. `/tmp` is RAM-backed and is not application persistence.

The measured root partition is 148 MiB; filesystem total is146784 KiB, used
110884 KiB and ordinary available28324 KiB. These are a particular read-only
measurement, not a promise about another build/device. See
[system footprint](SYSTEM_FOOTPRINT.md). Cleaning user storage does not enlarge
root; UPG compressed size does not establish unpacked filesystem fit.

The original updater formats root before unpacking and has no automatic previous
rootfs rollback. A visible-user-space free-space check does not prove root fit.
No qualified early recovery interface is available. Do not infer bootloader
commands, test pads or shorts from software extraction.

Apps validate mounted device identity, directory type, symlinks, link counts,
space and USB ownership. A path or flock alone does not exclude a USB host.
Application state, accounts, music, artwork, logs and partials remain on verified
user storage with no system fallback. Audit actual database destinations before
any stock refresh: `/db` may be involved.

## QEMU model

The generic Versatile ARM926 guest runs the original Japanese Home/Settings UI
with explicit device adapters and touch. The complete original AppList matters:
its cnmgr_daemon unblocks the Home client's connection-manager FIFO. A minimal
AppList is not equivalent. Original manager/apps remain pinned.

The model supplies RAM configuration, unplugged USB, idle power, silent
mixer/beep and original framebuffer/touch ABI. It accepts SpiderApp's 5 MiB
framebuffer mapping and converts Sony RGB565 to the generic CLCD bitfields.
Cached component tables avoid per-pixel ARM software divisions. The clock bridge
uses the stock two-word time layout. Touch is a latest snapshot, not a lossless
edge FIFO. Silent effect STOP/SYNC requests are argumentless.

These adapters do not implement Sony RF, DSP/audio, battery, sleep or updater
hardware. A passing guest cannot reproduce or exclude every physical hang.
See [QEMU](QEMU.md) for exact model inputs and controls.

## Evidence

Bind results to exact source/artifact hashes. QEMU instructions, local IPC,
filesystem fixtures, volume readback and physical RF/audio establish different
facts. Source changes invalidate old build receipts; never relabel them as new
passes. Private evidence and superseded notes belong in ignored `.tmp/`; reusable
inputs/results belong in ignored `work/`. Current documentation records
contracts and findings rather than a sequence of development sessions.
