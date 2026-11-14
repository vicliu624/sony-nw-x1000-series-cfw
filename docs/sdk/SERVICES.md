# Native C services

Use the `native-services` profile when an application needs its own C `main`,
event loop, renderer, codecs or networking. Select modules in `app.json` and
include their public headers under `x1000/services/`. The compiler resolves
dependencies from `sdk/services.json`.

For a generated touch application with a managed drawing loop, use the
[callback templates](README.md). Native-service applications own acquisition,
cancellation and cleanup. Player and radio access require a separately
authorized platform session; importing a module does not create one.
See the [lifecycle contract](LIFECYCLE.md).

## Choose modules

Header names below are relative to `x1000/services/`. The manifest contains
the complete export list. Existing C names and structures, including `hb_*`,
`fm_*`, `dx_*` and `qq_image_*`, remain the public interfaces.

| Need | Modules | Main headers or guide |
| --- | --- | --- |
| Original-libc program entry | `startup` | Supplies the ARM entry; define C `main` |
| Display and touch | `display` | `display.h`, `touch.h`, `device_io.h` |
| Stop observation | `signals-libc`, `termination` | `stop.h`, `termination.h` |
| Files and stock ABI structures | `files`, `abi` | `files.h`, `stat.h`, `stat_layout.h`, `abi.h` |
| Hashing | `hash` | `sha256.h` |
| Parent/child processes | `process` | `process.h`, `child.h` |
| Monotonic deadlines | `clock-libc` or `clock-oabi` | `clock.h`; select one provider |
| Small text and list presentation | `font5x7`, `list-ui` | `font5x7.h`, `list_ui.h`, `noto_ascii.h`, `presentation.h` |
| Mount and free-space preflight | `volume` | `volume.h`, `volume_policy.h`; [storage contract](../../runtime/platform/storage/README.md) |
| Bitmap fonts and dictionary data | `bitmap-font`, `lexicon` | `bitmap_font.h`, `lexicon.h`; [text contract](../../runtime/platform/text/README.md) |
| PNG/JPEG/RGB565 conversion | `images` | `images.h`; [image contract](../../runtime/platform/images/README.md) |
| PCM output and routing | `pcm`, `audio-route` | `pcm.h`, `audio_route.h`; [audio contract](../../runtime/platform/audio/README.md) |
| FM receiver and restoration | `fm` | `fm_model.h`, `fm_tuner.h`, `fm_session.h`, `fm_native.h`; [FM contract](../../runtime/platform/fm/README.md) |
| Device information | `system-info` | `system_info.h` |
| DNS, sockets, HTTPS and downloads | `network` | `dns.h`, `connect.h`, `socket.h`, `tls_stream.h`, `tls_platform.h`, `https.h`, `download_stream.h` |
| Catalog and package installation | `packages` | `market.h`, `repository.h`, `package_app.h`, `package_platform.h` |
| Original-player client | `player-client`, optionally `player-managed-client` | [Player client](PLAYER_CLIENT.md) |
| ESP-NOW transport and encryption | Select required `espnow-*` modules | [ESP-NOW services](ESPNOW.md) |

`unicode-font` remains a compatibility aggregate of `bitmap-font` and `lexicon`.
New applications can select either reader independently. Select one signal
provider and one clock provider within each executable.

## Configure and build

Prepare development inputs once from the checkout or extracted SDK root:

```sh
python tools/sdk.py setup --services
```

Setup checks the pinned Sony libraries and obtains public codec/TLS build inputs.
Sony binaries remain local and are excluded from app and SDK packages.

Create an application with the [quick start](README.md), keep its generated
metadata/artwork, and replace the callback program with a normal C `main`.
Set this `sdk` field in `app.json`:

```json
"sdk": {
  "version": "0.2.0-alpha.13",
  "profile": "native-services",
  "modules": ["startup", "display", "signals-libc", "abi", "hash"]
}
```

Pin the exact value from `sdk/VERSION`. This example targets current source
alpha.13; an extracted alpha.8 SDK needs its own pin. The app's `VERSION` is
independent.

Use this declarative `build.json` and keep the generated `build.py`:

```json
{
  "profile": "native-services",
  "sources": ["main.c"],
  "checks": [["--help"], ["--version"], ["--selftest"]]
}
```

Implement these CLI entries so they finish without opening hardware, network
accounts or application state. Then build and verify:

```sh
python tools/sdk.py build my-app --output work/my-app-build
python tools/verify_app_package.py work/my-app-build/package
```

The compiler uses ARMv5TE soft-float code, the original Sony loader/libc and
the selected safe QEMU checks. Choose a fresh output directory for every build.
Native-service apps use their own host/ARM fixture or render entry points;
generic SDL preview belongs to the callback profile.

Existing apps with ordered custom recipes retain their app-local builder
through `sdk_services.compiler`. The SDK CLI forwards their explicit profile,
sprite, device and audio-preview options. See the app's guide for those inputs.

## Resource ownership

Acquire resources only while the application or supplied session owns them.
Keep live handles in one owner, observe stop requests, drain pending work and
complete cleanup before returning control. Propagate uncertain or failed
restoration results. A socket close alone does not establish hardware retirement.

- `volume` provides read-only mount/space checks. The caller still coordinates
  USB access and file publication; account and import policy stay in the app.
- `images` requires serialized calls and nonoverlapping buffers. Its contract
  defines per-operation memory and image limits.
- Font and lexicon readers own their loaded buffer or stream. Qualify resource
  paths before opening and close a context before reusing it.
- `system-info` provides read-only diagnostic pages. Serialize `hb_info_collect`
  because it uses shared scratch storage. `hb_info_stock_space` uses the JP1.11
  statfs ABI; it is not a portable host query or an update-safety check.
- Networking requires trust anchors, hostname validation and valid TLS time.
  Player and ESP-NOW capabilities have independent lifetimes.

There is no public generic background-task registration API. The private Sony
Settings integration is firmware code, separate from an ordinary app.

## Verification and distribution

Run the [SDK checks](VALIDATION.md) against the exact source or extracted archive
being distributed. Current app builds check modules, safe CLI entries and package
contents. Historical byte-equivalence checks have a separate scope described
there.

Changed installed bytes require an app version increment. Packages keep mutable
state outside replaceable program files and exclude credentials and Sony
libraries. Display, RF/audio, USB, sleep and restoration require physical
acceptance; see [project status](../STATUS.md).
