# Current status and validation scope

The experimental [SDK](sdk/README.md) adds a source API, three starters and two
maintained development examples. Host/ARM fixtures and clean-bundle builds are
computer-side evidence. No new SDK hardware acceptance was performed by this
migration. Callback-profile state IO defaults to denied until ownership is
qualified; native services retain the existing app policies.
SDK publication is independent of the firmware/app release composition below.

SDK0.2 adopts the16 existing apps through native services. The user reports
successful testing of prior local builds; exact personal package identities
were not supplied. Function bodies, formats and policy are retained. Same-path
CI compares runtime and resources, with only identified non-loadable GCC file
markers normalized in memory. This is new offline evidence, not a new physical
acceptance report. ESP-NOW work is excluded by explicit user instruction.
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
