# QQ Music: implementation and device guidance

Source: runtime/apps/qqmusic. Goal: independent native QR login, own-account
collections, authorized new source download, native conversion/tagging, publication
on user storage and recognition/playback through the original player. A public QR
or a synthetic import is not the complete goal.

## Existing components

- Bounded JSON/HTTP/Cookie/session/login/catalog/resource processing.
- QIMEI/anonymous GetSession preparation before the sustained login flow.
- c-ares DNS, nonblocking TCP/address fallback, BearSSL TLS1.2 with host/CA/date
  validation, bounded HTTP and streaming media transport.
- Native QMC/Vorbis/Shine conversion, MP3/ID3/cover handling and output validation.
- Verified-volume workspace, reserve planning, staging/journal/publication,
  background worker and UI progress/cancellation.
- Separate original-cnmgr Wi-Fi helper and parent callbacks, plus diagnostics.

Use tools/build_qqmusic_native.py with an explicit non-account profile and fresh
work output. Optional device-full composition is not a hardware-ready claim.
Do not ship synthetic identities or test CAs. Do not import another client's
cookies/cache or repeatedly issue fresh QR codes to avoid debugging later stages.

## Wi-Fi findings and priorities

The physical existing connection uses eth0. Default route/DNS and a public ICMP
reply work. resolv.conf follows the original RAM-backed configuration. INPUT DROP
does not require an inbound exception for this outbound client; do not copy the
terminal's TCP2323 rule into QQ networking.

The observed physical date is January2008. hb_tls_current_time reads that clock;
network.c supplies it to certificate validation and request handling. The UI
clock path also uses it. First add a clear date/precondition diagnostic and a
trusted time policy; do not disable verification or trust an unauthenticated
HTTP Date. An app-local time basis must cover TLS, Cookies, signatures and media
consistently, not just one function.

program_config has ensure/cancel/release network callbacks, and program/media
workers have integration points. At the reviewed baseline main.c did not bind
them. Existing modules are not the same as completed production startup wiring.
Keep the original already-connected hotspot as the first device HTTPS baseline;
then qualify and bind cold-connect handling.

The helper avoids blocking the UI and drains original requests before fin. Its
original library handles across fork/concurrent cancellation, shared ownership
and blocking close still need physical validation. A45-second parent preparation
deadline does not prove that drain/reap finishes within45 seconds. Do not force
kill a controller and immediately finalize an outstanding original transaction.

Keep failures distinguishable: no address/route, DNS, TCP, clock/certificate, HTTP
and service/authentication. Existing diagnostic structures support this direction.
Network errors should not universally discard authorization and require a new QR.

## Storage, memory and playback

All account/session state, QR images, source files, covers, MP3s, journals and
partials must stay on verified user storage, with no system/tmp fallback. Disable
crash dumps containing account RAM. Do not trigger stock library refresh until
its /db and user-storage write destinations are audited.

Linux-visible RAM is about44.8MiB with no swap. Measure simultaneous control TLS,
artwork, decoder and encoder peaks. A64MiB source/128MiB MP3 disk-space budget is
not allocation of that amount of RAM. Use streaming and bounded workers; retained
cache memory is not all unreclaimable memory.

The current product chain is download/convert/import, not already-qualified ALSA
online playback. The device reports no ALSA soundcard but does expose stock OSS/
custom nodes; playback must follow separately verified Sony paths.

## Validation boundary

Computer ARM/live-service and synthetic tests cover individual protocol and import
steps. Real-account login/new download, actual file format, device throughput,
publication, Sony recognition and playback must form a continuous evidence chain.
Later Cookie/HTTP retry work does not establish that entire chain. State current
results, not old server errors as permanent diagnoses.

No account login, new QR, device QQ deployment or system modification was performed
as part of the Wi-Fi/code review or repository reorganization.
