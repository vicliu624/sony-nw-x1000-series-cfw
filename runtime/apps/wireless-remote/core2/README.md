# Core2 remote target

Core2 with Faces Bottom3 and Gamepad3 replaces Cardputer as the intended remote.
Cardputer remains a retained interoperability test peer, not the final UI target.
Reference hardware is the local aprs-weave project; that project is read-only
reference material and is not modified by this port.

The reference stack is Core2 v1.3, optional M144 Configuration A, Faces Bottom3,
and Gamepad3. This remote needs display, touch, Gamepad and ESP-NOW. It does not
start the M144 codec, APRS audio, PTT, SD logging or APRS networking. Optional
hardware presence must not turn on those unrelated functions.

Reference dependencies are pioarduino55.03.33, M5Unified0.2.11, M5GFX0.2.32 and
M5Faces commit28188e1820113a2caf1c21b3a948f574f3e535fe. Use M5Unified's board
mapping and M5.In_I2C, not guessed GPIO numbers. The reference initializes
M5Faces_Gamepad3 at M5FACES_BOTTOM3_ADDR and100kHz. Gamepad3 and Keyboard3 share
address0x08; a scan is not model identification. Read firmware/model information
and qualify the actual panel. The reference has a firmware3 stale-sample filter
and contradictory-direction protection; do not silently discard these concerns.

## Controls

| Button | Now Playing | Lists/settings |
| --- | --- | --- |
| Up/Down | Move control focus | Move item focus |
| Left/Right | Move control focus | Move item focus |
| A | Execute focused control | Activate focused view, navigation or read-only mode explanation |
| B | Back | Back/cancel |
| Start | Focus play/pause without execution | Return to player and focus play/pause |
| Select | Cycle page | Cycle page |

Focus is gold; actual stock selection is green and is not changed by focus.
Touch controls use the same activation path. All eight buttons are used.
Play-mode display must expose all five actual stock
modes through the player SDK. Unsupported or unknown mode must be shown as such;
Select must not fabricate a local mode or send an unimplemented mode-change call.
Navigation does not send player commands. Duplicate/held skip buttons must not
repeat tracks. Command IDs, uncertainty handling, pairing and independent radio
lifecycle stay in the shared application protocol rather than the board driver.

The320x240 layout should show title, artist/album, playback state, volume, actual
play mode, connection state and a browsable library view. Touch offers the same
actions as physical keys. Playlist browsing and five-mode reading still need
native SDK completion; the UI must not imply hardware acceptance from a preview.

Core2 firmware builds successfully. Focused transport/volume controls,
Start-to-player, A/B/Select navigation and touch tabs are implemented.
The mode page now accepts authenticated WRM1 frames and highlights a valid current
selection; unknown, invalid or expired state selects nothing. X1060 publication
integration and physical acceptance remain pending. Alpha.6 integrates the
authenticated library request/reply client and a one-item metadata browser with
Tracks, Playlists and Queue views. A activates the highlighted control; playlist
Open requests its children, and B returns to the playlist view. Previous/Next
retain the provider revision; Reload requests fresh data. No view is assumed
supported: unsupported, stale, empty and timed-out results are displayed explicitly.
Alpha.7 allows a five-second reply window so the host can finish an admitted
asynchronous read. The service continues BUSY reads at100ms intervals for up to
two seconds; this does not replay radio requests or playback controls. Requests
occur on user navigation, not periodic database scanning. Late, mismatched
and old-session replies are rejected, with no automatic read retry. Receive slots
include the941-byte metadata reply. The library client passes host/stock-libc ARM
correlation and timeout tests, but actual provider semantics and Core2 rendering
still require hardware acceptance. Application version is generated from VERSION.
An already-created Arduino event loop is accepted without creating a second
loop. Physical qualification remains pending; no Core2 has been flashed.

## Session recovery

Alpha.5 sends an authenticated session challenge only after pairing and while
status is absent or stale. Attempts are spaced three seconds apart and use
platform entropy while Wi-Fi is active. A verified new session clears old
commands and mode telemetry, then waits for new status before enabling controls.
This requires a host with the session responder; it does not pair automatically
or qualify the host's managed lifecycle. Local compilation
is not physical RF acceptance.
