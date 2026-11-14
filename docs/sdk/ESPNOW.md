# ESP-NOW services

The SDK exposes binary transport, codecs, security and explicit owner services.
ESP-NOW does not depend on the original player. Wireless Remote is one consumer
that combines transport with the separate player service.

Choose a transport profile first. The legacy mailbox, standard Action-body
codec and manager-supplied client have different packet limits and ownership
contracts. Linking a module does not load a radio image, start an owner, grant
access, disconnect Wi-Fi or install firmware.

Pin the exact version in `sdk/VERSION`. Current source and the published archive
are distinct configurations; see [status](../STATUS.md).

## Choose modules

| Module | Provides | Requires |
| --- | --- | --- |
| `espnow-client` | Bounded datagrams and peer operations through supplied FIFO descriptors | An authorized owner and its lifecycle contract |
| `espnow-core` | Legacy binary frame/mailbox codec and lifecycle policy | C library |
| `espnow-message` | Optional 96-byte text fragmentation and application ACKs | Core; no embedded NUL |
| `espnow-device` | Legacy fixed-mailbox JP1.11 controller and device adapters | Original libraries, exact image/profile and qualified exclusive guards |
| `espnow-full` | Standard variable-length frames, peers, endpoints and PN reservation | Core/hash; no automatic activation |
| `espnow-security` | CCMP, endpoint security, durable PN files and PMK vault | Full, ABI/crypto adapters and verified user-storage callbacks |
| `espnow-full-device` | Full-radio adapter and drain-before-restore controller | Full, original services, matching profile and platform guards |
| `espnow-owner` | Managed handoff, command streams, owner gate and runtime | Full-device/process adapters and a reviewed launch capability |

Public imports are under `<x1000/services/>`; function names retain the `xnow_`
prefix. `espnow.h` is the umbrella. Device implementations are C with the
verified ARM/Sony-libc ABI. Python is PC tooling only.

## Build an application

Prepare pinned original libraries locally:

```sh
python tools/sdk.py setup --services
```

Use the [native-services build](SERVICES.md) and select only needed modules.
For example, an application using a supplied client capability declares:

```json
"sdk": {
  "version": "0.2.0-alpha.10",
  "profile": "native-services",
  "modules": ["startup", "espnow-client"]
}
```

The version must match the installed SDK. Original libraries remain local and
are excluded from source SDK/application packages. Device-module builds generate
an identity header for their bridge code, not a deployable radio image. An
independently supplied image must match that identity and its verified profile.

## Use a supplied client

Include `<x1000/services/espnow_client.h>`. Allocate a fresh zeroed client in
static/heap storage and use it from one serialized worker. There is no endpoint
discovery, automatic activation, reconnect or fork reuse.

1. Adopt the owner's distinct nonblocking FIFOs with `xnow_client_adopt`.
   Success transfers both descriptor lifetimes; failure leaves them with the
   caller. The manager must close unintended copies.
2. Submit peer/send operations. A successful submission creates one request ID;
   PENDING creates no new request or ID. Keep another intent until capacity is
   available rather than assuming it was queued.
3. Step bounded I/O with `xnow_client_step` and retrieve events with
   `xnow_client_take`. Too-small output capacity preserves the staged event.
4. Distinguish request ACK, radio TX completion and peer application ACK. None
   alone proves playback, user action or hardware retirement.
5. Request stop through the owner contract, then detach locally with
   `xnow_client_close`. Detach/EOF/stop ACK alone is not a radio cleanup receipt.

Client payloads are bounded to 1,470 bytes; the actual owner/profile may impose
a lower limit. RSSI is not fabricated. Pending LMKs are wiped after complete
write or failure; callers must wipe their own copies.

Admission and cleanup belong to the system owner. Depending on the qualified
profile, it supplies an exclusive lease or a shared borrow. A shared client
must not disconnect the surviving native Wi-Fi owner. Sony Settings callbacks
and the private shared-session adapter are not public SDK entry points.
See [wireless lifecycle](WIRELESS.md).

## Standard datagrams and security

Use `espnow_wire.h` for v1/v2 plaintext Action bodies and MAC headers;
`espnow_endpoint.h` / `espnow_peer.h` provide application datagrams and peer
selection. Binary and empty payloads are supported, with codec limits of 250
bytes for v1 and 1,470 for v2. These limits do not qualify a radio profile.

