# Experimental ESP-NOW services

SDK0.2.0-alpha.7 extends xnow_full_received with RX flags: BROADCAST1 and
AUTHENTICATED2. Rebuild native consumers with the matching headers/library;
the frozen0.2.0-alpha.6 source zip and its verification receipt are unchanged.
AUTHENTICATED is reported only after successful MIC/replay checks and RX-state
commit; broadcasts are not authenticated. XNR1 offset24 now carries flags:u32LE
within the existing32-byte header; offset28 remains reserved. Old zero flags do
not prove authentication. See the full-stack guide for source validation scope.

[Radio/host implementation and stack gaps](../ESPNOW_IMPLEMENTATION.md) explain
how the original Marvell radio path is reused and what remains incomplete.

The newer [full-stack research implementation](../ESPNOW_FULL_STACK.md) adds
variable-length v1/v2, peer/security/journal code and an experimental full-radio
profile. The optional full modules below now expose these source interfaces. Whole
QEMU/Unicorn chains are offline evidence, not physical encrypted interoperability.

SDK0.2.0-alpha.8 exposes the measured encrypted profile explicitly. Call
`xnow_endpoint_security_attach_espnow(endpoint, workspace, local, pmk, block, io)`
before adding peers. Peer LMKs are API LMKs; provision TX/RX journal scopes using
`xnow_ccmp_espnow_wire_key(pmk, api_lmk, wire_key)`, not the API LMK directly.
The observed S3/IDF5.5.1 profile uses nonce0, legacy AAD and Key ID3. The generic
attach function retains its management profile. Keep MIC verification enabled.

The caller supplies guarded durable reserve/load/commit callbacks on verified
user storage. Resume existing records for used keys; provision only genuinely
fresh keys. Store no state in system partitions. Native context structs changed,
so rebuild every consumer with matching headers and sources. Physical encrypted
1470-byte bidirectional tests and process continuation pass; broader lifecycle,
over-air replay and power-loss qualification remain open. Linking never starts RF.

SDK0.2.0-alpha.6 includes the XNOW0.1.0-dev.11 C interfaces plus source owner services. Select the modules
explicitly in a native-services application; linking them does not load radio
firmware, disconnect Wi-Fi, open a device or install a service.

| Module | Use | Dependencies |
| --- | --- | --- |
| espnow-core | Binary frame codec, raw mailbox datagrams and lifecycle policy | C library only |
| espnow-message | Optional96-byte non-NUL message fragmentation, retry and application ACKs | core |
| espnow-full | Standard variable-length backend, peers, endpoint and PN reservation | core, hash; no activation |
| espnow-security | CCMP, protected endpoint adapter, PN files and local PMK vault | full, ABI, BearSSL; explicit caller storage policy |
| espnow-full-device | Bounded exact-profile driver and drain-before-restore controller | full, original device services; mandatory platform guards |
| espnow-owner | Managed foreground handoff, generic binary commands/partial IPC, gate and owner runtime | full-device, process; mandatory platform/storage guards; no automatic activation |
| espnow-device | JP1.11 driver adapter, stock connection manager, worker jobs, RF init, exact file checks and owner controller | core, ABI bridges, SHA-256, original libcnmgr/pthread |

## Build through the SDK

Run `python tools/sdk.py setup --services`. This extracts hash-pinned original
libraries locally; none is redistributed in the source SDK. An app contract can
select the device layer:

```json
"sdk": {
  "version": "0.2.0-alpha.8",
  "profile": "native-services",
  "modules": ["startup", "espnow-device"]
}
```

Protocol-only clients select espnow-core instead. espnow-message is optional;
espnow-device does not select it. Use the ordinary declarative
native-services build.json and build.py described in SERVICES.md. Public imports:

```c
#include <x1000/services/espnow_chat.h>
#include <x1000/services/espnow_mailbox.h>
#include <x1000/services/espnow_control.h>
```

espnow.h is the umbrella. Function names remain xnow_*, and structures/wire
formats are unchanged. Device sources are C with the original ARM/Sony-libc ABI;
Python is build-host tooling only. Device selection compiles the included radio
bridge C/linker input to generate its exact code-identity header. The compiler
receipt records that generated header's hash. It does not construct, deploy or
load a Sony radio image. An independently loaded image must match this build.

Run `python tools/test_sdk_espnow.py` for separate core/device ARM926 consumers.
They use public headers, roundtrip binary datagrams containing NUL/high-bit
bytes, separately test optional96-byte messages, and check missing-guard refusal.
They never open a real radio. The source-bundle test
runs them again from an extracted archive with clean setup inputs.

## Device lifecycle

The API is not restricted to chat. Remote controls, telemetry, synchronization,
games and user-defined binary protocols can use the same raw transport. With
the current bridge, a radio packet is exactly32 bytes: the XNOW header occupies
16 bytes and the remaining16 are opaque binary data, including zero bytes.
Use xnow_encode with XNOW_DATA, then xnow_mailbox_send; receive with
xnow_mailbox_receive and decode with xnow_decode. The application chooses its
sequence/token semantics, payload schema, fragmentation and reliability policy.
The channel is explicit in the controller options. These are implementation
limits, not permitted-use rules or the complete capabilities of ESP-NOW.

The existing xnow_chat_* names belong only to the optional message helper,
retained for source compatibility. That helper rejects embedded NUL and is not
a general binary stream. Raw transport imposes no such text restriction. Its
current poll-driven radio and latest-snapshot receive design still apply.

Use xnow_control_init with explicit channel/disconnect policy and independently
verified radio/file/USB and original-RAM-IPC callbacks. Step it from one owning
worker process. Calls may block on the original manager or driver and do not
belong on a UI thread. READY permits xnow_control_mailbox. Connect the mailbox
send/receive operations to your own protocol, or optionally use xnow_chat's
message callbacks and tick regularly.
Publication, radio acceptance and peer application ACK are separate outcomes.

