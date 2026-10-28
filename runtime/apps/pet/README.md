# BSOD Pet

Native C companion for Japanese X1000. See the [application guide](../../../docs/apps/PET.md)
for installation, interaction, build and verification boundaries. The local manual-test
package requires an existing working Homebrew launcher; no firmware change is needed.

Builder: tools/build_pet.py. Packager: tools/package_pet.py.
Artwork remains a local input. Physical app qualification is pending.

## Independent build

From the repository root, run `python tools/build_app.py pet`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.
