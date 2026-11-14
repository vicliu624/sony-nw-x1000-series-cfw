# Core2 controller

The controller uses M5Stack Core2 with Faces Bottom3 and Gamepad3. It displays
Sony player state, metadata, five play modes and library navigation over
ESP-NOW. Audio remains on the Walkman.

## Hardware and build

The reference stack is Core2 v1.3 with optional M144 Configuration A, Faces
Bottom3 and Gamepad3. This application uses display, touch, Gamepad and radio;
it does not start APRS audio, PTT, SD logging or an unrelated codec.

Dependencies are pinned in `platformio.ini`: pioarduino 55.03.33, M5Unified
0.2.11, M5GFX 0.2.32 and M5Faces commit
28188e1820113a2caf1c21b3a948f574f3e535fe. Board pins and I2C come from M5Unified
and `M5.In_I2C`. Gamepad3 uses `M5FACES_BOTTOM3_ADDR` at 100 kHz. Address 0x08 is
also used by Keyboard3; an I2C scan is not model identification.

`VERSION` is the controller source version. The installed controller version
and a local source version may differ. Builds are PC-side and do not upload by
default. The local builder uses Windows PlatformIO; help performs no build:

```sh
py -3 tools/build_core2_remote.py --help
```

The project uses `work/core2-platformio-packages` as its dedicated package cache.
`--packages-directory work/<other-cache>` overrides it explicitly. Isolation
avoids the pinned platform's cleanup of Arduino package variants in the shared
PlatformIO cache. Dependencies retain the same pinned versions.

For source validation while firmware packaging is paused, use
`py -3 tools/check_core2_syntax.py --database <existing-compile_commands.json>`.
It reads explicitly supplied compilation metadata and invokes the cached cross
C++ compiler with `-fsyntax-only`. It never invokes PlatformIO or regenerates the
database. A current version header is generated only inside the check's own work
directory. Cached build objects/images must remain unchanged.
Reports stay under `work/core2-syntax/`. It does not link, create an image or
access a serial port. This validates code against the actual cached M5/ESP
headers, not physical display/input/RF behavior.

`src/cover_renderer.h` owns image fit and decode into the caller's 96x96 RGB565
sprite. Transport progress and display pushes remain in the frontend. The optional
PC check in the full research checkout calls this same renderer with local M5GFX
0.2.32 sources:

```sh
python tools/check_core2_sprite.py --m5gfx-src /path/to/M5GFX/src --image /path/to/cover.jpg
```

The explicit image is optional. Synthetic JPEG/PNG, portrait/landscape, rejected
input, repeated rendering, pixel copy and surrounding-buffer preservation are
checked without a device. This does not qualify LCD, PSRAM, RF or frame timing.

Do not erase NVS during an application update: it contains pairing and channel
state. Physical uploads are a separate operation from a build.

## Interaction

| Button | Now Playing | Lists/settings |
| --- | --- | --- |
| Up/Down | Move focus | Move focus |
| Left/Right | Move focus | Move focus |
| A | Activate focused control | Activate focused item |
| B | Back | Back/cancel |
| Start | Focus play/pause without executing | Return to player and focus play/pause |
| Select | Cycle page | Cycle page |

Gold indicates focus. Green indicates the actual stock selection. Touch uses
the same activation path as buttons. Navigation never sends playback commands;
held skip controls must not repeatedly skip tracks.

The central indicator shows observed state: triangle for playing, bars for
paused, square for stopped, question mark for unknown. The associated action
uses the opposite explicit PLAY/PAUSE intent. A successful send does not toggle
the displayed state speculatively.

The mode page displays Normal, Repeat, Shuffle, Shuffle & Repeat and Repeat 1
Song only when the received mode is valid. Focus is not a mode change. Library
requests are user-driven and bounded; unsupported, stale, empty and failed
results are distinct from a populated list.

## Pairing and connection

Open Pairing on an unbound Core2, start pairing, then select it on the Walkman.
No code is typed. First pairing accepts a selected Walkman only during the
two-minute local window; discovery never replaces an existing binding. Removing
a binding requires confirmation. The Walkman's binding is separate.

