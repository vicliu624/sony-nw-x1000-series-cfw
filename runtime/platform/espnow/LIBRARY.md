# XNOW experimental native library

Source library for Japanese Sony NW-X1000 JP1.11, built for ARMv5TE soft-float
and the project's pinned Sony-libc/old-kernel profile. It is not a complete or
hardware-qualified ESP-NOW SDK. No driver/radio image is installed by linking
the library, and no Sony shared library or game ROM is included in this output.

## Local build

Run runtime/platform/espnow/build_library.py on Linux/WSL from the project root.
It requires the matching local Sony libraries, compiled radio bridge/header and
the current candidate under work/espnow-radio-candidate-poll-filter. The builder
verifies library hashes and candidate/payload consistency; it never downloads,
deploys or contacts devices. Prepare those analysis inputs using the project RF
guide before building. This is a local development profile, not a new release CI.

Output: work/espnow-native-library/<VERSION>/sdk, containing include/, lib/libxnow.a,
an example with no device access and build.json. The version belongs to this
library; it is separate from Sony1.11, the chat app and Cardputer firmware.

The build links both a minimal consumer and a whole-archive consumer with the
pinned original libraries, and runs both under ARM926 QEMU. Whole-archive linkage
checks dependency resolution; the example never invokes device operations.
C++ header/C-symbol compatibility is checked with a host C++11 consumer. The
report explicitly records whether an ARM C++ compiler was used. No current
build test establishes physical RF timing. A separate physical test of the
0.1.0-dev.8 archive passed bidirectional96-byte messages with application ACKs
and stock Wi-Fi restoration; see [validation scope](VALIDATION.md).

## Interfaces

Include xnow.h or an individual header. Public C functions have C++ linkage
guards. Compile/link with the matching Sony profile, not a modern system libc
or another Walkman model's binaries. No C++ runtime is supplied by this library.

| Header | Interface | Important boundary |
| --- | --- | --- |
| xnow_frame.h | Payload encode/decode | Byte framing, no RF IO |
| xnow_chat.h | Fragmentation, retry, application ACK |96-byte text, one outstanding message, bounded RAM |
| xnow_mailbox.h | Word-IO publication and receive snapshot | Serialized caller; latest snapshot can be overwritten |
| xnow_sd8686.h | Matching-driver adapter, channel and wake | Requires qualified bridge; SET paths require matching session actions |
| xnow_session.h | Startup/restore action sequencing | Policy only; executor must complete/drain each action |
| xnow_manager.h | Original connection-manager client | Blocking; use one controller process, retain client through restore |
| xnow_loader_job.h | Guarded child jobs | No default guard; no automatic use from chat |
| xnow_rf_init.h | Original RF initialization arguments | Original root tools/config must be verified; no NVP-write operation |
| xnow_file_check.h | Exact hash/size/path/device checks | Does not establish mount or USB authority |
| xnow_control.h | Dispatch manager, worker and verification actions | One owner process; mandatory radio/IPC guards; no UI-thread use |

The library requires the exact bridge code embedded in its generated identity
guard. build.json records the matching radio candidate and payload hashes. An
older candidate will fail the native adapter's guard. Do not disable the guard
to make different artifacts appear compatible.

## Results and lifecycle

Mailbox publication, radio queue acceptance and peer application ACK are three
different results. A negative/uncertain publication is not permission to submit
again blindly. Chat timeout means unconfirmed; a published request can remain
pending and transmit on a later peer poll. Exact polling heartbeats clock TX
without replacing an unread message snapshot.

The current launcher may SIGKILL an unreaped app group after about2 seconds.
Radio restore is not qualified inside that window. Do not enable automatic
candidate loading in an ordinary app until shutdown coordination, user-volume,
USB/IPC ownership and recovery behavior have been qualified. Root init tools
remain blocking operations; a zero tool exit is not independent RF calibration
proof. All app persistence must stay on verified visible user storage.

The public structs and development version are not a stable binary ABI. Rebuild
applications against the same source/header profile. Keep original images and
known-running rollback files separate from current generated candidates.

