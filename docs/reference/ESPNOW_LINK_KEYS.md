# ESP-NOW link keys

The managed Root owner and Core2 support authenticated per-link encryption
keys. This is an opt-in development composition, not the protocol in the
installed `shared-rx-02` image. Core2 alpha.29 requires the matching Root
`--link-keys` build. Do not update one side alone or erase a binding to
compensate for a version mismatch.

## Key lifetime

An ESP controller reboot can restart its native CCMP packet number at 1. A
receiver with a higher replay floor must reject that frame when the key is
unchanged. Clearing the replay journal permits replay and does not fix nonce
reuse. Burning application packets supplies no durable native-counter contract.

Each link derives a fresh 128-bit LMK from the existing 32-byte authentication
secret, ordered endpoint MACs and two fresh 128-bit nonces. The permanent
binding, PMK and application authentication remain unchanged. WRQ2/WRP2,
controls, metadata, library and artwork formats do not change.

## Negotiation

Negotiation uses 96-byte plaintext broadcasts with domain-separated
HMAC-SHA-256 authentication truncated to 16 bytes. No pairing secret or LMK is
transmitted. Authentication does not make a broadcast confidential.

| Message | Sender | Meaning |
| --- | --- | --- |
| ANNOUNCE | Root | A fresh owner instance is available |
| HELLO | Controller | Start an explicit attempt with a fresh controller nonce |
| OFFER | Root | Return that nonce and a fresh Root nonce |
| CONFIRM | Controller | Authenticate that exact challenge pair |
| READY | Root | Root installed the key; controller may install its matching key |

Key derivation is HMAC-SHA-256 over `X1000-ESPNOW-LINK-LMK-v1`, followed by Root
MAC, controller MAC, controller nonce and Root nonce, truncated to 16 bytes.
Wire authentication uses the distinct domain `X1000-ESPNOW-LINK-WIRE-v1`.
Nonces require platform entropy; clocks, MACs and saved request IDs are not
substitutes.

Root retains an active key until a matching CONFIRM authorizes replacement.
After installation it waits for an authenticated encrypted peer frame before
reopening app dispatch. Replayed HELLO/CONFIRM cannot recreate an old key:
a fresh challenge is required. Duplicate responses do not reinstall a key or
reset packet numbers.

Each attempt has a four-second deadline and at most three sends per phase,
700 ms apart. Submission retries retain the same transcript. There is no idle
heartbeat, periodic reconnection or quiet-session expiry. An uncertain playback
command is never automatically repeated.

## Ownership

| Module | Responsibility |
| --- | --- |
| `runtime/platform/espnow/xnow_link.[ch]` | Pure C transcript, authentication, key derivation and retry/deadline rules |
| `xnow_link_counter.[ch]` | RAM counters scoped to one authenticated unique key epoch |
| `xnow_owner_link.[ch]` | Root endpoint/key adapter; serializes key replacement after app and native TX drain |
| `xnow_owner_transport.h`, `xnow_owner_runtime.[ch]` | Separate negotiation progress from app requests and completion tokens |
| `runtime/apps/wireless-remote/core2/src/link_transport.*` | Controller adapter using public ESP-NOW peer APIs on the ordinary loop |

Only authenticated unique link keys may use volatile counters. Static/reusable
keys still require durable counters. Existing journals remain on user storage;
they must not be reset or treated as volatile state. Unknown/reused scopes fail.
Peer replacement waits for all native TX callbacks. Failed or late key
installation closes data admission.

Root holds an app SEND in the input stream during negotiation. It does not
publish a successful receipt containing a pending result. Sideband TX owns its
own completion. The independent stop token and pipe closure remain observable
while dispatch is held.

Logical cancellation wipes negotiation secrets and prevents new work. It does
not prove hardware retirement. Cleanup still disables RX, waits for accepted
producers, drains RX/TX, clears endpoint crypto, closes receive membership,
restores qualified shared sleep and releases the native lease. A timeout cannot
substitute for these completions.

## Verification

```sh
.venv/bin/python tools/test_xnow_link.py
.venv/bin/python tools/test_xnow_link_counter.py
.venv/bin/python tools/test_xnow_owner_link.py
.venv/bin/python tools/test_owner_transport_runtime.py
.venv/bin/python tools/test_core2_link.py
.venv/bin/python tools/test_core2_owner_bus.py
```

The combined check runs actual Root owner pipes, CCMP and the Core2 peer adapter.
It covers both process restarts, bidirectional encrypted data, held app requests,
quiet sessions and stop with outstanding producer/TX work. Radio words, native
peer APIs and delivery are modeled. Separate ARM checks use Sony libc and the
ARM926 profile. These checks do not qualify over-air delivery, sleep/wake or
physical USB recovery; see [status](../STATUS.md).
