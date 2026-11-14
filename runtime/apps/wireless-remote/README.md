# Wireless Remote

Wireless Remote controls Sony's original player through ESP-NOW. It sends no
audio to the controller and does not replace Sony's playback engine. ESP-NOW
transport and player control are independent system capabilities combined by
this application.

This directory contains the Settings-managed consumer, service processes and
controller implementations. In the full research checkout, build the ARM service with
`python tools/build_remote_service.py`; activation belongs to the original
Settings integration. The foreground app catalog discovers directories with
`app.json`. This consumer has its own service entry instead of a foreground
application definition.

## User interaction

The original Settings page provides activation and pairing. With no saved peer,
Start pairing discovers a controller in its local pairing window. Select the
discovered device and confirm it; no pairing code is typed. With a saved peer,
the page shows its address. Selecting it opens the native removal confirmation.
A storage error must not be displayed as an unpaired device.

Wi-Fi mode permits the radio transport; router association is not required for
ESP-NOW. The controller must match the player's actual radio channel. Turning
Wireless Remote off stops this consumer. Wi-Fi Off drains custom consumers
before Sony's shutdown. An ordinary application switch must retain native
Wi-Fi while stopping the player-dependent remote consumer.

Both discovery and encrypted sessions acquire the same scoped native interface
receive membership when sharing Wi-Fi. The RF owner acquires it before READY,
retains it through partial-startup cleanup, and releases it after endpoint drain
but before restoring shared sleep or releasing the native borrow. This socket
owns a filter reference; authenticated payloads still use the endpoint and owner
stream. It does not replace the receiver with a packet-socket data path.

## Source responsibilities

| Files | Responsibility |
| --- | --- |
| `native_page_bridge*` | Translate private Sony page requests to this consumer's backend |
| `settings_backend*`, `settings_factory*`, `run_profile*` | User requests, system-owned task coordination and matching startup/retirement |
| `pairing_auto*`, `pairing_proof*`, `pairing_store*` | Selected-peer negotiation, verification and binding persistence |
| `service.c`, `supervisor*`, `worker*` | Service process and consumer lifecycle |
| `rf_owner.c` | Explicit RF owner entry with pairing/admission/retirement policy; private system integration, not an app template |
| `../../platform/espnow/native_environment.[ch]` | Shared native input, mount and key/PN preparation; retained workspace and caller-owned cleanup |
| `status_sender*`, `receiver*`, `control*`, `session_wire*` | Authenticated status/control and session correlation |
| `library_client*`, `library_wire*` | Bounded library navigation |
| `artwork_client*`, `artwork_wire*`, `artwork_image*` | Correlated image transfer and image validation |
| `core2/`, `cardputer/` | Controller-specific display, input and radio adapters |

Original menu callbacks, choice-view access and stock layout constants live in
`runtime/platform/sony-settings/`. The Settings factory reports ready work,
descriptor interests and whether retirement still needs a short wait. The
player's owner loop controls native admission and the wait timeout. The page
bridge and factory are private to this consumer. Third-party apps use public
SDK modules for player and radio access.

The shared radio implementation belongs in `runtime/platform/espnow`; original
player access belongs in `runtime/platform/player`. Neither should depend on a
controller's display or button layout. A protocol receipt does not grant radio
ownership and does not establish that a playback transition has completed.

## Runtime contract

- Controls use explicit PLAY, PAUSE, NEXT, PREVIOUS and volume intents. The
  latest observed state selects the opposite play/pause action. The icon shows
  observed playback state, matching Sony's indicator.
- Owner readiness requires endpoint bootstrap, peer admission and a fresh
  parent observation. Static-key profiles also require their journals. In the
  opt-in negotiated-key profile, application dispatch stays held until a fresh
  key and encrypted peer confirmation are established; see
  [link keys](../../../docs/reference/ESPNOW_LINK_KEYS.md). Canceled or denied
  preparation requests retirement without publishing READY.
- A completed, admitted round delayed by synchronous work requires a fresh
  parent observation before its next data round. The loop reuses its existing
  timestamp. Fast/idle rounds keep the ordinary observation schedule and expiry;
  stop, failed runtime work or a replaced lease cannot rearm the old session.
- A command receipt is distinct from completion. Never automatically repeat a
  sent command whose result is uncertain, especially NEXT/PREVIOUS.
