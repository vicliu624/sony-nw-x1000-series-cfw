# Experimental ESP-NOW services

## Client-only transport

The `espnow-client` source module exports `<x1000/services/espnow_client.h>`.
It communicates with an already authorized owner through two explicitly supplied
nonblocking FIFO descriptions. It contains no driver loader, radio backend,
default endpoint or automatic activation. A system owner must supply admission,
ordinary-Wi-Fi exclusion and final hardware cleanup receipts.

Requests support peer add/modify/delete, one-peer sends and stop. Generated IDs,
partial transfers and one retained event avoid implicit replay. A queued command
ACK is distinct from TX completion and from application acknowledgement. Local
close or a stop ACK does not establish hardware power-off. Payloads are bounded
to 1470 bytes; no RSSI is fabricated. Pending key material is wiped after writing
or failure, while callers remain responsible for wiping their own key copies.

The pinned stock `libcnmgr.so.1` has a separate `cnmgr_power_off()` entry.
`tools/check_cnmgr_power_off.py` executes its ARM body with RAM-modeled IPC:
it sends request kind4 in a1020-byte request and returns the status at offset0
of the1012-byte response. Success and failure status propagation are checked.
This establishes the client protocol, not daemon transition, exclusive ownership,
physical RF power-off or standby current. Neither `cnmgr_fin()` nor disconnect
is a substitute for a qualified power-off operation. The system remote switch
still needs restoration, original manager power policy and hardware validation.

`tools/replay_cnmgr_power_off.py` executes the original daemon request handler
under12 supplied contexts. Internal states2/3 call `cnmgr_wlan_power_off`, move
to internal state0 and return success when the modeled driver succeeds. Supplied
states0/6/7/8 reject this request without that driver call. These are daemon
internal values, not public `cnmgr_get_state()` values. Client reference counts1
and2 have the same power-off behavior: a held cnmgr client is not exclusive
radio ownership. Do not use its reference count as a power-off admission check.

The low-level wrapper closes its two WLAN pipe descriptors and invokes the
stock `wlanapi.sh stop` then `wlanapi.sh unload`. Four replay cases verify that
both commands are attempted and shell failures produce wrapper error16. No
shell command actually runs in these tests. The stock unload script removes
sd8xxx, mp200_sdio, wlan_pm_register and finally wlan_pwr_ctrl, in that order.
`tools/replay_wlan_power_exit.py` replays the last module's original exit section
with RAM-backed GPIO: it calls `pwc_regulator_off(0x50806)` then performs the
original GPIO/PMU reset writes. This establishes the original power-off intent
and software path. Kernel import results are modeled; rail voltage/current and
successful physical unload remain unqualified. Production should use the
original cnmgr path after exclusive admission, not copy the raw register writes.

`xnow_power_off.c` is an optional internal platform helper, not automatically
selected by public service manifests or ordinary close. It requires the serialized
manager owner, held lease and STOPPING/RELEASE boundary. A separate callback
must return exactly1 before the original power-off API can run. Public cnmgr
state4 or transition/error states are refused; successful power-off must be
followed by state2, all four WLAN modules absent and a still-valid ownership check.
The shared read-only `platform/wireless/radio_modules.c` parser is also used by
native startup/retirement; stock script success can hide partial unload. A
reported-off manager with residual modules is uncertain too. Failures latch
manager uncertainty and retain the lease. `tools/test_xnow_power_off.py` covers
admission, reentry, repeated close, ownership loss and API/state failures with
host sanitizers and actual ARM926/stock-libc code; cnmgr/module effects are modeled.

