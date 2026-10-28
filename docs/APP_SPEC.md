# Native application specification

This specification targets Japanese Sony NW-X1050/NW-X1060 on the verified 1.11
platform. It is not an ABI guarantee for other Walkman families. Device programs
are C/C++ with necessary ARM assembly. Build-time Python runs on the computer only.

## Ownership and discovery

An application's source, metadata, artwork and app-specific build implementation
belong under runtime/apps/<id>. Public platform adapters stay in runtime/native,
runtime/platform and runtime/store. Do not add ID switches or app-specific artwork
or descriptions to the launcher. A release allowlist is publication policy, not
application discovery. Shared emulator engines may be reused by separate app entries.

Required application-local inputs:

- app.json: schema 1, immutable id, target, title, summary, description, changes,
  channel and build definition.
- VERSION: independent SemVer. Changed installed bytes require a higher version;
  build metadata alone does not make a new version.
- assets/icon.png: transparent 64 x 64 RGBA source artwork. assets/icon.svg is an
  optional editable original; preserve attribution and licenses.
- C/C++ sources and headers; build.py for complex application-specific builds.
- README.md describing dependencies, controls, persistent files and offline checks.

The current app_registry.py discovers */app.json; it has no list of application
IDs. The artwork field used by the original project's artwork regeneration tool
is optional design input, not a device interface or a requirement for a new app.

IDs contain 1-32 lowercase ASCII letters, digits or hyphens, begin with a
letter/digit and equal the application directory name. Target is always
sony-nw-x1000-jp for this specification. Example app.json (use your own artwork):

```json
{
  "schema": 1,
  "id": "my-example",
  "target": "sony-nw-x1000-jp",
  "title": "My Example",
  "summary": "A native example",
  "description": "What this app does and what it requires.",
  "changes": "First experimental build.",
  "channel": "experimental",
  "build": {
    "script": "build.py",
    "package": "work/app-builds/my-example/package"
  }
}
```

For a small console example, a complete build.json can be:

```json
{
  "sources": [
    "main.c",
    "@/runtime/store/start.c",
    "@/runtime/store/start.S"
  ],
  "checks": [["--help"], ["--version"]]
}
```

Implement those safe CLI options in main.c and use HB_BUILD_VERSION for the
compiled version. Graphics/input apps also list the shared native device,
frontend and stop adapters; see the key-check recipe for an existing example.

## Presentation metadata

The title is 1-48 printable ASCII characters; summary 1-96; description 1-640;
changes 1-384. Channel is stable or experimental. These limits match the current
native market text renderer. This does not restrict language inside an app that
implements its own text rendering. Do not put credentials in metadata.

The release builder derives app-info.json and presentation.bin from the local
definition. Do not maintain a second hand-edited copy in a global config file.
Source icon.png/icon.svg are included for inspection. Presentation resources must
be added before computing files.sha256.

presentation.bin is exactly 2746 bytes:

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | ASCII HBART001 |
| 8 | 49 | Printable ASCII title followed by NUL padding |
| 57 | 97 | Printable ASCII summary followed by NUL padding |
| 154 | 2592 | 36 x 36 little-endian RGB565 pixels, row-major |

Pixel zero means transparent. The PC converter maps opaque black to 1. This keeps
the device renderer small and avoids a PNG/SVG decoder in the launcher. Strings
must contain a terminator and zero padding. Invalid sizes, magic, strings, links
and non-seekable resources fall back to generic presentation. The launcher reads
only a fixed bounded resource; it does not interpret paths or code from this file.
Presentation validation is not package authenticity. The installer must verify
catalog hashes and the complete inventory before publishing an application.

## Installed application

The directory is HOMEBREW/apps/<id> on verified exposed user storage. Keep the
existing API1 app.ini exactly compatible: api, id, name, version, target, exec,
bytes and sha256. Target is sony-nw-x1000-jp and exec is app. Do not add unknown
manifest keys; optional presentation is a separate file.

files.sha256 starts with HBFILES1 and lists SHA-256, byte count and relative path
for every package file except itself. Reject linked inputs, duplicate/unsafe paths
and unbounded payloads. Inventory includes app.ini, executable, presentation,
resources and license notices. Generated app-info.json contains the deployed
version and presentation metadata. Never include ROMs, private identities,
account/session data, saved games or installation-specific state in public apps.

## Runtime contract

