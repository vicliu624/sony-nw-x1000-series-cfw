# Current status

Target: Japanese NW-X1050/NW-X1060, based on Sony 1.11. International NWZ-X
firmware and other Walkman families are comparison material only.

The working tree is **0.1.0-dev.37**; SDK source is **0.2.0-alpha.13**.
The experimental native radio archive source is **0.1.0-dev.22**. Its per-link key
negotiation is connected to the opt-in Root owner and Core2 alpha.29 adapters.
The matching diagnostic has established a link and delivered authenticated
player state on hardware; it is not a new public SDK module.
Dev.36 adds opt-in FRM1 packet transactions within the same 1,900-byte radio
reservation. Native code connected to original MCU instructions uses eight
commands for a representative request/reply/completion, compared with 41 for
BLK2 and 148 for BLK1. Two fragments retain the full 1,536-byte protected body
limit. Lost submit replies close admission and reconcile only scoped cancellation
and completion, without resending data. FIFO framing and bounded negotiation/SEND
fairness remain part of the source contract.
The checked reservation uses 1,896 of 1,900 bytes. TX release claims preserve
completion across packet-address reuse, and queue rejection cancels tracking
before original free. Instruction preemption replay covers both boundaries;
physical IRQ/DMA and shared lifecycle qualification remain outstanding.
Dev.37 applies the same release ownership to scalar, BLK1 and BLK2 profiles.
Their common packet queue interface cancels tracking before rejection free;
only the callback holding the release claim can publish completion.
The local dev.37 `frame-01` package has UPG SHA-256
`7b4f35a46dde9cc4f3bbd9faa76101b17f70f82f9d25de0867daae5c5eca7f32`.
The user reports that Wireless Remote cannot be enabled. This candidate is
withdrawn from further testing; its direct startup failure has not been located.
The actual dev.34 and dev.37 UPGs have identical installer, kernel, initrd,
original player payload and menu resources. Six root files differ. The
startup wrapper has identical ELF program headers and segment data; only its
symbol string table differs. The player DSO, Remote service and owner have
changed code. The supervisor has changed embedded owner/service identities,
and the SD8686 image changes from the bulk profile to FRM1. The owner and
service sizes and hashes embedded in each supervisor match the executable
files in its own UPG. This was a combined host, service and radio update.
The host and service receipts both record the changed `xnow_client.c`.
Comparing the packages does not identify the failed startup stage.
The same radio image and SDK archive now pass a shared-controller startup replay
under Sony libc and the selected MCU instructions. It covers modeled manager
states 2, 3 and 4 and a rejected FRM1 marker. Root/USB admission, physical wake,
receive membership and the actual failing Settings attempt remain outside this
replay. See [offline checks](REGRESSION.md#groups).
Runtime changes and new candidates are on hold pending cause/architecture review.
The 1 Mbps application target remains unmeasured; see
[performance](reference/ESPNOW_PERFORMANCE.md).
The user reports installing the dev.34 diagnostic. Core2 alpha.30 established
visible artwork on hardware; alpha.31 supplied mode-write UI, and alpha.32 is
the current application-only timing diagnostic. Its stored binding/channel are
retained. No additional X1060 image was installed for this timing work.
Dev.34 adds source-level Play Mode writes, explicit command negotiation and
bounded bulk packet IO. The local composition, complete allocation model and
independent extraction pass, together with 104 immutable offline regressions,
157 unit checks and exact radio-image checks on the 52f5438 source baseline.
The controller timing addition has its own build and physical measurements.
Mode changes and lifecycle acceptance of the new composition are still pending. The mode composition
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
visible artwork. Play Mode writes are unsupported in that earlier control
path. Cover throughput there was about 1.3 KiB/s;
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
The user reports installation and the matched controller receives the new mode
write capability. A 131,872-byte cached image completed in 46.358 seconds with
normal drawing and 46.229 seconds with progress redraws suppressed, about
2.8 KiB/s. Mean request-to-Core2-radio-arrival time is about 351 ms per data
reply; Core2 queue delay averages 5.6 ms. This isolates the dominant wait before
Core2 processing, not pure RF or X1060 ioctl time. The complete backend replay
still counts 148 radio commands per representative request/reply/completion,
excluding extra polls and GUI RPC. See [artwork](apps/REMOTE_ARTWORK.md).
Mode changes, sleep and USB behavior remain physical acceptance items.

## Feature status

| Area | Established behavior | Remaining work |
| --- | --- | --- |
| Stock startup, Settings, Homebrew | The user reports `native-ipc-01` installed and Homebrew entry/exit are much faster; timing was not measured. Earlier Settings, English, Graphics and one-HOME passes are separate evidence | Confirm current Settings/app launch/one-HOME behavior and repeated cold startup |
| Localization | Original Japanese and completed English/Chinese text paths are implemented | Recheck sleep/wake and every installed language with the final composition |
| External apps | Source SDK, launcher, package validation, native application builds and external storage layout are implemented | Check the complete installed app set after lifecycle changes |
| Developer SDK architecture | All 36 public service modules and their implementation/header dependency graph are independent of app source; private stock Settings callbacks/layout have a separate platform module | Consumer-specific native composition still needs review; callback device persistence needs qualified ownership, and a general managed task API is not provided; see [delivery gaps](ARCHITECTURE.md#developer-delivery-gaps) |
| Ordinary Wi-Fi handoff | On `native-ipc-01`, the user reports no Wi-Fi drop through Homebrew entry/exit; the diagnostic uses retained mode0/command6. The Remote trial explicitly used Wi-Fi on without a router | Confirm association/data continuity and sleep/wake separately; enabled radio alone is not an IP connection |
| Remote pairing | Selection-based Core2 pairing and persisted bindings have worked on the test unit | Retain binding across service restart, USB and sleep in the final composition |
| Remote controls | The user confirmed basic controls on the earlier matched profile; the installed dev.34 profile advertises typed five-mode writes through the original native request/settings order with explicit command negotiation | Physically qualify all five mode changes and restart behavior; old journals remain unchanged |
| Remote artwork | Cover display works. Two Core2 alpha.32 reads of the same cached 131,872-byte image take about 46 seconds, with/without progress redraws, about 2.8 KiB/s; final decode is about 0.34 seconds. The 150 ms pacing and 120-second cutoff fixes remain | Reduce the X1060 control-command overhead; isolate live ioctl/RF times. Another track returned source I/O and needs separate investigation |
| Quiet remote sessions | Current sender emits no heartbeat; Core2 has no periodic reconnect or quiet-session expiry | Confirm interaction-driven recovery with the final hardware composition |
| Packet IO | Installed dev.34 transfers artwork at about 2.8 KiB/s. Offline BLK2 costs 41 complete-path commands; FRM1 costs eight in the native/MCU replay and retains the 1,500-byte command boundary and full packet limits | Measure actual command/PHY timing, qualify the final shared composition and physical lifecycle; no physical FRM1 throughput result exists |
| Sleep and recovery | Native observer tests retain qualified wake entry/completion during a pending transition, defer rearm until stable, and reject recovery after exit | Physical screen-off, suspend and wake timing remain unqualified |
| USB after remote use | `shared-rx-02` hung after confirmed Remote Off. Actual Root stop functions plus the full controller reproduce a source bug: endpoint drain can execute manager RELEASE before the outer receive/sleep cleanup runs. Dev.19 yields at this transition; host/ARM tests pass connected/unassociated, channel-change and cleanup-failure paths | Physical USB recovery remains unverified. New retirement summaries need a fresh diagnostic seed; the old occupied-slot trace does not describe the failed trial |
| Root capacity | The dev.37 frame layout adds 648 KiB in an ordinary 148 MiB ext2 model using Sony's formatter, with about 27.08 MiB nonreserved margin; full content and inode metadata readback pass | This model does not explain the reported Remote startup failure. Actual NAND geometry, installation and recovery remain unqualified; see [system footprint](SYSTEM_FOOTPRINT.md) |
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
