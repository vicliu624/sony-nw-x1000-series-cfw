# Game Boy Color

A native Game Boy and Game Boy Color emulator integration. Supply your own compatible game files on visible storage; no ROMs or personal saves are included. Consult the emulator guide for controls, compatibility and validation limits.

Build from the repository root with `tools/build_app.py gbc`.
See [the application specification](../../../docs/APP_SPEC.md) for the package
and runtime contracts. No device access is part of the build.

## Independent build

From the repository root, run `python tools/build_app.py gbc`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
