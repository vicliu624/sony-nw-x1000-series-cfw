# Stock application and sleep bindings

These bindings apply to the Japanese 1.11 SpiderApp, sysmgrd and kernel hashes
in [platform knowledge](../KNOWLEDGE.md). Numeric states are original values,
not names for unqualified physical power states.

## Boot identity

Startup follows `/etc/init.d/gemini`, `/usr/local/bin/sysmgr.sh`, then
`sysmgrd -r /usr/local/bin/moc_repairer.sh /etc/AppList.conf`.
Special ID 1 is SpiderApp; ID 2 is Responder. Classes `0x0001xxxx`, `0x0002xxxx`
and `0x0003xxxx` mean resident service, common app and proxy-routed app.

The third AppList token is both executable and lookup name; following tokens
are arguments. ID 1 must retain token `SpiderApp`. A wrapper pathname breaks
lookup with result `0x111`; preserving PID/argv0/kernel name cannot repair it.
The wrapped profile keeps `/usr/local/bin/SpiderApp` as the wrapper and one
payload at `/usr/local/lib/x1000-player/SpiderApp`. Both basenames stay SpiderApp;
original absolute RPATH `/usr/lib/omf` is independent of relocation.

Stock LinuxThreads gives GUI and pthread workers distinct kernel getpid values.
Worker binding checks the trusted GUI-created socket's `SO_PEERCRED` and records
the actual worker identity. It cannot assume modern same-PID threads or let a
forked copy use another process's ownership record.

## Preparation and acknowledgement

### Application switch and playback-state capture

The mode0 path is not a direct call to command6 preparation. APF notification6
invokes `0xeb9c`, which posts `0x420024`. Active Root actions set command6 and
post `0x430113` to the playback-state capture service. Its wrapper `0x6df2c`
dispatches the object at `0x683328`, through descriptor `0x3f4388`.

In mode1, states1..5 select callback `0x6ed0c`: it serializes playback state and
posts `0x420032`. Root continuation `0x71f00` can then reach coordinator
`0x112fc`. States6 and7 instead select the original no-op `0x6df6c`; they return
without a `0x420032` completion. These numeric states have not been assigned
hardware readiness names. A valid object pointer and a visible Home screen
are insufficient to establish that this capture request will complete.

`tools/test_native_snapshot_dispatch.py` executes the original constructor and
receiver with all seven state fixtures. States6/7 execute their real no-op and
FSM return. States1..5 stop at the serializer callback; this check does not
execute media work, IPC or a complete switch. The full source-layout guest
must independently demonstrate capture completion, native preparation and
target launch. Never force a state byte or manufacture completion to qualify
that path.

### Sleep preparation

| Original path | Meaning |
| --- | --- |
| APF slot 3 -> `0xecb8` | Sleep preparation |
| APF slot 2 -> `0xf090` | Reason-dependent; reasons 0 and 1 differ |
| Root callsite `0x719ec` | Notification 3 can request coordinator command 1 |
| Main 3/4 notification 3 | Can queue `0x410006` directly, bypassing command 1 |
| Main command 1 completion -> `0x61c44` | Media/environment work, then `0xb03e8` |
| `0xb03e8` -> client `0x267e28` | Manager command 18 acknowledgement |
| `0xb0268` -> client `0x267d50(client,0)` | Command 19 transition; not wake completion |

Manager command 17 (`0xff48` -> `0xd6d8`) moves supplied state 1 to 3, builds
pending apps through `0xa968` and emits internal callback `[3,0,0]`. Original
notification conversion yields APF `[20,0,3,0,0]`. Command 18 uses a 20-byte
request; command 19 uses 24 bytes. Preserve original sequence/header/client ID
construction rather than copying numeric fixture identities.

Manager handler `0xffb0` processes command 18. Helper `0xb1f8` clears the matching
pending client; sleep is requested only after the final client clears. A
non-final acknowledgement returns before sleep starts. `0xb17c4` is a media
call through `0x263974`, not that acknowledgement. Root command 11 completion
also does not establish radio retirement. Intercepting only Root command 1
misses the direct Main branch.

## Original finalization and NCAN

Command3 finalization passes through `0x10ee4` and `0x10d80` into GctlSys
finalization at `0xed98` (also reached through its thunk). Stop helper `0x32d8f8`
changes the GctlSys state from 2 to 3, signals its condition event, requests
NCAN break through `0x32bf7c` and joins the worker via `0x3375e0`.
Worker entry is `0x32c8bc`; its thread handle is stored at `0xe17408`.

The worker's NCAN wait is ioctl `0xc0046308`. Its failure path retries before
checking the stopping state. Break ioctl `0x6309` supplies the successful wait
result needed to inspect that state and return. The pinned original module
uses event word `0x200`; internal Digipod/non-Digipod branches differ in how an
earlier break is retained or cleared. An idle test model must state which
ordering it supplies. This is a driver event, not an application acknowledgement.

`test_stock_ncan_wait.py` executes the original ioctl instructions, then checks
the C model with host sanitizers and actual original LinuxThreads in a generic
ARM system guest. IRQ/sensor state, locks and scheduling are fixtures. In the
full GUI model, this permits actual original Responder entry; missing
`/dev/mgscsi` then prevents its setup. RF, an active remote generation and
physical USB ownership remain unqualified.

## Recovery

