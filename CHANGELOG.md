# Changelog

## Unreleased (0.1.0-dev.35)

- Add checked read vectors for matching shared-radio profiles, reducing a complete
  modeled request/reply/completion from 148 commands to 41. Code/state stays
  within the same 1,900-byte reservation; physical throughput remains unmeasured.
- Consume an available FIFO header and body in one bounded client/owner turn,
  with HUP checks before each read, partial I/O and one-record backpressure.
- Process queued peer negotiation before admitting a new application send,
  rechecking readiness without increasing the per-turn RX budget.
- Update source consumers to SDK alpha.12 and the native radio archive to dev.21.
  Keep the installed dev.34 package and its physical results separate.

## 0.1.0-dev.34 development changes

- Add explicit five-mode Remote controls through Sony's native request/settings
  path, with legacy-compatible SDK command negotiation and Core2 alpha.31 UI.
- Add fingerprint-qualified bulk SD8686 packet IO. Each host command is limited
  to 1,500 bytes; larger spans are split while retaining ownership and lease checks.
- Keep the user-confirmed Core2 alpha.30 artwork fix: response-paced reads,
  bounded size-based deadlines, visible progress and explicit retry.
- The reviewed new system layout adds 640 KiB over stock, 8 KiB above the earlier
  working profile, with about 27.09 MiB nonreserved margin in the PC model.
- Group native apps under runtime/apps/<application> and update builders/fixtures.
- Consolidate English platform, build and app guides; preserve old notes locally.
- Ignore scratch, local packages, compositions and private generated evidence.
- The new mode/bulk composition still requires physical acceptance. This entry
  does not create a public release or qualify RF, sleep, USB or recovery.

## 0.1.0-dev.21 application and QQ Music update

- Give all sixteen maintained apps local metadata, artwork, versions and builders.
- Discover and package apps through tools/build_app.py; release builds reuse it.
- Read bounded external launcher presentation instead of compiling per-ID icons.
- Keep store entry code with its app and reuse shared package/network adapters.
- Document the native application contract and verify complete package inventories.
- Update QQ Music to 0.1.1-alpha.3 with artwork thumbnails and conversion progress;
  keep the experimental audio-preview adapter opt-in.
- No device deployment or firmware qualification is implied by these changes.

## 0.1.0-dev.17 development state

- Candidate 12 uses a process-owned language cache; sleep stability is unverified.
- WiFi Terminal supports real authenticated root-shell commands on the test unit.
- Live read-only work establishes mounts, selected drivers and launch credentials.
- Pocket FM implements 76-108 MHz; RF/audio qualification remains outstanding.
- QQ Music contains native network/login/import components, with real-account
  completion and device/time/lifecycle/playback checks still outstanding.

Earlier detailed logs are local history, not a hardware-qualified release record.
No public release is created by this maintenance.