The remote-specific adapter `runtime/apps/wireless-remote/radio_stop.c` calls
this helper after normal controller restoration and before normal RELEASE/fin.
It rejects disconnect-enabled/borrowed-Wi-Fi sessions, preserving the generic
SDK restoration behavior. The full-controller fixture tests power-off ordering,
no fin after failed power-off, retained uncertainty after fin failure and refusal
to report completion with a borrowed connection. This adapter still requires a
qualified production admission callback and integration with Settings.
`tools/build_remote_owner.py --power-off-exit` selects it in the finite lab owner
through explicit `xnow_owner_runtime_step_with_controller()` and gate stepping.
These entry points preserve stop-token/HUP revocation and actual completion
notification, without changing object layouts or default runtime behavior.
The lab admission combines its existing explicit operator assertion and gate/IPC
identity checks; it is not automatic original Sony/APF arbitration.
`tools/test_full_owner_runtime.py --power-off` exercises the full real-pipe path
with modeled driver/API effects and confirms power-off before cleanup/receipt.

## Native Settings routing analysis

The pinned JP1.11 Settings list is descriptor ID2 in the table at0x3f611c.
The stock selection callback0x950f0 is referenced at0x411350. It converts the
selected index through0x74634 and returns a native transition encoding; it is
not a driver API. Native SWD sid-050-00 maps Japanese list labels by row index.
The completed-language data profile contains Language at index10. That table
edit alone did not establish physical visibility: the user later reported only
ten entries. The former media-list adapter was rejected after the physical failure. Current
combined-host analysis changes only the Japanese Pcs descriptor count fields;
original Pcs pool/object construction now reproduces the failed count10 and
corrected count12. It is not full GUI/hardware acceptance. See LOCALIZATION.md
and KNOWLEDGE.md for the separate selection/display tables.

`tools/prepare_remote_settings_row.py` prepares a separate analysis profile:
it extends the checked RX list at0x4d8000 to12 entries, appends0xfd0000,
redirects the single selection pointer to a68-byte source-built callback at
0x4d8040 and maps label index11 to new wording ID7310. Labels are Japanese,
English, Simplified and Traditional Chinese; other native wording files use an
English fallback for this new label only. Existing text is preserved. All95
list IDs under two classifications replay with only the Japanese Settings list
changed (190 cases). Thirteen callback cases verify original argument/return
forwarding and one request for the new item. No ELF file growth or writable-data
extension is needed, and reverting the declared edits reconstructs the base.

The request anchor LR0x4d8078 falls through ordinary getpid behavior in default
hosts. The opt-in `--native-remote-settings` player-host profile now consumes it
after checking the68-byte callback, selection pointer and48-byte list hashes,
the original bound owner and non-reentry. It forwards to a bounded private
Settings request queue; no activation backend is automatically registered.
The callback replay models the stock selection boundary/delegate. A separate
anchor test executes the actual guarded shim, rejecting code/pointer/list changes
and wrong-thread requests. Queue tests execute actual admission/delivery/cancel
code with a modeled nonblocking backend. No on/off state or physical UI
acceptance is implied.
This analysis ELF/resources must not be mistaken for an installable remote
switch. The completed SDK/owner admission and explicit progress/failure UI remain
required before final firmware composition.

`tools/test_xnow_client.py` exercises the actual owner stream and client with
partial FIFO transfers under host sanitizers and original-libc ARM926 execution.
Radio operations in this test are synthetic, not physical link qualification.

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
captured-frame replay and power-loss qualification remain open. Linking never starts RF.

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

## Latest physical security observations

On the Japanese X1060/JP1.11 with the standard S3/IDF5.5.1 test peer:

- After resetting only the sender and restoring its disposable test key, the
  receiver retained its durable high-water38. It reported seven REPLAY (-23)
  rejections, subsequently authenticated five1470-byte messages and persisted
  high-water61. This tests stale packet numbers over air, not an exact byte-for-
  byte retransmission of a recorded ciphertext.
- A separate fresh-key session used a wrong peer key first: six AUTH (-22)
  rejections were followed by six authenticated1470-byte messages after the
  sender switched to the matching key. The first accepted payload digest matched.
- Both sessions completed normally and authenticated Terminal access returned.

These results supplement the published alpha.8 implementation; they do not
change its API or frozen source archive. Disposable keys and raw device logs
remain private. Cross-version peers, multi-peer load, complete original-platform
lifecycle handling and power-loss behavior remain outside this evidence.
