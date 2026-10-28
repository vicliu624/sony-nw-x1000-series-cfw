# Tamagotchi iD

A native Tamagotchi iD emulator integration. Supply your own compatible input files as described in the emulator guide. No ROMs or personal saves are bundled. Emulator compatibility and physical controls require separate testing.

Build from the repository root with `tools/build_app.py tamagotchi-id`.
See [the application specification](../../../docs/APP_SPEC.md) for the package
and runtime contracts. No device access is part of the build.

## Independent build

From the repository root, run `python tools/build_app.py tamagotchi-id`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
