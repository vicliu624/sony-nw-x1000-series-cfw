# Wireless capability and lifecycle

The native Settings integration exposes **Wi-Fi** and **Off**. ESP-NOW is a
transport capability available to an admitted consumer; Wireless Remote is one
consumer with its own On/Off and pairing policy. Neither the transport nor the
SDK player-control API is inherently a remote-control application.

This guide describes private system integration. Public transport modules and
build examples are documented in [ESP-NOW services](ESPNOW.md). Installing an SDK
archive does not install a global mode manager or grant hardware ownership.

The opt-in Root/Core2 transport can negotiate fresh per-link keys without
replacing the permanent binding or resetting old replay journals. This private
composition is described in [link keys](../reference/ESPNOW_LINK_KEYS.md); it is
not yet installed on the test player or exposed as a new public service module.

## Ownership

| Object | Owner | Purpose |
| --- | --- | --- |
| Wireless mode policy | Serialized system/GUI owner | Select allowed mode and track exact resource generations |
| Native Wi-Fi lease | Sony lifecycle adapter | Ordinary connection manager access and qualified shutdown |
| Shared borrow | One custom consumer, issued by the system owner | Use the active Wi-Fi radio without acquiring its native lease |
| ESP-NOW endpoint | Admitted transport consumer | Peer/message operations and transport cleanup |
| Player session | Original-player service owner | Playback controls, state and library requests |
| Remote binding | Wireless Remote application | Persist selected peer and authentication state |

`mode_policy.c` contains no hardware detector, loader, player, thread or timer.
Its state is meaningful only when trusted native adapters supply identity and
retirement evidence. Creating another copy in an app does not create another
global authority.

A lease consists of generation, serial, consumer and mode. Data permission is
separate from cleanup ownership. Draining revokes new data while the old owner
retains responsibility for release. A stale callback cannot release a newer
lease. Failures retain ownership and an explicit failed policy state.

The Remote owner's cleanup observation is distinct from its data observation.
After data expires or is revoked, restoration may continue only with a fresh,
correlated snapshot of the same retained lease and independent native checks.
An old queued reply is discarded before requesting that snapshot. The cleanup
query keeps the one-second bound and permanently closes data admission; it does
not repair a failed policy, revive a session or prove hardware power-off.

A completed, previously admitted Remote round may have blocked in synchronous
work. Before continuing data, its owner can demand a new parent reply using the
same retained lease. Old queued replies do not suffice. Fast/idle rounds retain
the normal observation cadence and one-second expiry. This does not revive an
observer that already revoked data or continue after a stop/runtime failure.

A shared borrow pins native Wi-Fi until the custom consumer has drained. Its
separate ticket prevents a previous borrower from releasing a newer borrower
on the same native lease. It does not authorize native radio shutdown.

The full controller yields STOPPING immediately after shared endpoint drain.
Before its next step can release the manager, the Root owner closes receive
membership and restores only sleep state that it changed. Cleanup failures
retain the lease and uncertainty. This is an explicit call boundary, not a
delay used as proof of retirement.

## Mode selection and startup

Selecting Wi-Fi permits native Wi-Fi and shared consumers; it does not prove
association with a router. ESP-NOW does not require a router. A shared consumer
follows the actual channel; its peer must use that channel. No operation may
assume that a powered radio is always on channel 1 or the cold-start default.

Selecting Off retires custom consumers before forwarding Sony's shutdown. An
active borrower delays that shutdown; it must not be silently revoked while
using the chip. Switching Wireless Remote off closes only that consumer and
leaves ordinary Wi-Fi available.

Startup distinguishes a qualified pre-existing native owner from an off radio.
The authority adopts the former or admits the reviewed cold-start path for the
latter. It must not reject a valid off-radio start merely because an earlier
prototype expected powered/unassociated state, nor reload the chip underneath
an already active native owner.

The original cached Wi-Fi setting is two-state: category 6/item 0x600 uses 0 for
Wi-Fi and 1 for Off. Native getter 0x37f5c returns through its output argument;
its return register is not a status. Private legacy ESP-NOW mode value 2 remains
in internal compatibility/test paths. Never persist it as Sony's two-state
setting. Native menu resources must match the two-choice composition.

