# Current status

Target: Japanese NW-X1050/NW-X1060, based on Sony 1.11. International NWZ-X
firmware and other Walkman families are comparison material only.

The working tree is **0.1.0-dev.34**; SDK source is **0.2.0-alpha.11**.
The experimental native radio archive source is **0.1.0-dev.20**. Its per-link key
negotiation is connected to the opt-in Root owner and Core2 alpha.29 adapters.
The matching diagnostic has established a link and delivered authenticated
player state on hardware; it is not a new public SDK module.
The X1060 still uses the earlier dev.19 transport. Core2 alpha.30 established
visible artwork on hardware; alpha.31 has since been application-only updated,
hash-verified and observed at startup with the stored binding/channel retained.
Dev.34 adds source-level Play Mode writes, explicit command negotiation and
bounded bulk packet IO. The local composition, complete allocation model and
independent extraction pass, together with 104 immutable offline regressions,
157 unit checks and exact radio-image checks. Physical acceptance of the new
mode/bulk composition is still pending. The mode composition
requires Core2 alpha.31 or newer.
The release baselines are firmware **v0.1.0-dev.21** and SDK
**sdk-v0.2.0-alpha.8**. A public release and the current working tree are
different configurations. Do not transfer validation claims between them.

General release packaging remains on hold. The user reports installing the
private `native-ipc-01` diagnostic, fast Homebrew entry/exit and uninterrupted
Wi-Fi through that handoff. This partial physical acceptance applies to UPG
SHA-256 `04505d749b354dd5befd8a53ebb454067ad0a74c73034cdf603050d2f119e7e5`.
The later `shared-rx-02` diagnostic (UPG SHA-256
`b17f660c5d2fcbc34ebfc2ce1dbe58e6765ab5df2b23d92b789334769f6f1814`)
still fails session establishment. USB also hung after the user confirmed Remote
Off; RESET restored USB. Core2 alpha.28 observed native CCMP TX PN1 after a paired
reboot, while every retained counter group's valid high-water maximum is at least
18. Reusing that key would be rejected by the current replay check. Fresh-link
negotiation has offline adapter, actual owner-pipe and bidirectional CCMP
coverage, but is not integrated in this installed image.
The trial used enabled, unassociated Wi-Fi; router-associated continuity,
sleep/wake and complete remote operation remain unqualified.

The local `link-retirement-03` diagnostic combines the fresh-key transport and
shared-retirement ordering fix, with Core2 alpha.29 required. The user reports
installing it, and the Core2 application update was hash-verified with existing
pairing and channel retained. The matched trial established a fresh-key link,
accepted authenticated player snapshots and began artwork transfer. The user
confirmed visible playback information and working basic controls. Core2 alpha.30
subsequently completed and decoded an 82,969-byte cover, and the user confirmed
visible artwork. Play Mode changes remain unsupported by the current control
path of the installed image. Cover throughput there remains about 1.3 KiB/s;
its radio adapter copies packet data through scalar word commands. Sleep/wake and USB retirement still
require separate acceptance.
Its UPG SHA-256 is `fdff75678168e18461216c458034125f2ff0fb5683fde1f9aad4e178c57fbf97`.
Independent Rockbox extraction, complete inventory/allocation checks and
current-source compatibility checks pass. This is prepared test material,
with partial physical acceptance, not a public release.

The new local `dev34-mode-bulk-01` diagnostic has UPG SHA-256
`6a2296898a766d957351fb13ad417da177fdddc3d0b0cf1b75ecc1a84d5fa46d`.
It pairs Core2 alpha.31 with opt-in five-mode command negotiation and the bounded
bulk radio/native adapter. The player ELF matches `link-retirement-03` byte for
byte; the startup wrapper, parent library and Remote/radio components have new
identities. Its original installation script, kernel and initrd are preserved.
The new composition has not been installed on the X1060: mode changes, actual
cover throughput, sleep and USB behavior remain physical acceptance items.

## Feature status