`espnow_security.h`, `espnow_endpoint_security.h`, `espnow_pn_file.h` and
`espnow_keyring.h` provide separate security/persistence components. For the
measured Espressif S3/IDF5.5.1 profile, attach with
`xnow_endpoint_security_attach_espnow` before adding peers. Peer LMKs are API
LMKs: derive the journal scope with `xnow_ccmp_espnow_wire_key(pmk, api_lmk,
wire_key)`. The measured profile uses nonce0, legacy AAD and Key ID3; the generic
attach method retains its distinct management profile. MIC checks stay enabled.

Supply durable reserve/load/commit callbacks on verified user storage. Resume
existing records for used keys. Provision a missing journal only for a proven
fresh key; never reset a PN to recover from an error under an existing key.
Current V2 storage and downgrade limits are in [wireless lifecycle](WIRELESS.md).
No key, private identity or permissive storage callback is supplied by default.

AUTHENTICATED is set only after MIC/replay verification and RX-state commit.
Broadcast data is not authenticated. XNR1 carries RX flags at offset 24 in its
32-byte header; offset 28 remains reserved. Old zero flags do not prove security.
Malformed plaintext is a format rejection, not backend IO. Actual read/storage
errors propagate into stop/restoration handling.

## Explicit owner runtime

`espnow-owner` supplies managed foreground handoff, binary commands, partial
streams and the owner runtime. It does not imply that a standard installed
launcher grants the capability. The reviewed host must supply it; absent or
invalid authority refuses RF work. The 80-byte `launch.contract` binds opt-in
to the app executable hash.

Construct the gate, controller and nonblocking stream before runtime start.
The gate supplies the controller lease; platform guards still establish the
original device, mount, USB and epoch conditions. Keep unintended owner-only
descriptor copies closed, handle SIGPIPE and provide `prepare`/`close_data`
callbacks. Encrypted preparation must attach complete crypto/storage operations.

Cooperative stop is observed between storage, prepare, command, completion and
receive stages. An admitted call may finish; the next producer is not started.
A prepare callback may request stop and return success to enter normal
retirement, including before crypto setup is complete. Real callback errors
remain recorded when stop is also requested. The data-close callback must clean
up partially prepared state after controller retirement.

Keep stepping while pending. On UI disconnect, the owner drains/restores,
closes storage references, notifies completion and closes the restore writer.

For shared radio, successful endpoint drain returns `XNOW_SESSION_STOPPING`
while the original manager lease is still held. The composing owner must close
its receive membership and finish any owed shared-sleep restoration before the
next controller step can execute RELEASE. The endpoint accessor already refuses
new data during this interval. Closing a socket or seeing STOPPING alone does
not authorize a native USB/sleep acknowledgement; final matching retirement
evidence is still required.
Unknown ownership or failed restoration retains fault handling. A timeout or
normal process exit cannot substitute for completion evidence. Calls to original
manager/driver methods may block, so run them away from rendering/input callbacks.

This explicit source owner is separate from the private system firmware
integration. A generic manager-delivered background-task API is not published;
see [service lifecycle](LIFECYCLE.md).

## Legacy mailbox profile

The legacy `espnow-device` bridge carries exactly 32 bytes: a 16-byte XNOW header
and 16 opaque data bytes. `xnow_encode`, `xnow_mailbox_send`,
`xnow_mailbox_receive` and `xnow_decode` support binary data. The optional
`xnow_chat_*` helper adds text fragmentation/retries; it is not a binary stream.
Neither limit applies automatically to the distinct full-radio adapter.

Use explicit channel/disconnect options and qualified controller guards.
READY permits mailbox use. On exit, request stop and step until completion;
inspect both failure fields because DONE alone is not success. The launcher's
ordinary termination deadline is not proof that restoration has finished.

## Verification and limits

Run the public consumer checks from the prepared environment:

```sh
python tools/test_sdk_espnow.py
python tools/test_sdk_espnow_full.py
python tools/test_sdk_espnow_owner.py
```

They cover public C/C++ consumers, original-libc ARM execution and modeled
codec/ownership/stream operations. They do not access the radio. Clean SDK archive
checks repeat setup/build from extracted source; a stale local library is not
source-only reproducibility.

Recorded physical exchanges, private native power/Settings bindings and their
limits are in [native wireless reference](../reference/STOCK_WIRELESS.md).
The [full-stack guide](../ESPNOW_FULL_STACK.md) defines broader interoperability
and acceptance work. Public interfaces remain experimental, not an ESP-IDF
drop-in ABI. RF current, complete sleep/wake, USB handoff, multi-peer load and
power-loss recovery require separate physical acceptance.
