# X1000 SDK0.1.0-alpha.2

Fixes immediate cancellation visibility inside application callbacks:
xw_is_stopping now observes the original-libc signal token before returning to
the event loop. This is tested with actual SIGTERM delivery under the pinned
Sony loader/libc. Sample app versions increase with their changed linked bytes.
The published alpha.1 source remains immutable.

First experimental source-only developer kit for Japanese NW-X1050/NW-X1060,
JP1.11. SDK identity is independent of firmware and application versions.

- Small C facade for lifecycle, touch, canvas, proportional ASCII text, RGB565
  images, button interaction and guarded app data/resource access.
- Minimal, touch UI and canvas game templates; maintained counter/canvas examples.
- SDL2 interactive preview and headless scripted PNG rendering from the same C
  application source. Host state is isolated under work/.
- Pinned original-libc ARM builds, safe QEMU entry checks, exact package inventory
  and source-hash reports. No firmware builds or device installation.
- Clean extracted-bundle tests create, preview, ARM-build and package all templates.

The ZIP contains no Sony binary, original libc, ROM, music, account or private
state. Setup locally extracts hash-pinned libraries from the recorded Japanese
updater without executing it. Read docs/sdk/README.md after extraction.

Device USB ownership remains unresolved in the stock SDK profile. Device storage
IO fails closed until an independently qualified owner callback is supplied;
the counter otherwise keeps state only in memory. Host preview demonstrates
isolated file persistence. No physical SDK display/USB/sleep/audio qualification
is claimed. The source archive is a developer kit, not a player-installation ZIP.
