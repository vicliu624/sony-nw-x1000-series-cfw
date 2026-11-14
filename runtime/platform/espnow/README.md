# X1000 ESP-NOW transport

Native ESP-NOW transport for Japanese Sony NW-X1050/NW-X1060 on Sony 1.11.
It is independent of player control, controller display and ordinary IP apps.
A router is unnecessary; both endpoints must use the actual radio channel.

## Supported paths

| Path | Scope |
| --- | --- |
| Legacy mailbox | Fixed 32-byte application frames and optional 96-byte fragmented chat; separate experimental radio image |
| Full endpoint | Standard ESP-NOW vendor Action frames, v1/v2 payloads, peer admission, CCMP and receive replay checks |
| Managed Root consumer | Private system integration with native Wi-Fi borrowing, receive membership and explicit retirement |
| Link negotiation | Opt-in Root/Core2 fresh per-link keys; permanent pairing and player protocols are unchanged |

Do not interchange radio images, generated profiles or ABI assumptions between
these paths. Full v2 payload support does not enlarge the legacy mailbox.
The public SDK facade and the experimental native archive have separate versions
and delivery contracts.

## Implementation

- `xnow_link*` owns authenticated transcripts, unique key epochs and their counter
  scope. It has no player or hardware ownership policy.
- `xnow_endpoint*`, `xnow_security*`, `xnow_ccmp*` and `xnow_pn*` own peer/message,
  encryption and replay behavior.
- `xnow_owner_runtime*`, `xnow_owner_stream*` and `xnow_owner_transport.h` serialize
  app requests, negotiation and distinct completions over the owner's IPC.
- `xnow_full*`, `xnow_sd8686_full*` and `xnow_shared_session*` implement the pinned
  radio adapter and shared native receive membership.
- Wireless policy and native lease authority live in `../wireless/`. The remote
  player consumer lives in `../../apps/wireless-remote/`.

The full radio payload reserves the former fourth large packet block at
`0xc000a190..0xc000a8fc`. Its matching image reduces that pool to three blocks
and changes startup zeroing and the management callback. Never load it into the
unmodified four-block image. Exact code, pool, layout and profile guards are
required before driver access; a matching driver name alone is insufficient.

## Lifecycle and storage

Data admission and cleanup ownership are separate. Stop prevents new work but
retains the same owner until accepted producers, receive queues and native TX
have drained. Endpoint cleanup precedes receive-membership release, qualified
shared-sleep restoration and native-lease release. Neither a timeout nor process
exit proves hardware retirement.

App state, permanent bindings, reusable-key counter journals and bounded optional
diagnostics belong on verified user storage. Unique authenticated link keys may
use their dedicated volatile counter provider. Static keys require durable
counters. Do not clear a journal to make a restarted controller connect.
No system partition or system-backed temporary path is a persistence fallback.

## Build and verification

The [library guide](LIBRARY.md) describes local ARM archive builds and required
pinned inputs. Build output stays under ignored `work/`; building does not
install a driver, enable RF or access a player. Device operations require the
qualified native owner and explicit hardware scope.

Read [link keys](../../../docs/reference/ESPNOW_LINK_KEYS.md),
[wireless lifecycle](../../../docs/sdk/WIRELESS.md) and
[public ESP-NOW services](../../../docs/sdk/ESPNOW.md) for the corresponding
contracts. The maintained [regression groups](../../../docs/REGRESSION.md) record
source snapshots and test limits.

Earlier bounded physical bidirectional 96-byte exchange and stock restoration
are recorded in [validation](VALIDATION.md). They do not qualify the current
shared-radio composition. Current session, artwork, sleep and USB acceptance is
listed in [status](../../../docs/STATUS.md). Host models and ARM emulation do not
replace those physical checks.