- State is sent on change or explicit resynchronization. No periodic heartbeat,
  automatic quiet-session expiry or recurring reconnect probe is used.
- An explicit control coalesces one current-state refresh, even if the command
  leaves native state unchanged. This recovers a previously missed snapshot
  without an idle poll or replaying the control.
- Command admission, observed target state and peer response are separate facts.
  A missing receipt does not invalidate a newer authenticated state. An accepted
  command whose target remains unconfirmed is not automatically a lost link.
- A boot/user-demand/new-session handshake is bounded. Cached metadata remains
  last received data; it is not proof of a currently reachable player.
- An authenticated handshake uses its protocol/challenge as request identity.
  A fresh explicit attempt is independent of media sequence advancement; an
  identical request returns its cached reply and coalesces one status refresh.
  This does not replay a player command or introduce idle traffic.
- Changed status is scheduled before the next artwork response. Image transfer
  must not starve controls or status publication.
- Cover retries retain request identity and accept only correlated,
  authenticated replies. The controller fetches a bounded current-track image,
  decodes it once and retains pixels in RAM. No disk artwork cache is created.
- Temporary unknown track identity pauses assembly and presentation without
  discarding progress. Only a confirmed identity permits more chunks. The
  managed READ session rejects cache-epoch changes; bounded zero-offset restarts
  prevent mixed images. The renderer reads progress without mutating the job.
- Five stock play modes are read from the player. Unknown is distinct from
  Normal. Merely moving focus must not change playback or its mode.
- Leaving the player stops its remote consumer and drains the SDK generation.
  Native app handoff, sleep and USB shutdown have separate completion rules.
- Data-observation expiry stops traffic without discarding retained cleanup
  ownership. Shared sleep-setting restoration requires a fresh read-only
  observation of the exact original lease plus the independent owner/native
  checks. Cleanup never restores data permission, repairs a failed policy or
  authorizes work on a replacement lease.
- Stop observation is cooperative between data stages. Once accepted, a stop
  prevents later player reads, library work and cover production in that step.
  An already admitted call may finish. Player close, local radio detach and the
  independent retirement receipt remain distinct cleanup stages.
- Producer callbacks may request stop synchronously. Signal handlers write a
  flag; the worker observes it between stages. The first accepted stop reason
  is retained together with a later callback error. Cleanup still runs while
  the stop flag remains set. Requested closure includes supervisor lifecycle
  actions and does not identify a manual user action by itself.

## Storage and cleanup

Binding keys and packet-number journals belong on verified user storage. They
are retained across updates. V2 counter storage uses two fixed 80-byte slots;
never reset them under the same key or downgrade to a reader that ignores them.
Unknown/corrupt counter state refuses activation.

System-installed owner/service binaries are code, not writable runtime state.
Logs, diagnostic records, partial transfers and pairing state must not grow
system partitions. Diagnostic capture is bounded RAM while consumers run;
qualified flushing uses a preallocated user-storage file with no system fallback.

The retirement summary records decoded/auth/replay counts, negotiation traffic,
key installs and unrestored shared wake state. It adds no driver queries or
file writes while the owner is active. The parent retains it in RAM and uses
the existing quiescent trace flush. Legacy or incomplete summaries remain
unknown. Each physical trial needs a fresh diagnostic seed: occupied slots are
preserved and must not be interpreted as results of a later run.

A normal child exit is not sufficient hardware-retirement evidence. The
supervisor checks owner identity, retirement receipt, EOF and SDK drain. The
private clean-start refusal code is valid only with independent cleanup proof;
unknown exits and uncertain cleanup retain fault handling.

## Development and verification

Read [architecture](../../../docs/ARCHITECTURE.md),
[wireless lifecycle](../../../docs/sdk/WIRELESS.md),
[player client](../../../docs/sdk/PLAYER_CLIENT.md) and
[Core2 controls](core2/README.md).

```sh
.venv/bin/python tools/test_firmware_regressions.py --suite lifecycle --suite remote
```

These are offline checks. Pairing and controls have worked in earlier device
builds, but later control/session regressions and incomplete Core2 artwork
remain open; see the single [current status](../../../docs/STATUS.md) table.
Do not infer physical RF, sleep or USB acceptance from source builds.
