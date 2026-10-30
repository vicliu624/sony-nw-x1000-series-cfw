# Native services and existing apps

SDK0.2 supports normal C main applications through the native-services profile.
The callback profile in app.h remains available for new small apps. Existing
apps retain their own framebuffer, event loop, state machine, renderer and policy.

## Public service contracts

Import sdk/include/x1000/services headers instead of private implementation
paths. Proven names and structures are retained: hb_devices/hb_touch, hb_dns/
hb_tls, hb_pcm, fm_*, dx_* and qq_image_*. Forwarding headers contain only a
fresh guard and the original header import. They add no runtime thunk, automatic
acquisition, allocation, packing change or new stop behavior. sdk/services.json
owns the implementation/dependency graph. Private transitive declarations do not
make superseded research entry points part of every maintained service module.

| Capability | Public headers |
| --- | --- |
| Caller-owned display/touch | display.h, touch.h, device_io.h |
| Original libc/OABI stop providers | stop.h, termination.h |
| Full-size files/directories and ABI bridges | files.h, stat.h, stat_layout.h, abi.h |
| Mount/device identity, reserve, descriptor rechecks | volume.h, volume_policy.h |
| Original tiny/Noto/UTF-8 BMP bitmap text | font5x7.h, noto_ascii.h, unicode_font.h |
| Bounded PNG/JPEG/RGB565 conversion | images.h |
| DNS, connect, deadlines, caller-verified TLS engine | dns.h, connect.h, clock.h, url.h, tls_stream.h, tls_platform.h, https.h |
| PCM, mixer, tuner and restoration models | pcm.h, audio_route.h, fm_tuner.h, fm_session.h |
| Parent/child lifetime operations | process.h, child.h |
| Maintained network market/package services | market.h, repository.h, package_canvas.h, package_platform.h |
| Read-only device information | system_info.h |
| Experimental original-player client | player.h, player_remote.h; see [client guide](PLAYER_CLIENT.md) |
| Experimental ESP-NOW | espnow.h, espnow_chat.h, espnow_mailbox.h, espnow_control.h |

These are low-level C services, not an OS sandbox or a hardware-ownership grant.
TLS still requires proper trust/hostname/time setup. Physical RF/audio, USB and
sleep qualification remain separate. Standard C/POSIX, codecs, app-specific
protocols, authentication and custom layout keep their existing responsibilities.

## Building a custom-main client

```sh
python tools/sdk.py setup --services
```

Setup obtains pinned original c-ares/librt/pthread/libm plus hash-pinned public
BearSSL/header sources. It checks both lib/ and usr/lib/ in the original updater.
Sony libraries remain local and are never included in SDK/application ZIPs.
Compiled archive hashes are recorded, not claimed identical across toolchains.

An application-local app.json can declare:

```json
"sdk": {
  "version": "0.2.0-alpha.3",
  "profile": "native-services",
  "modules": ["startup", "display", "signals-libc", "abi", "hash"]
}
```

Use sdk_build.build in build.py, with this build.json:

```json
{
  "profile": "native-services",
  "sources": ["main.c"],
  "checks": [["--help"], ["--version"], ["--selftest"]]
}
```

The shared compiler resolves services, validates the SDK/target, preserves Sony
startup and runs the selected safe QEMU entries. Select one signal and one clock
provider per declarative build. Complex existing apps bind their original ordered
recipes through sdk_services.compiler. Their CPU flags and link order remain
exact. SDK CLI forwards original profile/sprites/device-full/public-installation/
audio-preview options. A personal playback delivery profile remains explicit;
CI does not fabricate observed-device identity records to bypass its guard.
Existing-app commands run in the full repository. The lean SDK ZIP provides
shared services, starters and callback examples, not every full app's business
code/assets. New custom-main clients use it independently. These apps retain
their existing ARM render/fixture entry points; generic SDL preview belongs to
the callback profile and does not emulate Sony's OS.

## Migration and preservation

The frozen16-app scope and immutable pre-SDK commit are in
config/sdk-migration.json. ESP-NOW was excluded from that original migration.
The subsequent optional integration is described in [ESP-NOW](ESPNOW.md).
Controls, text, pixels, resources, IDs, save formats/paths, protocols, TLS checks,
ROM requirements and cleanup retain their original code. The callback API's
64KiB settings/1MiB resource limits are not imposed on these existing apps.
Their original volume/storage guards remain; no always-true lease replaces them.

This task does not republish app binaries or replace installed packages. Original
app versions remain unchanged. SDK metadata/receipts are development inputs,
outside installed app-info/app.ini/inventories. Every runtime byte and resource
must match the old build in the migration check.

Some original single-command GCC builds insert random ccXXXXXX.o STT_FILE names
in a non-allocated symbol table. Diagnostics confirmed these were the only
differences for the affected programs, with identical disassembly. The comparison
normalizes ONLY those markers outside all PT_LOAD ranges, in memory, then follows
their digest edges in app.ini/files.sha256. Actual files/inventories are never
edited. All other bytes, names, fields, sizes, versions and resources must match.
Raw hashes and the exact normalization records remain in the report. Negative
tests prove code changes, program-symbol changes and allocated/mapped strings
cannot be ignored. A later public app rebuild still needs the normal raw-hash
immutability/version checks; this comparison is not permission to overwrite an
existing version with different bytes.

The user reports previous local builds passed on their unit; exact personal
package identities were not supplied. This record is preserved without claiming
new hardware acceptance or reconstructing a personal installation. Available
local original executables were preserved under ignored work/sdk-migration.

## Verification

```sh
python tools/audit_sdk_adoption.py --check-logic
python tools/test_sdk_services.py
```

The audit checks SDK pins/imports, original metadata, unchanged function bodies
and effective include ordering, also covering conditional code with private local
profiles. The CI-only test_sdk_app_equivalence.py builds original/current source
at the SAME path with identical toolchain/inputs, reruns original app fixtures
and compares every installed file with the narrow compiler-noise rule above.
It uses public data, synthetic pet artwork
and an ephemeral test-only terminal key, never a ROM, account or personal state.
Optional QQ audio components use their existing host/ARM fixtures. An extracted
SDK builds an independent client exercising Unicode, images, networking
dependencies, PCM/FM models, large-volume planning, packages, files and processes.

Intentional future behavior changes require a new app version and a reviewed
baseline/test update. Do not loosen the frozen gate merely to pass a new build.

The original migration baseline remains fixed for fourteen apps. The intentional
pet 0.4.0-dev.1 pairing/discovery and terminal 0.1.0-dev.22 stable connection-code
updates use the immutable per-app commits in
config/sdk-migration.json for both source auditing and installed-payload
comparison. Reports record this override; it is not pre-SDK migration evidence.
