# App Market

Browse verified applications for Japanese X1000 players. Read descriptions and release notes, compare installed and available versions, then explicitly download and install. Existing Wi-Fi and correct device time are required. Update the running market through the computer package.

Build from the repository root with `tools/build_app.py store`.
See [the application specification](../../../docs/APP_SPEC.md) for the package
and runtime contracts. No device access is part of the build.

## Independent build

From the repository root, run `python tools/build_app.py store`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