## Application, sleep and USB transitions

| Caller | Private method | Required result |
| --- | --- | --- |
| Application command 6 | `xw_player_host_wireless_prepare_application` | Drain custom borrowers; preserve the exact valid native Wi-Fi lease |
| Application activation | `xw_player_host_wireless_resume_application` | Reopen player admission after successful stock activation |
| Sleep preparation | `xw_player_host_wireless_prepare_handoff` | Drain custom consumers and require verified radio retirement |
| Verified sleep recovery | `xw_player_host_wireless_resume_handoff` | Reopen the matching sleep epoch after native recovery |
| USB/permanent exit | `xw_player_host_wireless_prepare_stop` | Drain and stop; do not automatically rearm this player instance |

An application handoff and a sleep handoff cannot consume or resume each
other's epoch. The original GUI owner allocates monotonically increasing epochs.
Preparing/resuming with a stale epoch or the wrong transition kind is refused.

For ordinary application switching, Sony wireless component 0x3b498 handles
command 6 by calling 0x3b404(1), which sets context +0x20. Commands 7 and 21 clear
that flag. These paths return token zero and enqueue no RF operation. Therefore
application handoff must not manufacture a Wi-Fi disable request. Forcing a
native disconnect here prevents Homebrew network apps from using an existing
association and cannot be repaired by asking them to retry the old IP address.

`host_handoff_bridge.c` first stops player-dependent custom work, then invokes
stock coordinator 0x112fc from a later owner-loop tick. It waits for successful
native activation with the correct client and newer sequence before reopening
admission. It does not inject a fake native completion token.

Screen blanking, sleep preparation and completed sleep are different states.
A display-off observation alone is not sufficient reason to end the remote
session. Physical sleep/wake and radio continuity remain hardware acceptance
items; the generic guest does not model them.

The qualified original input wait also includes currently owned SDK IPC
descriptors. Managed channels wait for reads or pending reply writes; the mode
observer waits for its next request or queued reply. Readiness wakes the existing
owner loop without exposing SDK descriptor bits as Sony input events. This keeps
request handling independent of a long stock select timeout. It does not change
the authorization observation lifetime, native sleep admission or on-air traffic.
The existing bounded idle-timeout lease remains a fallback for non-I/O work.

This private adapter applies only to the verified GUI owner/callsite and original
32-bit select ABI. Other calls delegate to Sony's original implementation.
It neither owns descriptors nor grants access; producers remove closed/faulted
channels from the wait set. Pending writes use write readiness to avoid spinning
on queued input while a reply is blocked. See [native lifecycle reference](../reference/STOCK_LIFECYCLE.md).

## Qualified radio retirement

`native_stop.c` posts Sony disable event 0x4c0006 through original queue entry
0xa57f0. Queue return 0 means backpressure; retry on a later GUI tick. Return 1
means accepted, not completed. No direct register write or module unload is
introduced by this adapter.

Original power-off runs through connection-manager request kind 4 and its stock
stop/unload path. `cnmgr_fin`, disconnect, a cleared UI flag, process exit and
closed descriptors are not power-off evidence.

A retirement notice carries the exact lease and worker seal. Its independent
checks require successful native result, public closed state 2 and absence of
`sd8xxx`, `mp200_sdio`, `wlan_pm_register` and `wlan_pwr_ctrl`. The original unload
script can mask a later module-removal failure, so shell success alone is not
sufficient. A stale/malformed notice cannot release current ownership.

Original helper 0x3b41c is not an off primitive: depending on cached/environment
state it posts 0x420012 and 0x4c0005, initiating native Wi-Fi work. Do not call it
to implement shutdown. The pinned callback, queue and unload behavior has
instruction-level tests; measured power consumption remains a hardware question.

## Interprocess observation

`mode_channel.c` is the trusted nonblocking server. `mode_client.c` consumes an
inherited connected descriptor and expected identity; an app cannot create its
own authority through it. READ-only observers may query the exact lease but
cannot select mode, acquire, release or supply retirement evidence.