## Owner controller

Version0.1.0-dev.2 adds xnow_control: init with explicit channel/disconnect policy
and caller-provided radio/IPC guards, then step in one owning process. It connects
the session policy to original-manager APIs, guarded worker jobs, candidate code
validation, RF initialization and channel readback. stop invalidates the mailbox
immediately and requests restoration after any in-flight job drains. Poll until
finished; inspect session.failure even when DONE. A failed restoration retains
the client for explicit retry; unknown worker/manager ownership is not a clean
finish and cannot be reset/retried blindly. Do not call these APIs from a signal
handler or reset an active controller with init.

Stock verification checks the original four-block layout and SHA-256 of276
stable code/layout bytes, including the pool initializer and callback. It is not
complete radio-RAM attestation. Independent original-file and ownership checks
remain necessary. No production guard, UI-owner IPC or launcher-shutdown fix is
provided by linking the controller. Its platform effects are modeled in the
controller unit tests; original-manager FIFO tests exercise the real dispatcher
and unchanged Sony libraries/daemon instructions, with radio effects modeled.

Version0.1.0-dev.3 corrects runtime fingerprinting: the original radio reclaims
its boot-only scatter table, so comparing that table with its download-image
bytes falsely rejected an original running radio. Original11e0/11f4 execution
reproduces the clearing. The corrected stable-code digest remains derived from
the pinned original image, not accepted from a device sample. The read-only
stock check, channel GET and pool GET passed on the X1060; loading, channel SET,
native app RX/TX and restoration were not qualified at that version. The later
0.1.0-dev.8 physical result is documented in VALIDATION.md.

Version0.1.0-dev.4 restores from the official current-connection snapshot instead
of selecting saved defaults via NULL. The1004-byte opaque value is captured
before any disconnect, retained only in owner RAM, passed unchanged to the stock
connect API and wiped before release. Capture failure prevents disconnect.
Never serialize manager/controller structs: the snapshot can contain secrets.
The later stock-only and candidate tests passed current-config reconnect on
hardware. This does not establish arbitrary lifecycle or sleep/USB safety.

##0.1.0-dev.9 development scope

Adds xnow_wire.h/.c, a standard plaintext ESP-NOW v1/v2 body/MAC codec independent
of XNOW headers and chat. Host sanitizers and original-libc ARM926 tests pass.
The existing radio adapter/ABI is unchanged and still limited to32-byte XNOW
packets. New codec size constants do not make the deployed transport larger.
The word-command hook experiment is not linked into the old radio image.
See ../../../docs/ESPNOW_FULL_STACK.md. The identified0.1.0-dev.8 physical report
remains scoped to that original archive; it is not relabeled for this version.

##0.1.0-dev.11 receive error separation

Security-adapter plaintext decode errors normalize to XNOW_SECURITY_FORMAT.
They must not escape as wire error integers that collide with backend IO or
uncertainty. Malformed remote datagrams are discarded; actual transport/storage
failure still propagates. The real-runtime regression covers malformed IE/version
then valid unknown plaintext, encrypted1470 TX/RX, restart/replay and injected IO
failure. No physical operation is qualified by these computer-side checks.

##0.1.0-dev.10 full native source scope

The archive now includes the variable-length backend/endpoint, peer table,
CCMP/security/PN/file components, local key vault, bounded full driver and full
controller. Selecting a header does not select a radio image or establish USB/
exclusive ownership. Full use remains experimental and physically unqualified.
The standalone builder also requires the hash-pinned BearSSL0.6 source/build
from SDK setup --services. Consumers extracting crypto objects must link that
separate ARM libbearssl.a before the original libc. Its license/dependency is
not a Sony binary. Old fixed32 calls and their known-running profile are kept.

The full controller requires an externally verified generated profile and real
platform guards. It never provides a default valid lease or claims the known
chat acceptance report qualifies encrypted v1/v2. See docs/ESPNOW_FULL_STACK.md
for source addresses, test coverage and unverified physical boundaries.
