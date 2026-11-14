# hello

Native application sources. See [application guide](../../../docs/apps/DIAGNOSTICS.md).

## Independent build

From the repository root, prepare the pinned original libraries with
`python tools/sdk.py setup`, then run `python tools/build_app.py hello`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