Manager handler `0xb80c`, from supplied state 4 and event `[2,1,0]`, returns to
state 1 and emits the callback. Observer `0xf298` and worker `0xf0fc` preserve it
in APF `[20,0,2,1,0]`: notification 2/reason 1, not the reason-0 command-11 path.
SpiderApp posts `0x42001f`, then coordinator command 15 at `0x71e6c`. Completion
`0x410010` selects Main `0x61a1c` in 3/4 or `0x61540` in 2/2. Radio rearm requires
successful original completion and the later stable Main/client/sequence view.

The kernel `mp200_pm_sleep` wrapper `0xc003a148` sets its mode during synchronous
`pm_suspend` and clears it after return, preserving the result. Neither this
wrapper nor a userspace command-18 return independently proves physical wake.

## CFW and verification

### Original input wait

Input reader `0xe1aa0` calls `select` at `0xe1b18`, returning to `0xe1b1c`.
The guarded eight bytes are `77b1fceb581095e5`, SHA-256
`bab36b7e53f5b328c624d2ca62a902e5aa657835aeae2d506e8933081c40f190`.
Its original descriptor set is 128 bytes; timeval contains two signed 32-bit
fields. The pinned libc exports `select` and `__select` at the same ELF address
`0xa72b0`; this is not a modern time64 interface.

The private factory profile extends only this owner-thread read-only call with
eligible managed/mode IPC read or write interests. This includes the native
wireless publisher's query/reply socket and its separate bootstrap/retirement
notice socket. Both must wake the same GUI pump: native worker queries have a
200 ms deadline, and a long input-only wait can expire otherwise valid ownership.
The descriptor query grants no new operation and remains available for cleanup
after admission closes. `owner_wait.c` contains the
bounded mask/return-value adaptation; `host_hook.c` qualifies the native boundary.
Only original descriptor readiness is visible to Sony's callbacks. SDK-only
readiness permits the existing main-loop pump to run. Queued local Settings
intents receive one immediate owner turn. A pending application, permanent-exit,
sleep or SDK-cleanup transition bounds a longer qualified wait to 200 ms even
before an IPC descriptor exists; shorter native waits remain unchanged. This
uses a local timeval and does not modify Sony's global policy value. Idle waits
without such work pass through. Actual system suspend remains separate.

The GUI wait has these private sources. Readiness lets the existing owner pump
run; it transfers neither descriptor ownership nor a service/hardware grant.

| Source | Adapter | Wait interest and lifetime |
| --- | --- | --- |
| Managed player session | `host_managed_service.c` | READ for a request, WRITE for a queued reply; only a bound, non-closing channel in ACTIVE/STOPPING |
| Remote's mode observation | `remote_auto.c` | READ or pending WRITE on the factory's valid owner view, including cleanup after new work is refused |
| Pairing-store result | `remote_auto.c` | READ while the current GUI-owned child/result reader exists; the job validates identity before consuming it |
| Native wireless permission query | `wireless_host.c` | READ or pending WRITE while the native publisher's issued channel remains bound and healthy |
| Native boot/retirement notice | `native_bootstrap.c` through `wireless_host.c` | READ on the original GUI's bootstrap datagram; it also covers boot before authority binding and retirement after the worker seals its query channel |

The optional inherited descriptor offer in `host_inherited.c` is a single
owner-dispatch action followed by local close, not a maintained listening socket.
The normal system wrapper removes its one-shot authorization environment before
starting Sony. `startup_delivery.c` belongs to a separate explicit validation
profile and completes its bounded handshake before the player exec. Neither is
an additional ordinary GUI request reader.

Child/process retirement without a readable result still needs bounded owner
progress. Its transition scheduling hint is separate from the channels above.
New asynchronous integrations must supply the correct current READ/WRITE interest
and remove it before owner-side close; shortening a global input timeout or
reopening SDK admission is not a substitute for that integration.

`test_owner_wait.py`, `test_owner_wait_anchor.py` and `test_owner_wait_loader.py`
cover real IPC, original input instructions and original loader symbol binding.
The native input case reaches its original return with zero key flags on an
SDK-only wake. RF, actual screen-off scheduling and Sony-kernel suspend are not
qualified by those checks.

### Sleep integration

`sleep_native.c` checks acknowledgement callsites `0x614f0`, `0x61648`, `0x61940`
and `0x61c5c`, exact pre/post states and APF sequence. It delays acknowledgement
for custom drain. Recovery must finish before the matching sleep epoch reopens.
Entry/completion observers retain qualified command15 notifications even when
the original transition-pending flag is set. That flag gates actual rearm, not
observation; otherwise a transient busy value can lose a notification that Sony
does not repeat. Stable Main/APF/Root/sequence validation and a clear flag are
still required before resource admission. Native exit invalidates this attempt.
Application command 6 is a different transition and retains native Wi-Fi after
custom borrowers retire; see [wireless lifecycle](../sdk/WIRELESS.md).

During command6 drain, the native-view check qualifies forwarding only. View
revocation does not cancel the already-owned radio/SDK cleanup. Once revoked,
the bridge finishes that same cleanup, retires its view and never invokes the
old coordinator or accepts a return for that cancelled switch. Real cleanup
failure remains a fault. The caller checks execute original code/view guards;
the separate service-chain check uses actual SDK readers with modeled native
view and radio completion.

Original-code checks under `tools/` include `check_app_sleep_callbacks.py`,
`check_sleep_client_packets.py`, `check_sleep_client_manager_chain.py`,
`check_manager_notification_wire.py`, `check_sleep_completion_dispatch.py` and
`check_kernel_sleep_wrapper.py`. Initial state, IPC/device or suspend are explicit
models. [Regression checks](../REGRESSION.md) cover the CFW adapters separately.
These results do not establish physical wake, RF power, timing or USB recovery.
