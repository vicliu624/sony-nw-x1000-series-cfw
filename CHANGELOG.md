# Changelog

## 0.1.0-dev.21 application and QQ Music update

- Give all sixteen maintained apps local metadata, artwork, versions and builders.
- Discover and package apps through tools/build_app.py; release builds reuse it.
- Read bounded external launcher presentation instead of compiling per-ID icons.
- Keep store entry code with its app and reuse shared package/network adapters.
- Document the native application contract and verify complete package inventories.
- Update QQ Music to 0.1.1-alpha.3 with artwork thumbnails and conversion progress;
  keep the experimental audio-preview adapter opt-in.
- No device deployment or firmware qualification is implied by these changes.

## Unreleased maintenance

- Group native apps under runtime/apps/<application> and update builders/fixtures.
- Consolidate English platform, build and app guides; preserve old notes locally.
- Ignore scratch, local packages, compositions and private generated evidence.

## 0.1.0-dev.17 development state

- Candidate 12 uses a process-owned language cache; sleep stability is unverified.
- WiFi Terminal supports real authenticated root-shell commands on the test unit.
- Live read-only work establishes mounts, selected drivers and launch credentials.
- Pocket FM implements 76-108 MHz; RF/audio qualification remains outstanding.
- QQ Music contains native network/login/import components, with real-account
  completion and device/time/lifecycle/playback checks still outstanding.

Earlier detailed logs are local history, not a hardware-qualified release record.
No public release is created by this maintenance.
