# Sharing and submitting an SDK application

Build a fresh package with tools/sdk.py and verify it with verify_app_package.py.
Use tools/sdk.py package to create a computer-download ZIP with exact
HOMEBREW/apps/<id> layout and an empty state directory outside the application.
Retain the SHA-256 sidecar and the builder's source-hash report. Never attach
Sony libraries, firmware, ROMs, save seeds, private identities, music or account
state. An application does not require a new firmware build.

Before sharing, replace placeholder artwork, document controls, dependencies,
state paths and limitations, retain dependency notices, and select a unique
stable ID. Increment the app version for any installed-byte change. Review
downgrade/state compatibility explicitly; SemVer does not migrate save files.

Generated apps are discovered locally without launcher/global-ID edits. They do
not automatically enter the official firmware/app release allowlist or website
catalog. Request an upstream review with source, a reproducible recipe, license
notices, offline reports and an honest per-model hardware-status statement.
Maintainers intentionally update config/release.json after reviewing a release
candidate. File hashes verify integrity, not publisher trust or sandboxing.

SDK source releases use sdk-v<SDK VERSION>, independently of firmware v<VERSION>.
The SDK workflow builds/tests from clean inputs before publishing an experimental
source-only release. It does not publish application ZIPs or firmware packages.
Root firmware VERSION and existing app versions are not changed by SDK releases.

The SDK release gate is its own exact-commit verification job: callback/service
checks, public ESP-NOW core/full/security/device/owner consumers and a clean
source-archive extraction/build. Historical application migration equivalence
remains a separate diagnostic, not a release prerequisite after applications
intentionally change their own logic or versions. A successful SDK release does
not publish or certify those application payloads or a new firmware image.
