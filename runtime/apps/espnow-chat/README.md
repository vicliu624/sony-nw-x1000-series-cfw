# ESP-NOW Chat (local candidate)

Current source is dev.3, a local managed-launch review candidate. It refuses RF
startup without the launcher's inherited handoff capability. A dedicated writer
passes to the detached owner, which notifies restoration only after its controller
finishes and user-storage access is closed. Premature event EOF is repair state,
not completion. One owner session is allowed per launch. The builder emits an
app-hash-bound launch.contract and deployable=false. Do not install this candidate
until hardware lifecycle checks pass. Actual client/owner host fork/exec through
the managed launcher now survives UI forced-kill with delayed restoration and
retains foreground on owner crash. Its volume/radio/cnmgr boundaries are modeled,
so this is not player/APF qualification. Actual ARM launcher contract/catalog
checks pass for the dev.3 files, including wrong-hash rejection.
The physically identified installed app and the acceptance history below are
dev.2; this development work has not changed the player.

Native C touch interface for Japanese X1000 and the original Cardputer. Version
0.1.0-dev.2 uses the public SDK and an independent radio-owner executable.
The UI and owner exchange bounded messages through unnamed RAM pipes. History,
drafts and ordinary owner state are RAM-only; no ordinary chat journal is saved.
App files and the separately verified radio candidate live on user storage.

The underlying XNOW0.1.0-dev.8 native lab passed physical bidirectional96-byte
messages and stock restoration. The new touchscreen owner path is a separate
candidate: offline pipe/duplicate-owner tests pass. The exact UI client/owner
transport also passed physical bidirectional96-byte messages, independent process
group checks, pipe-EOF restoration and owner reaping. The user subsequently
reported that Chat testing passed. That report is not a complete HOME/sleep/USB
test matrix. No TCP/UDP fallback is used for chat messages.

Connect original Wi-Fi before opening. The owner captures its configuration,
loads the user-storage radio image, sets channel8 and reports READY. Closing the
only UI command writer requests stock restoration. The owner has a separate
process group so the ordinary launcher timeout does not kill it with the UI.
A Linux abstract socket prevents duplicate chat owners without a socket file.
The UI's Back arrow waits for normal completion; HOME/termination can close the
UI first while the owner continues restoration. Failure/uncertain ownership is
retained for inspection rather than killed or retried on a timer. Do not assume
sleep/USB/force-reset safety from normal-session tests.

The SDK capability is general-purpose: this app selects the optional message
helper. Other applications can use raw binary transport without chat semantics.
See ../../platform/espnow/VALIDATION.md and ../../../docs/sdk/ESPNOW.md.

The on-demand keyboard uses stock-inspired 60x44 telephone keys. Tap the draft
to edit; repeated taps cycle a group, RIGHT/SET or a short pause commits a
character. OK accepts the draft and CANCEL preserves the previous draft. The
keyboard stays hidden while reading messages. It has no predictive dictionary.
The conversation uses left/right message bubbles, confirmation state and a
compact composer. Drag the history vertically to review retained messages;
the header back arrow returns to apps and the refresh icon checks radio state.
The touch keyboard currently enters ASCII. The protocol preserves UTF-8 bytes,
but the bundled preview font is an ASCII subset. Messages up to96 bytes use
fragment confirmation, retry and duplicate suppression. A missing ACK means
unconfirmed, not proof the peer did not receive the message.

Build the radio prototype header first, then this local package:

```
.venv/bin/python runtime/platform/espnow/build_radio_bridge.py
.venv/bin/python runtime/apps/espnow-chat/build.py
```

Outputs and previews are under work/espnow-chat-app. --help, --version,
--selftest, --render-preview and --render-keyboard-preview do not open devices.
The default entry opens display/touch
through the existing native adapter. Never run that entry concurrently with
WiFi Terminal's foreground display. The back arrow/HOME release the resources.

The builder now compiles/links the shared libxnow.a and records its archive and
source fingerprints. It requires the matching local poll-filter radio candidate
and original library inputs documented by the experimental native library guide.
It does not install that candidate or enable the incomplete session controller.

See ../../../docs/RF_HARDWARE.md for the current implementation and limits.