Request xnow_control_stop on exit and continue stepping until finished. Examine
both session failure fields; DONE alone is not success. Unknown worker ownership
or a failed restoration is not permission to exit/reinitialize the controller.
Retain the client, inspect the error and explicitly retry only when justified.
The optional stock-rehearsal constructor exercises recovery without a candidate.

The normal launcher termination deadline is not long enough to assume radio
recovery will complete. The separate chat app now uses an independent owner
and RAM pipes. That exact client/owner path passed physical exchange and EOF
restoration. The user then reported Chat testing passed. That report does not
qualify an exhaustive input/HOME/sleep/USB matrix. Merely
selecting the SDK module never enables a radio switch or installs an owner.
Preparing and qualifying the modified radio image requires the full project's
RF research inputs. The lean source SDK supplies the library, not a preinstalled
radio image or a default always-successful ownership callback.

## Physical evidence and limits

The original Cardputer (not ADV) and Japanese NW-X1060 exchanged96-byte messages
in both directions with application ACKs on channel8. The native worker exited,
Wi-Fi recovered automatically, and the original radio fingerprint/pool were
verified afterward. The exact tested library hash is documented in
[XNOW validation](../../runtime/platform/espnow/VALIDATION.md).

That experiment predates SDK aggregation: it proves the identified underlying
native implementation, not every SDK-generated executable. No general sleep,
USB storage, long-duration, throughput, multi-peer or other-model acceptance is
claimed. Custom chat packets have no application encryption. All new app files,
images and logs must remain on verified user storage; no system-partition
fallback is provided. SDK source packaging contains no Sony firmware or private
device credentials, and installation/flashing is never a build side effect.

## Full-stack development additions

The new espnow_wire.h public interface encodes/decodes standard plaintext v1/v2
Action bodies and MAC headers without XNOW framing. It supports binary/empty
payloads and up to250/1470 bytes in the codec. The current deployed radio adapter
still has its old32-byte mailbox limit: codec support is not a claim that large
or encrypted packets work on hardware. See ../ESPNOW_FULL_STACK.md for the full
acceptance matrix and host-command doorbell experiment.

## Full-stack source API

Use public espnow_endpoint.h / espnow_peer.h for general application datagrams,
not the optional chat protocol. espnow_security.h, espnow_endpoint_security.h,
espnow_pn_file.h and espnow_keyring.h expose the separate security/persistence
components. espnow_full_control.h exposes the experimental original-action
controller; its platform guards must establish real exclusive/USB/mount/epoch
ownership. No permissive owner or automatic key/PN provisioning is supplied.

With the security adapter attached, malformed plaintext wire data is reported as
XNOW_SECURITY_FORMAT and discarded by the owner. Raw codec error integers are
not forwarded as backend IO/UNCERTAIN. Actual read/storage errors still propagate
and request stop/restoration. This distinction is fixed in SDKalpha.6/XNOWdev.11.

The matching compiled radio profile must come from the full-radio builder and
profile generator; it is not bundled in the source SDK or loaded by linking.
Read ESPNOW_FULL_STACK.md before attempting hardware work. Current offline
whole-chain results do not qualify actual MAC ACK, protected hardware admission,
original kernel/FAT power loss, sleep/USB or physical restoration. Source APIs
remain experimental rather than an ESP-IDF drop-in ABI. Existing installed chat
continues to use the earlier fixed32 transport until explicitly migrated/tested.

## Experimental managed owner

SDKalpha.5 adds espnow-owner as an explicit source service. It includes the
foreground handoff, inherited pipe/cookie adoption, cooperative owner gate,
binary owner commands/partial-stream transport, controller binding and full owner
runtime. It does not depend on espnow-message or restrict packets to chat.
For encrypted applications additionally select espnow-security and provide
explicit key and verified user-directory journal initialization.

Public headers are espnow_handoff.h, espnow_managed_process.h,
espnow_launcher_bridge.h, espnow_owner_gate.h, espnow_owner_commands.h,
espnow_owner_stream.h and espnow_owner_runtime.h. The native function/type names
are retained. This prerelease API may change; pin0.2.0-alpha.8 exactly.

The reviewed launcher must supply the inherited capability; an ordinary installed
launcher does not do that. App startup must adopt it before RF work and refuse
when absent. An80-byte launch.contract binds the managed opt-in to the verified
app executable hash. The optional launcher-review implementation is provided as
source; linking the service does not modify/install/enable that launcher.

Construct gate, controller and nonblocking stream before starting the runtime.
The exact gate supplies the controller lease; qualified original platform guards
are still mandatory. The runtime checks real stream identity and separate restore
pipe identity. Ignore SIGPIPE explicitly, keep UI/loader copies of owner-only FDs
closed, and implement prepare/close_data callbacks. Encrypted prepare must attach
all crypto operations; PN records must already exist or be provisioned in a
separate proven-fresh-key operation. No reset-on-missing/default path is provided.

Keep stepping on pending. On UI disconnect the owner drains and restores, closes
user-storage references, notifies and closes the restore writer. Uncertain state
is not exit permission. The cooperative socket, mount check, matching fingerprints
and successful notification are not original APF/USB/sleep ownership proof.
Physical full-owner qualification remains outstanding. The standalone XNOWdev.11
archive excludes these new owner objects; use this source service to link them.

Run tools/test_sdk_espnow_owner.py for a public C consumer, original-libc ARM926
execution and C++ header syntax. It tests bounded command refusal, STOP and an
anonymous-pipe handoff lifecycle without accessing the radio or user volume.
The real-process and encrypted journal/radio instruction fixtures remain separate
evidence and do not constitute a device qualification report.
