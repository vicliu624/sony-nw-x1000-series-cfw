# Current status and validation scope

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
| QQ Music | Native login/network/import components and bounded PC service evidence | Complete real-account/new-download/device conversion/import/playback chain |
| Other apps | Source and builder-specific offline checks | App-specific hardware qualification |

The physical clock was observed in January 2008. The terminal's exact pin does not
qualify ordinary HTTPS certificate dates. Latest QQ work includes Cookie/HTTP
compatibility and manual retry handling; an old service response is not a permanent
diagnosis. Do not rotate identities or import cookies to evade unexplained errors.

This maintenance changes computer-side organization only: no VERSION change,
device deployment, new firmware installation or claim that old hash-bound reports
validate the reorganized tree.