The client permits one request at a time and records descriptor identity to
avoid closing an unrelated reused FD. A step performs one nonblocking send or
receive. Unknown generations, serial reuse, stale replies and unexpected grants
are refused. A successful reply delivery is distinct from its operation result.

The owner admission adapter refreshes its local permission observation; DATA
expires without a fresh matching response. These local ownership checks are
independent from on-air heartbeat policy. There is one reader for a delegated
channel; parent diagnostics must not consume the child's replies.

## Remote protocol and persistence

- WRS2 carries compact authenticated state; WRS1 remains accepted. WRH1 is
  decode-only compatibility. Current senders emit no periodic heartbeat.
- State is published when changed or explicitly requested. Quiet time does not
  prove disconnection. One bounded user-demand handshake may obtain a new
  session; an uncertain sent playback command is never replayed automatically.
- An explicit control also requests one coalesced current-state snapshot. A lost
  prior update plus an idempotent control must not leave the receiver permanently
  displaying the old state. This adds no periodic traffic.
- The remote distinguishes command outcome from peer response. A matching
  receipt is not completed playback; a newer authenticated snapshot can remain
  usable even if the receipt was lost. Expiring a state goal does not erase a
  response already received or supply radio ownership/retirement evidence.
- Status scheduling precedes the next artwork response. Image traffic must not
  starve changed playback state or control receipts.
- Artwork requests retain identity on retry; valid late same-request replies
  may be accepted. Wrong track, offset, session or authentication is rejected.
- WPI2/WPO2/WPA2 pairing uses ephemeral X25519 and transcript-bound confirmation.
  Selection on the Walkman completes pairing without typing a code. First
  contact has no out-of-band identity authentication.
- A valid saved peer replaces Start pairing with the peer address. Selecting it
  opens the native unbind confirmation. Storage errors are not an absent peer
  and must not trigger discovery automatically.

Pairing keys and packet-number journals live on qualified user storage. Legacy
XPN00001 dat/tmp records are scope/checksum validated and may advance to their
highest verified reservation. Current XPN00002 persistence uses two fixed
80-byte slots, updating the older slot under a scope lock and syncing file and
directory. Steady-state commits do not rename or truncate directory entries.

After V2 is observed, missing/corrupt slots are refused rather than rolling
back. Old firmware cannot read V2: do not reset counters under existing keys to
make a downgrade work. Explicitly re-pair with new keys if compatibility cannot
be retained. Numeric result -21 alone is ambiguous between historical endpoint
CHANNEL and security STORAGE; preserve the failure origin in diagnostics.

A service's private clean-start refusal result 75 is not generic success. The
supervisor still requires a matching complete RF retirement record, EOF and
normal owner retirement, then drains the SDK generation before policy release.
Unknown exits, signals and uncertain cleanup keep the fault path.

## Implementation map

| Concern | Source |
| --- | --- |
| Serialized policy and typed leases | `runtime/platform/wireless/mode_policy.[ch]` |
| Local observation channel | `runtime/platform/wireless/mode_channel.[ch]`, `mode_client.[ch]` |
| Stock mode publication and retirement | `native_publisher.c`, `native_rf_worker.c`, `native_retirement.c`, `native_stop.c` in the wireless platform |
| Stock/player transition adapter | `runtime/platform/player/wireless_host.[ch]`, `host_handoff_bridge.c`, `sleep_host.c` |
| SD8686 and transport | `runtime/platform/espnow/` |
| Remote policy, pairing and protocol | `runtime/apps/wireless-remote/` |
| Public source modules | `sdk/include/x1000/services/`, `tools/sdk_services.py` |

## Verification

Run the lifecycle and remote groups in [regression checks](../REGRESSION.md).
`test_stock_wireless_lifecycle.py` executes 224 original ARM callback cases.
`test_wireless_mode_channel.py` runs real local IPC and production policy under
host sanitizers and Sony-libc ARM, including separate application-retention and
sleep-retirement cases, with and without a shared consumer. Hardware state is
supplied by fixtures. Native RF queue, sleep recovery and explicit stop have
separate tests; none substitutes for physical association, USB or power tests.

Current feature acceptance is listed once in [status](../STATUS.md). Do not
interpret an old prototype's exclusive-mode assumptions or historical test
counts as the current product contract.