| Area | Established behavior | Remaining work |
| --- | --- | --- |
| Stock startup, Settings, Homebrew | The user reports `native-ipc-01` installed and Homebrew entry/exit are much faster; timing was not measured. Earlier Settings, English, Graphics and one-HOME passes are separate evidence | Confirm current Settings/app launch/one-HOME behavior and repeated cold startup |
| Localization | Original Japanese and completed English/Chinese text paths are implemented | Recheck sleep/wake and every installed language with the final composition |
| External apps | Source SDK, launcher, package validation, native application builds and external storage layout are implemented | Check the complete installed app set after lifecycle changes |
| Developer SDK architecture | All 36 public service modules and their implementation/header dependency graph are independent of app source; private stock Settings callbacks/layout have a separate platform module | Consumer-specific native composition still needs review; callback device persistence needs qualified ownership, and a general managed task API is not provided; see [delivery gaps](ARCHITECTURE.md#developer-delivery-gaps) |
| Ordinary Wi-Fi handoff | On `native-ipc-01`, the user reports no Wi-Fi drop through Homebrew entry/exit; the diagnostic uses retained mode0/command6. The Remote trial explicitly used Wi-Fi on without a router | Confirm association/data continuity and sleep/wake separately; enabled radio alone is not an IP connection |
| Remote pairing | Selection-based Core2 pairing and persisted bindings have worked on the test unit | Retain binding across service restart, USB and sleep in the final composition |
| Remote controls | The matched `link-retirement-03` trial established a fresh-key link and accepted authenticated player state; the user confirmed visible playback information and working basic controls. Source now adds typed five-mode writes through the original native request/settings order, with explicit legacy-compatible command negotiation | Installed firmware cannot change modes remotely; qualify the new composition, all five modes and restart behavior; old journals remain unchanged |
| Remote artwork | Core2 alpha.30 completed and decoded an 82,969-byte cover; the user confirmed visible display. The fixed 150 ms read pacing is removed, and size-based bounded job admission replaces the unconditional 120-second cutoff. Authentication, retry and control-priority regressions pass | Throughput remains about 1.3 KiB/s; qualify faster transfer, other image formats and source-read failures |
| Quiet remote sessions | Current sender emits no heartbeat; Core2 has no periodic reconnect or quiet-session expiry | Confirm interaction-driven recovery with the final hardware composition |
| Bulk packet IO | Actual adapter tests reduce a 1 KiB span to 21 RX / 17 TX host commands, retaining ownership/lease/ticket checks. Original instruction replay identifies the 1,500-byte request/event boundary; spans beyond 1,484 data bytes are split | Bulk radio image and native adapter are not installed or throughput-qualified; validate the complete new pair |
| Sleep and recovery | Native observer tests retain qualified wake entry/completion during a pending transition, defer rearm until stable, and reject recovery after exit | Physical screen-off, suspend and wake timing remain unqualified |
| USB after remote use | `shared-rx-02` hung after confirmed Remote Off. Actual Root stop functions plus the full controller reproduce a source bug: endpoint drain can execute manager RELEASE before the outer receive/sleep cleanup runs. Dev.19 yields at this transition; host/ARM tests pass connected/unassociated, channel-change and cleanup-failure paths | Physical USB recovery remains unverified. New retirement summaries need a fresh diagnostic seed; the old occupied-slot trace does not describe the failed trial |
| Root capacity | The new mode/bulk layout adds 640 KiB in an ordinary 148 MiB ext2 model using Sony's formatter, 8 KiB above the installed profile, with about 27.09 MiB nonreserved margin; full content and inode metadata readback pass | Actual NAND geometry, installation and recovery remain unqualified; see [system footprint](SYSTEM_FOOTPRINT.md) |
| QEMU | Original Home/Settings UI and touch run with explicit adapters; USB/NCAN models are checked against original driver instructions; original and composed players reach actual Responder entry with the explicit idle NCAN wait model | Responder stops at missing mgscsi setup; warm capture mode1/state7, complete target return, active Remote/RF, audio/DSP, Sony power management, physical USB and installation remain unqualified |

A green offline test does not resolve an outstanding hardware result in this table.

## Current maintenance contracts

- Command6 application handoff drains custom player/radio consumers while retaining a
  valid native Wi-Fi connection. Sleep drains radio ownership before its stock
  acknowledgement. USB/permanent exit uses the separate stop path.
- ESP-NOW transport and original-player control are independent capabilities.
  Wireless Remote is one system consumer, not the radio authority.
- Wi-Fi Off retires custom borrowers before Sony shutdown. Closing a remote
  consumer alone must not disconnect ordinary Wi-Fi.
- Shared discovery and encrypted endpoints acquire the same scoped native
  interface receive membership before READY. Endpoint drain precedes membership
  release, shared-sleep restoration and native-lease release. The caller-level
  omission has a failing/passing offline reproduction; physical recovery of the
  session handshake remains unverified.
- State is transmitted when changed or explicitly requested. Silence alone is
  not evidence of disconnection. A sent control with an uncertain receipt is
  never automatically repeated.
- The qualified original input wait includes current SDK IPC read/write
  interests, native wireless query/reply and boot/retirement notices, and the
  pairing-store result pipe. Queued Settings intents receive
  one immediate owner-pump turn before they have an IPC descriptor; idle pages
  retain the original wait. SDK readiness returns control to the existing owner
  pump while preserving native input; authorization deadlines and sleep gates
  remain intact. This corrects a reproduced source-level starvation case; the
  installed device symptoms still require acceptance against the new candidate.
- Owner-loop waiting remains bounded while remote children, readers or radio
  retirement need progress, including after new admission closes for exit or
  sleep. Confirmed cleanup restores Sony's timeout; this is not a radio heartbeat
  or a fabricated native retirement result.
- Pairing keys and packet-number journals remain on verified user storage.
  Current V2 journals cannot be downgraded to legacy counter values under the
  same key. Installation must preserve existing binding/counter files.
- Stock kernel, initrd and installation behavior remain unchanged. No automatic
  flashing, partition editing or live device test is part of regression checks.

## Validation

Run the maintained offline groups from the project root in the prepared WSL
virtual environment:

```sh
.venv/bin/python tools/test_firmware_regressions.py
```

Select `lifecycle`, `sdk`, `remote`, `integration`, `workers` or `layout` with
`--suite`. The separate `host` subset runs in source-only CI without Sony inputs.
The runner retains each test's log/exit status and the checked source snapshot,
and refuses an aggregate pass if source changes during the run. Routine CI pushes
do not build firmware; packaging requires an explicit manual workflow option.
Reports belong under ignored `work/firmware-regressions/`; they describe only
the tested source and environment. See [regression checks](REGRESSION.md).

## Known operational limits

- RESET and stock reflashing are not guaranteed recovery mechanisms after every
  possible failed update. There is no qualified early recovery interface.
- Windows device problem 47 means prepared for ejection; it is distinct from an
  RF fault or a damaged volume. Actual volume errors require separate evidence.
- Generic QEMU and modeled RF retirement cannot establish physical power-off,
  battery consumption, audio quality, sleep stability or USB recovery.

Read [architecture](ARCHITECTURE.md), [platform knowledge](KNOWLEDGE.md) and the
relevant [app guide](APP_DEVELOPMENT.md) before changing native bindings.
