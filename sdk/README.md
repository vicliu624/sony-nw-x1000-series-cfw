# X1000 SDK

Experimental native C development kit for Japanese Sony NW-X1050/NW-X1060,
JP1.11. Start with the [quick start](../docs/sdk/README.md),
[API reference](../docs/sdk/API.md) and [validation scope](../docs/sdk/VALIDATION.md).

SDK VERSION is independent of firmware VERSION and each application's VERSION.
The current profile is 0.1.0-alpha.2, source API1. Pin the exact SDK version in
build.json. No cross-model or shared-library binary ABI is promised.

Public headers are in include/x1000. Implementation remains shared under
runtime/platform/sdk and reuses native/store adapters. Templates are under
templates; two maintained consumers are runtime/apps/sdk-counter and sdk-canvas.
They are development examples, not additions to the firmware release allowlist.

Use tools/sdk.py to create, build, preview, render or package apps. tools/build_app.py
also discovers generated applications through their local build.py. Neither
command installs anything or changes the firmware. Python runs on the computer.

Source archives include only explicit source/data inputs. Sony libc and the
loader are extracted locally from a hash-pinned updater; they are never bundled.
The new SDK facade/templates/tools have the MIT notice in LICENSE. Reused project
adapters retain their source notices; the existing Noto raster retains SIL OFL1.1.
