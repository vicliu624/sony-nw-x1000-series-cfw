# X1000 SDK

Experimental native C development kit for Japanese Sony NW-X1050/NW-X1060,
JP1.11. Start with the [quick start](../docs/sdk/README.md),
[API reference](../docs/sdk/API.md) and [validation scope](../docs/sdk/VALIDATION.md).

SDK VERSION is independent of firmware VERSION and each application's VERSION.
Read VERSION for the current development identity: source API1 plus native services. Pin its exact
version in the app contract. No cross-model/shared-library binary ABI is promised.

Public headers are in include/x1000. Implementation remains shared under
runtime/platform/sdk and reuses native/store adapters. Templates are under
templates; callback examples are runtime/apps/sdk-counter and sdk-canvas.
The16 existing apps adopt the [native service layer](../docs/sdk/SERVICES.md)
while retaining their main, UI and policy. The optional [ESP-NOW services](../docs/sdk/ESPNOW.md) expose the tested XNOW
core and explicit device lifecycle without automatically changing radio state.
The unreleased [player-client service](../docs/sdk/PLAYER_CLIENT.md) exposes
controls, state polling and media browsing through a local original-player service.
Its native service bootstrap is not installed by the SDK.
Development examples are not additions
to the firmware release allowlist.

Use tools/sdk.py to create, build, preview, render or package apps. tools/build_app.py
also discovers generated applications through their local build.py. Neither
command installs anything or changes the firmware. Python runs on the computer.

Source archives include only explicit source/data inputs. Sony libc and the
loader are extracted locally from a hash-pinned updater; they are never bundled.
The new SDK facade/templates/tools have the MIT notice in LICENSE. Reused project
adapters retain their source notices; the existing Noto raster retains SIL OFL1.1.
