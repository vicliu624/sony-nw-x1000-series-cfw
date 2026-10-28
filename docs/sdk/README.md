# X1000 SDK quick start

Build a touch application without changing the firmware, launcher or official
release composition. Target: Japanese NW-X1050/NW-X1060, JP1.11 only. This is an
experimental source SDK. Computer tests are not device qualification.

## 1. Prepare a Linux/WSL development environment

Supported baseline: Ubuntu24.04, Python3.12, Node is not needed for native apps.

```sh
sudo apt-get update
sudo apt-get install gcc gcc-arm-linux-gnueabi binutils-arm-linux-gnueabi libc6-dev-armel-cross qemu-user p7zip-full libsdl2-dev python3-venv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r sdk/requirements.txt
python tools/sdk.py setup
python tools/sdk.py doctor
```

Run all commands from the checkout or extracted SDK root. setup downloads the
exact Japanese updater recorded in sources/downloads.json if missing, validates
its hash, decrypts the pinned container and extracts only libc/loader locally.
It never executes Sony's updater or writes a device. If the recorded server is
unavailable, obtain the exact original independently and use
`python tools/sdk.py setup --stock-exe /path/to/NW-X1000_V1_11.exe`.
No other model's libraries or arbitrary sysroot is a substitute. Existing
matching inputs are preserved. Original binaries stay under ignored local paths.

Host-only preview needs gcc, SDL2 and the Python dependencies; it does not need
the Sony updater or ARM toolchain. doctor reports the full development profile,
so its missing ARM/input rows do not mean host rendering is unavailable.

## 2. Create an application

```sh
python tools/sdk.py new my-counter --template touch-ui --title "My Counter"
```

This creates runtime/apps/my-counter with main.c, app.json, build.json, build.py,
VERSION, README.md and neutral original placeholder PNG/SVG artwork. Use your own
icon and metadata before sharing. A deployed application ID is stable. Creating
an app does not modify the launcher, a global ID list or config/release.json.

Three templates are available:

| Template | Behavior |
| --- | --- |
| minimal | Text, a Back button and clean exit, no persistent state |
| touch-ui | Touch counter, settings API and visible unavailable-storage state |
| canvas-game | Clipped canvas, timed motion and a Back button |

build.json pins the SDK version and the app/canvas/storage profile. Applications
own their VERSION. Changed installed bytes require a higher SemVer precedence.
Keep app title/metadata ASCII for the current native market renderer; a website
translation does not make the native text renderer Unicode-capable.

## 3. Preview and test

```sh
python tools/sdk.py preview my-counter --data
python tools/sdk.py render my-counter --data --output work/counter-frame
```

The preview is a PC SDL2 window (WSLg or a Linux graphical session). Click/touch
with the left mouse button. Escape/Home/window close exits. --data selects an
isolated PC-only directory under that preview output. No host path is accepted
by the device executable. The same C application, canvas and event handlers run
in preview and ARM builds; display/input/storage backends differ.

Headless render produces frame.ppm and frame.png. A script allows reproducible
interaction without any window or physical device:

```text
tap 60 215
tick 32
```

Save it in work/events.txt and run:

```sh
python tools/sdk.py render my-counter --data --events work/events.txt --output work/counter-tapped
```

Supported lines: tap/down/move/up followed by x y (240x432), tick followed by
0..1000 milliseconds, and home/usb/stop/fault. Scripts are bounded to10000 lines.
The last rendered frame is retained. In an interactive preview, actual SDL
elapsed time is used. A preview session's settings stay in its printed output
directory. Creating another preview output starts with separate state.

## 4. Build and verify the ARM package

```sh
python tools/sdk.py build my-counter --output work/my-counter-build
python tools/verify_app_package.py work/my-counter-build/package
python tools/sdk.py package my-counter --from-package work/my-counter-build/package
```

Outputs must be fresh work/ or dist/ paths. Existing outputs are refused, not
deleted. The build compiles ARMv5TE soft-float code, checks the original loader
and libc hashes, validates the ELF dependencies/interpreter, and runs safe help,
version and metadata-selftest entries under QEMU. --selftest is deliberately a
safe metadata check, not a complete business-logic test or hardware acceptance.
Reports carry source hashes outside the package. No physical app entry is run.

The ZIP uses HOMEBREW/apps/my-counter with app.ini API1, the ARM app, rich metadata,
presentation, artwork and complete file inventory. It also provisions an empty
HOMEBREW/data/my-counter directory outside the replaceable program. It does not
contain settings, account data, Sony libraries or a firmware image. The .sha256
sidecar checks integrity, not publisher authenticity. Review the package before
copying files using the project's existing storage/deployment procedures.

The existing app entry point also works:

```sh
python tools/build_app.py my-counter --build-output work/my-counter-native --output work/my-counter-package
```

## Storage boundary

Device state belongs only under /contents/HOMEBREW/data/my-counter. The SDK
validates the actual vfat/mtdblock2 mount, directory identity, links, free space
and a caller-provided ownership lease before file operations. State is limited
to flat safe names and64KiB files; resource reads are limited to1MiB. Writes use
an exclusive temporary file, sync and rename, with an explicit uncertain result.

**The stock profile does not yet establish exclusive USB ownership.** Its
default provider is unknown, so device state/resource IO returns an ownership
error. The counter still works in memory and shows Storage unavailable. Host
preview demonstrates real isolated persistence. An advanced integrator can
provide a qualified original-platform ownership callback; an always-true callback,
an unplug assertion, flock or a masked USB query is not evidence of exclusivity.
No template bypasses this gate. This is an explicit capability limit, not a
promise that all device storage/lifecycle paths are solved.

See [API reference](API.md), [validation](VALIDATION.md) and
[contributing an app](PUBLISHING.md) before extending or distributing applications.
