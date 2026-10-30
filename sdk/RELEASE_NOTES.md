# X1000 SDK0.2.0-alpha.8 (development)

Exposes the explicit measured ESP-NOW CCMP profile through espnow-security:
`xnow_endpoint_security_attach_espnow`, `xnow_security_init_espnow` and the
profile-specific CCMP/wire-key helpers. The generic management profile remains
unchanged. Context structures changed; rebuild consumers. XNOW is dev.14.
Fresh counter scopes use effective wire keys; never reset records for a used key.
Physical encrypted TX/RX and process continuation have separate local evidence;
this SDK version does not qualify all lifecycle, replay or power-loss scenarios.
Older source archives remain unchanged. No installed application is replaced by
updating these source contracts.

# X1000 SDK0.2.0-alpha.7 (development)

Fixes reception of plaintext broadcasts from encrypted-unicast peers, including
the unattached-security path. Adds BROADCAST and AUTHENTICATED receive flags;
authentication is set only after successful CCMP/replay processing and state
commit. Broadcasts are never authenticated by peer membership. XNR1 uses its
previously reserved offset24 for flags while retaining its32-byte header.

This changes the native receive structure ABI: rebuild every consumer with the
matching source/headers/library. XNOW advances to0.1.0-dev.12. Existing alpha.6
archives are retained unchanged; installed apps and radio/firmware are not updated.
The actual Espressif encrypted RF profile and full hardware qualification remain
unresolved. Source SDK publication does not certify encrypted interoperability.

# X1000 SDK0.2.0-alpha.6 (development)

Fixes malformed plaintext handling when the endpoint security adapter is attached.
Raw wire errors overlapped backend IO/UNCERTAIN values, so a rejected plaintext
datagram could stop an otherwise healthy owner. Decode failures now return
XNOW_SECURITY_FORMAT and follow the datagram-discard path. Actual transport IO
still requests stop/restoration. Valid unknown plaintext remains accepted.

Actual runtime regression tests reproduce the pre-fix failure and cover malformed
IE/version discard, following valid plaintext, encrypted1470-byte TX/RX, durable
restart/replay and injected real IO failure under host sanitizers/ARM926/Sony libc.
XNOW archive version advances to0.1.0-dev.11 for this implementation change.
SDK dependency contracts advance; alpha.5 artifacts remain unchanged. No installed
app, radio image or firmware is updated, and physical qualification is pending.

# X1000 SDK0.2.0-alpha.5 (development)

Adds optional espnow-owner source services: managed foreground handoff, inherited
capability adoption, cooperative gate, binary owner commands, partial pipe IO,
controller binding and the full owner runtime. Applications can send arbitrary
binary data; chat is not selected or required. Security remains a separate module.
Selecting/linking this module never starts radio operations or provisions keys.

This source API is experimental. Mandatory platform/storage guards still need
device qualification; no ownership claim follows from a mount, socket or lock.
Legacy launchers do not supply the managed capability: apps must refuse RF work
when it is absent. The opt-in launcher review is not installed by this release.
The standalone XNOWdev.10 archive is unchanged and does not export these new owner
objects; use the source SDK service for them. Existing19 app dependency contracts
advance without rebuilding or replacing installed apps. Root firmware VERSION
and images remain unchanged. No publication or deployment is performed.

# X1000 SDK0.2.0-alpha.4 (development)

Adds optional espnow-full, espnow-security and espnow-full-device services;
existing fixed32-byte services remain available. Full services expose binary
v1/v2 payloads, peers, endpoint polling, CCMP/PN/replay/local key-vault modules
and an experimental exact-profile driver/controller. Crypto is separate from
HTTP and chat. XNOW archive version advances to0.1.0-dev.10 and now includes
implementations for the full headers it packages. BearSSL remains an explicit
separately acquired dependency; app packages include its notice when linked.

Public ARM926/original-libc consumers exercise core/security functions without
opening a device. Whole guarded encrypted/file-journal/radio instruction chains
are separate offline evidence. No device, installed app or firmware is updated;
physical encrypted interoperability and actual USB/exclusive-owner integration
remain incomplete. Selecting/linking a module never automatically loads a radio
image or disconnects Wi-Fi. Source contracts advance to the new SDK prerelease.

# X1000 SDK0.2.0-alpha.3 (development)

Adds public espnow_wire.h standard plaintext v1/v2 encoding and decoding, with
binary/zero-length data and250/1470-byte protocol bounds. Existing device mailbox
capacity remains32 bytes. Full-stack radio, encrypted interoperability and queue
work are incomplete. No deployed application, driver or firmware was replaced.

# X1000 SDK0.2.0-alpha.2

- Adds optional espnow-core, espnow-message and espnow-device native services,
  public forwarding headers and ARM/Sony-libc consumer tests. XNOW remains experimental0.1.0-dev.8.
- Generated radio identity is built from included C/linker sources only when the
  device module is selected. Setup extracts pinned libcnmgr locally; Sony binaries
  and radio images remain excluded from the source archive.
- No firmware or installed app is updated. Existing SDK dependency pins advance;
  the original16-app migration baseline remains a separate historical check.
- A previous native XNOW worker passed physical bidirectional96-byte messages
  and stock restoration. SDK aggregation tests are offline and do not qualify
  touchscreen lifecycle, sleep, USB, throughput or another device model.

See docs/sdk/ESPNOW.md for module selection and hardware boundaries.

# X1000 SDK0.2.0-alpha.1

Existing-application adoption and native service APIs for Japanese NW-X1050/
NW-X1060, JP1.11. SDK identity remains separate from firmware/app versions.

- The16 existing apps bind compilation to the SDK and import its public native
  services. Their own main, UI, controls, state formats, resources, protocols
  and cleanup retain the original implementation.
- Adds23 selectable service modules: display/touch, original signal providers,
  files/ABI, volumes, Unicode BMP fonts, PNG/JPEG, networking, processes,
  PCM/FM models, package services and read-only system information.
- Custom-main declarative builds and existing complex recipes are supported.
  Existing apps retain their exact ordered compiler arguments and link order.
- SDK setup prepares pinned original libraries and public source dependencies.
  Independent clients build from the source ZIP, including individual modules.
- The callback/SDL starter profile remains available for new small apps.

The migration gate rebuilds old/new source at the same path with the same inputs
and compares all16 runtime/resource payloads. Only proven GCC ccXXXXXX.o STT_FILE
names outside allocated/program-load ranges are normalized in memory. No code,
data, resource, version, size, other symbol or actual inventory is waived/edited.
Raw hashes and marker records remain visible. Optional QQ playback components
run existing host/ARM fixtures without inventing a personal delivery profile.
ESP-NOW in-progress work is explicitly excluded.

This release is source only. No app/firmware update or device installation is
performed by the toolkit. Original releases and rollback inputs remain intact.
Do not republish changed raw inventories under an existing app version. No Sony
binary, original libc, account state, music, ROM or saved state is included.

The user reports previous local apps passed on their unit; exact personal
package identities were not supplied. This migration has no new physical RF,
audio, USB or sleep acceptance. Native services preserve existing storage policy;
the callback profile still denies state IO until ownership is independently
established. Start with docs/sdk/README.md and docs/sdk/SERVICES.md.