Use the existing original-libc startup, ARMv5TE/soft-float build and pinned Sony
loader. Reuse verified file/stat/time/signal bridges. Modern r7+svc0 syscalls and
modern time64 layouts are not compatible substitutes for Sony's OABI contracts.
Do not call fixed SpiderApp addresses from independent applications.

Only one foreground owner may access display/touch. Reuse shared device and
termination adapters. HOME/stop/USB cancellation must close owned resources and
return through the existing launcher/application manager path. Return from main
is not proof of complete hardware restoration. Keep safe --help/--version and
appropriate --selftest paths free from device and account actions.

Persistent state belongs on verified user storage, outside replaceable package
payload when needed. Validate mount identity, USB ownership, free space and links.
Never fall back to system paths, raw flash, NVP or system-backed temporary storage.
Keep logs/caches bounded and installation transactional. Preserve original updater,
kernel and initrd behavior; app development does not require new firmware builds.

## Required verification

Check app-local metadata and versions; build ARM code from current sources;
exercise safe entry points under the pinned original loader; test package
inventory and unknown-ID discovery. Exercise malformed/missing presentation and
cleanup failures. Run tools/check_repository_layout.py after source moves.
Report source hashes and distinguish host/QEMU checks from physical qualification.
Never relabel old build or visual reports after sources move.

## Computer-side commands

Run from the repository root in Linux/WSL with the documented toolchain:

```sh
.venv/bin/python tools/build_app.py --list
.venv/bin/python tools/build_app.py device-info --output work/my-device-info
.venv/bin/python tools/build_app.py hello --output work/my-hello
```

The command discovers app.json and invokes its local build.py. The build.package
field identifies the builder's package tree; build.executable defaults to app.
A single_executable recipe copies only its executable, not objects, logs or private
build profiles. Additional resources and notices are explicitly listed in package_files; each
entry maps a repository-relative source to an installed relative destination.
Do not copy a build directory wholesale when it contains profiles or logs.
Existing individual tools/build_<name>.py entry points remain compatibility
wrappers. Application-specific CLI options are forwarded to the local builder.
Use a new output directory; packaging does not overwrite a previous candidate.

The --package-from option skips compilation and packages an explicitly selected
fresh build tree. It is useful during migration, but does not establish build
provenance or runtime qualification by itself. Do not feed old release artifacts
to a clean-source release workflow.

## Declarative native builds

A simple application can use the shared native_app_build.build function from its
local build.py. Its build.json owns sources (relative to the application, or @/
for a shared repository source), cflags, libraries, ldflags, library_paths and
safe checks. The helper supplies the verified original-libc startup conventions;
include runtime/store/start.c and start.S in the recipe. Complex builds may use a
local Python build.py on the computer. Neither form ships Python to the player.

Example app-local build.py:

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from native_app_build import build
if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
```

Start from the hello C source and the diagnostics/key-check declarative recipe,
replace the local entry source, and supply your app.json, VERSION and artwork.
Do not edit app_registry.py, the launcher or a global icon list. Only add an ID to
config/release.json when intentionally publishing it through this repository.

For builders with configurable output, --build-output selects their temporary
work directory; --output selects the finished app package. build.output_suffix
locates the package below that builder directory. QQ Music additionally requires
an explicit public installation profile and --device-full --public-installation.
Pet requires --sprites pointing to a locally supplied sprite sheet. Private art,
ROMs, accounts and personal keys are not release prerequisites or public inputs.

Validate a finished package with:

```sh
.venv/bin/python tools/verify_app_package.py work/my-device-info
```

## Compatibility and limits

Maintained applications have app-local definitions and build entries. The SDK
counter/canvas examples use the same discovery and package contract; they are
not additions to the official release allowlist. See [SDK](sdk/README.md).
Release composition calls the same packaging entry point, retaining the explicit
public allowlist. Shared emulator implementation remains shared; gbc and
tamagotchi-id each own an entry, build flags, version and artwork.

Launcher 0.1.0-dev.19 is required for external presentation. Older launchers can
still launch API1 packages but retain their old compiled artwork. The market uses
catalog metadata and generic artwork before remote payload download; automatic
remote icon preview fetching is not implemented. This does not require a per-ID
registry or prevent independent application packages. There is no new device
firmware, system storage write or on-device Python requirement in this change.

Offline builds, inventories and ARM fixtures do not establish physical hardware,
USB, sleep or original-player return qualification. Preserve those separate test
boundaries when distributing an application.
