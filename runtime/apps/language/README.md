# Language (legacy)

This external language-pack switcher is retained for older firmware profiles.
Current firmware uses the original Settings language selector and built-in
resources. This app is no longer included in release catalogs or player setup
packages. Keep the source and old evidence for compatibility research; do not
install it as part of the current profile. See the
[localization guide](../../../docs/LOCALIZATION.md).

## Independent build

From the repository root, run `python tools/build_app.py language`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