Channel is configurable from 1 to 13 and is retained in NVS, subject to driver
regulatory checks. The default is 8, not a claim about the current Walkman
channel. A shared Wi-Fi radio follows its actual channel. A router is not an
ESP-NOW prerequisite.

There is no periodic heartbeat, three-second reconnect loop or thirty-second
quiet-session expiry. Boot, explicit user demand or an authenticated new
session may initiate one bounded handshake. A sent control is never replayed
after a lost receipt. A previously unsent intent may wait for fresh state.

Cached metadata is last received data. It cannot establish present radio
reachability; the UI must not label it LIVE. A failed interaction requests an
explicit connection check rather than inventing a successful control result.

Alpha.29 negotiates a fresh native encryption key for each link while retaining
the existing NVS binding. It requires the matching Root `--link-keys` build;
the earlier installed Root image is incompatible. App traffic waits for key
installation, and peer replacement waits for native TX callbacks. Pairing and
app payload formats remain unchanged. See
[link keys](../../../../docs/reference/ESPNOW_LINK_KEYS.md) for the protocol and
validation limits. Builds do not automatically update either device.

A matching receipt and a newer authenticated snapshot are independent response
evidence. PLAY/PAUSE completes only when its target state is observed. A timeout
without that target remains an unconfirmed command; when the peer has responded,
it must not clear the link or cancel a cover job as if the peer were absent.
A missing receipt leaves the sent operation uncertain, with no automatic retry.
The player coalesces a current-state refresh after explicit controls, including
idempotent controls that do not change its state.

## Artwork

Current-track JPEG/PNG is limited to 512 KiB and read in authenticated 1024-byte
chunks. It is decoded once to a 96-pixel sprite; compressed bytes and pixels use
PSRAM. A track/session change replaces the job. Missing, malformed, oversized
and failed artwork keeps the placeholder. No disk cache is used.

Successful reads are spaced by 150 ms; active controls defer new image requests.
Retries retain the request ID and may accept a valid late reply during the gap.
Old-session/track/offset and invalid authentication are rejected. Transfer
progress is retained for diagnostics when the session becomes unavailable.

Temporary missing track identity pauses a same-session job. Its bytes and
deadline survive, but replies cannot append and the cover is hidden until
identity is confirmed again. New track/session or connection revocation cancels
the context. The image client owns retries and exposes const progress; the UI
does not mutate pending requests. Cache changes return STALE and permit at most
two zero-offset restarts within the original job budget.

Authenticated correlated image/library/mode replies show peer activity without
proving that a playback command executed. They must not be discarded as link
evidence merely because a separate control receipt was lost.

## USB console

- `status`: source version, binding, channel, session, control and artwork counters.
- `connect`: request one handshake without a playback command.
- `cover-retry`: retry current artwork without changing binding.
- `channel N`: select the matching radio channel when no command is pending.
- `pair-start`: open the local pairing window.
- `unpair`: remove the saved local binding deliberately.

Console commands do not qualify a failed RF path. Read the project's
[current status](../../../../docs/STATUS.md) for hardware acceptance; complete
artwork display and current control/screen-off stability remain unresolved.

`REMOTE_RADIO` separates local send attempts/queue errors from asynchronous
wireless completion, and raw receive callbacks from size/type/queue rejection.
`tx_completed` is the driver's successful completion: unicast MAC delivery or
broadcast transmission, not application authentication or a handled request.
`REMOTE_RESUME` reports the current volatile handshake state without
printing challenges, session IDs or keys. These counters are RAM-only and are
printed on explicit `status`; they add no heartbeat, retry or persistent log.

`REMOTE_TX_FRAME` observes the fixed MAC/CCMP header exposed by the pinned
ESP-IDF send callback. It reports whether a packet number was present, along
with public frame-control/key-ID fields. The callback buffer is never retained
or printed. This is a local driver-buffer observation, not an independent air
capture or proof of receiver processing. Large-frame body length is a byte in
the vendor ABI; the observer reads at most the fixed 24-byte MAC and 8-byte IV.
