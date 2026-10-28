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
