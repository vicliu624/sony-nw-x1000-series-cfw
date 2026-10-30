SDK0.2.0-alpha.8 development sources expose the physically measured encrypted
profile through espnow-security, retaining the generic management profile.
Public full/security/device consumers pass ARM926 execution with Sony libc.
Application source contracts are aligned to alpha.8; installed apps and frozen
alpha.7 packages are unchanged. No new source SDK archive is implied by this edit.

# Current status and validation scope

2026-10-30 physical encrypted TX now passes eight byte-exact nonempty
X1060-to-Cardputer payloads through 1470 bytes, using the observed ESP-IDF profile.
A second native process reused the same key and durable user-volume PN records;
the Cardputer peer remained installed. Its eight payloads also matched exactly,
with PN reservations continuing from 10241 rather than restarting at one.
Both runs completed ten MAC transmissions, exited and restored authenticated
Terminal access. Zero-length transmissions completed at MAC level but did not
produce Cardputer receive callbacks; application delivery is not supported by the tested standard peer. Bench0.1.3
fixes its null-zero callback guard but does not change that physical result;
standard IDF5.5.1 itself returns ESP_ERR_ESPNOW_ARG for a zero-length send.
This proves process-restart persistence, not arbitrary power-loss behavior.
The alpha.2 worker uses XNOWdev.14. Native encrypted RX also authenticated twelve 1470-byte packets from Cardputer;
the first decoded payload SHA-256 matched the original exactly and authenticated
Terminal access returned after stock restoration.
full encrypted bidirectional/lifecycle acceptance remains open. SDK alpha.7 is
an older source snapshot and does not yet export this physical-profile update.

Alpha.3 adds RX resume without reprovisioning. Two physical native RX processes
using one key and the retained Cardputer peer authenticated1470-byte messages;
the validated user-volume replay record advanced from19 to38. Both restored
Terminal access and first-message digests matched. This establishes receive
continuation across a native process restart, not over-air replay rejection or
power-loss safety. Alpha.3 is installed separately from the older test workers.

SDK0.2.0-alpha.7/XNOWdev.12 incorporated the plaintext-broadcast compatibility
fix and explicit receive authentication/broadcast flags. Native consumers must
be rebuilt for the extended receive structure. Host/original-libc ARM endpoint,
secure-owner and partial-pipe tests pass; no installed apps or firmware change.
Encrypted over-air interoperability and full hardware qualification remain open.
Earlier SDK release evidence below remains historical, not retagged as alpha.7.

The experimental [SDK](sdk/README.md) adds a source API, three starters and two
maintained development examples. Host/ARM fixtures and clean-bundle builds are
computer-side evidence. No new SDK hardware acceptance was performed by this
migration. Callback-profile state IO defaults to denied until ownership is
qualified; native services retain the existing app policies.
SDK publication is independent of the firmware/app release composition below.

Current SDK0.2.0-alpha.6 adds explicit espnow-owner source services, including
managed handoff, generic binary IPC and full owner runtime. The public consumer
passes original-libc ARM926 execution and C++ header syntax. This neither updates
installed apps/firmware nor qualifies full ESP-NOW hardware operation. Original
platform/APF/USB/sleep, protected hardware admission and standard encrypted peer
interoperability remain outstanding. The standalone XNOW archive remains dev.11.

A concrete crypto compatibility gap is now confirmed at the source boundary:
native management nonce10 differs from ESP-IDF's espnow software branch nonce00.
The actual S3 RF/hardware profile is not yet determined. Native MIC verification
remains enabled. Generic CCMP and journal tests do not establish encrypted ESP-NOW
interoperability; resolve this before attempting an encrypted compatibility claim.

SDK0.2 adopts the16 existing apps through native services. The user reports
successful testing of prior local builds; exact personal package identities
were not supplied. Function bodies, formats and policy are retained. Same-path
CI compares runtime and resources, with only identified non-loadable GCC file
markers normalized in memory. This is new offline evidence, not a new physical
acceptance report. ESP-NOW was excluded from that original migration.
SDK0.2.0-alpha.2 now adds optional generic ESP-NOW services separately; the
underlying XNOW library passed a bounded physical bidirectional exchange and
stock restoration. See [ESP-NOW SDK scope](sdk/ESPNOW.md).
See [native service adoption](sdk/SERVICES.md).

Baseline: VERSION 0.1.0-dev.17, Japanese 1.11 platform, one physical NW-X1060.
NW-X1050 is a target without an equivalent device report.

| Area | Established | Still unverified |
| --- | --- | --- |
| Firmware | Matching extraction, component hashes and original reconstruction | General installation/failure recovery safety |
| Root filesystem | Live 148 MiB partition, ext2 read-only root | Arbitrary new-image installation and bad-block handling |
| Native execution | Terminal UI, authenticated commands and launch credentials | Every app and all Home/USB/sleep paths |
| Terminal | Live pinned TLS, root shell, reconnect, command output/exit status | Long stress, forced-stop and full cleanup lifecycle |
| Localization | Four-pack design and offline cache tests | Candidate 12 physical sleep stability after candidate 11 incident |
| FM | Native 76-108 MHz implementation, offline checks, Si470x live binding | Exact chip ID, RF/audio and restoration on hardware |
| Wi-Fi | Existing connection, route, DNS and public ICMP | Cold-connect/helper ownership and QQ HTTPS on player |
| QQ Music | Native feature implementation complete: QR login, collections, artwork, source download, tagged MP3 import, progress/cancel and Wi-Fi/clock preparation | Continuous real-account/new-download/device conversion/import/Sony recognition/playback hardware acceptance |
| Other apps | Source and builder-specific offline checks | App-specific hardware qualification |

The physical clock was observed in January 2008. The terminal's exact pin does not
qualify ordinary HTTPS certificate dates. Latest QQ work includes Cookie/HTTP
compatibility and manual retry handling; an old service response is not a permanent
diagnosis. Do not rotate identities or import cookies to evade unexplained errors.

Source-based CI now builds an experimental firmware profile, fourteen app packages
and an explicit GitHub Release repository snapshot. See RELEASES.md for publishing
and prerequisites. These are computer-side builds: no firmware was flashed or new
hardware qualification inferred from old reports.

## Application cohesion

Project version 0.1.0-dev.21 gives all sixteen maintained apps local metadata,
artwork, versions and build entries. tools/build_app.py is the shared entry point;
public release composition uses it too. All sixteen completed offline ARM builds
and full-package inventory/resource checks during migration. The launcher review
version is 0.1.0-dev.19 and consumes external presentation.bin. Unknown-ID rendering,
malformed/link/FIFO fallback, metadata and native market list/version checks pass.
See APP_SPEC.md for commands, formats and the generic remote-icon limitation.
No device was accessed or firmware built for this maintenance.
