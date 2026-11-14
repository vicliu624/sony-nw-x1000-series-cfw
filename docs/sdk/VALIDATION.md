# SDK validation and capability limits

Generated validation projects belong under `work/`, including source and failure
evidence. `sdk.py --apps-root work/<sources>` selects an isolated source catalog
for declarative SDK templates and native-service recipes. It does not change
the maintained `runtime/apps` catalog, release allowlist or device storage:

```sh
python tools/sdk.py --apps-root work/sdk-examples new sample --template minimal
python tools/sdk.py --apps-root work/sdk-examples build sample --output work/sample-build
```

Build output must also be fresh and below `work/`. Explicit source roots reject
symlinks and paths outside `work/`; an unknown app never falls back to the formal
catalog. Nondeclarative application builders retain their regular build path.

Current SDK source is **0.2.0-alpha.10**. The published source SDK is
**0.2.0-alpha.8**. Build and validation receipts identify the exact source or
archive they checked; publication, offline validation and device acceptance
are separate results.

The SDK supports foreground callback applications and explicit native-service
clients on the Japanese 1.11 platform. It does not provide a general persistent
task manager or automatically grant access to Sony's player or radio.

## Offline coverage

| Area | Executed checks | Scope |
| --- | --- | --- |
| Callback lifecycle | Success, partial open, failed init/input/present/close, cancellation, finish and SIGTERM observed inside a callback | Host and ARM with the original loader/libc and synthetic display ports |
| Graphics and input | Clipping, invalid text/image inputs, button drag/release, SDL window/texture/present and synthetic mouse events | Host renderer and dummy SDL video driver |
| Storage | Bounded save/load, missing state, ownership loss, symlink/hardlink/FIFO rejection, stale temporary files and uncertain publication | Dedicated PC directories; device persistence remains denied without qualified ownership |
| Storage cancellation | Stop during ownership callback, pending backend stop, provider/context replacement and real SIGTERM | Host file publication and original-libc ARM admission; no device writes |
| Native services | Aggregate external client and an independent link for every selected module | ARM926 with original libc; missing dependencies cannot hide behind another module's link inputs |
| Text modules | Font-only, lexicon-only, legacy aggregate, include-order and C/C++ consumers | Separate font/query links and compatible public declarations |
| Player client | Explicit descriptor adoption, grants, generation, bounded requests, events, close and refusal paths | Supplied service fixtures; no automatic authorization or reconnect |
| ESP-NOW | Core/message/device/full/owner clients, malformed frame rejection, following valid traffic, encryption and bounded handoff/STOP | Host sanitizers and original-libc ARM clients; RF is modeled |
| Clean source bundle | Manifest/path/hash checks, original-input setup, three generated templates, previews, ARM builds, packages and public service clients | Fresh extracted project without copied local build outputs or installed apps |

Device tests remain necessary for display/touch restoration, physical radio,
audio, power consumption, USB ownership and suspend/wake. The current physical
acceptance state belongs in [project status](../STATUS.md), not in an SDK test
count. Earlier component-level RF exchanges do not qualify the complete current
firmware or every SDK consumer.

## Reproducing the checks

On Linux/WSL, prepare the pinned original inputs with `python tools/sdk.py setup
--services`, then run:

```sh
python tools/test_firmware_regressions.py --suite sdk
```

For a source delivery, create a new archive under `dist/` and test that archive:

```sh
python tools/package_sdk.py --output dist/sdk/review-source.zip
python tools/test_sdk_bundle.py dist/sdk/review-source.zip \
  --stock-exe firmware/original/NW-X1000_V1_11.exe
```

Use a fresh output name; the packager refuses to overwrite an existing archive.
The bundle test checks every file against its manifest, prepares dependencies
from the pinned updater, generates minimal/touch-ui/canvas-game apps, renders
them on the host, builds ARM packages and exercises the service matrix. Original
Sony binaries remain local and are not included in the source ZIP.

The `--player-only` bundle option is a narrower client check. Its report must not
be described as a full SDK validation. None of these commands flashes firmware,
connects to a player or accesses a real account.

## Application compatibility

Current application builds and historical equivalence answer different questions.
The current-build matrix checks the declared SDK modules, safe entry points and
package inventory. It does not prove an unchanged application or installed-device
behavior.

Historical comparisons use an immutable pre-SDK source baseline and the same
build path. Only independently identified nonloaded GCC temporary file markers
may be normalized; raw hashes and normalization records remain separate. Source
splits require their own caller/ABI and output comparisons rather than a claim
that the original file remained unchanged. See [native services](SERVICES.md).

## Runtime limits

- The callback device storage provider defaults to unknown ownership. Apps must
  not bypass that denial with an always-successful ownership callback.
- A managed player client consumes an authorized session; it cannot grant one
  to itself. Closing its socket is not proof of server or hardware retirement.
- ESP-NOW and player control have independent lifetimes. Private Remote Settings
  integration is not a public registration or background-task API.
- A successful preview or generic QEMU run establishes software behavior for its
  supplied ports. It does not establish native driver compatibility, installation
  safety or recovery.
