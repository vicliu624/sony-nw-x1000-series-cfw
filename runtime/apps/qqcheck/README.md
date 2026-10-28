# QQ Startup Check

Native startup diagnostic for QQ Music. No account data is included.

Build from the repository root with `tools/build_app.py qqcheck`.
See [the application specification](../../../docs/APP_SPEC.md) for the package
and runtime contracts. No device access is part of the build.

## Independent build

From the repository root, run `python tools/build_app.py qqcheck`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
