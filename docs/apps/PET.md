# BSOD companion

A standalone native C touch companion for Japanese X1000 Homebrew. It uses the
shared original-libc startup and framebuffer/touch adapters. No firmware change,
Sony UI overlay, Python runtime or live Codex session connection is involved.

## Install and use

Copy the package's `HOMEBREW/apps/pet` folder to visible player storage. Keep app,
app.ini, files.sha256, sprites.bin, font.bin and LICENSES together. Safely eject, enter Homebrew and
select **BSOD Pet**. An existing working X1000 Homebrew installation is required.
Do not replace the launcher or run an updater. Preserve HOMEBREW/data/pet when
updating. The package does not install or modify system files.

The room focuses on a large BSOD without numeric needs or mandatory chores.

- Tap BSOD to greet/stroke it, or tap a sleeping BSOD to wake it.
- The top-right menu opens treats, play, rest/wake, help, reset and exit.
  The room has no bottom buttons; the normal exit is inside the menu.
- BACK in the menu returns to the room without choosing an action.
- Help returns to the room. Reset requires confirmation.
- The menu exit saves and returns to the app list. Save failure offers retry, leave unsaved or keep
  playing; the failure screen never traps the user.
- Physical HOME remains owned by the existing launcher. The pet does not remap or
  exclusively grab keys. The launcher stops the app and requests Sony Home.

Idle BSOD blinks, waves, tinkers with a laptop and walks left/right within bounded
space. Touch interrupts autonomous actions; reactions finish and return to idle.
Rest suppresses autonomous activity until wake. Treats and play are just for fun;
there is no hunger penalty or energy gate. Time away causes no catch-up backlog.

## Persistence and lifecycle

State stays in `/contents/HOMEBREW/data/pet/`. State-changing interactions save
immediately; a minute checkpoint preserves resting progress; explicit exit saves
again. Manager stop/HOME starts no new writes. Completed interaction saves remain,
but the uncheckpointed interval can be lost on forced termination. Save failure
leaves a persistent warning and an explicit exit can retry.

The storage adapter checks the original writable user-volume mount, pinned
directory identity, file type/link count and free space. Two alternating bounded
48-byte snapshots have checksums and temporary-file sync/rename publication. A
corrupt newest slot falls back to the other valid slot. If both are invalid,
the app starts a fresh in-memory pet with a warning. Reset or a successful later
save can establish a new snapshot. There is no system-path fallback. These guards
are not a sandbox against malicious concurrent processes.

Stop requests release graphics/touch resources and return. A stop arriving during
save prevents later publication checks, but cannot undo an already completed
rename. Original launcher lifecycle must stop the app before USB host export.
No background process, network session or growing log is created. Legacy bounded
care fields remain in the v1 wire format for decoding compatibility; they are
neither displayed nor used for starvation or interaction restrictions.

## Build

Application version: runtime/apps/pet/VERSION. Run on the computer:

```sh
python tools/prepare_pet_assets.py /path/to/bsod-v2-sheet.webp
python tools/build_pet.py --sprites work/pet-review/assets/sprites.bin
python tools/package_pet.py --build work/pet-build
```

The source sprite sheet was found in the locally installed Codex desktop app:
192x208 cells, eight columns, nine animation rows plus two look-direction rows.
The device records contain nine rows of 96x104 RGB565/alpha8 frames, rendered at
twice that size. All 2156544 sprite bytes are loaded once, not file-mapped or read
each frame. The canvas is 207360 bytes plus shared device mapping and normal
process overhead; these sizes do not measure total RSS. Artwork stays in ignored
local outputs; redistribution permission has not been established. This work does
not publish the artwork or packages.

## Verification

Offline checks cover ARM companion/autonomous logic, UI navigation, original-libc
help/version execution, virtual-touch app loop, manager stop and device open/touch/
close errors, retry/discard/continue, corrupt-slot rollback, low-space/write/sync/
rename/mount/symlink failures, renderer bounds for all nine poses and page variants
with sanitizers, and original native launcher package discovery. Rendered pages
were visually inspected. Build reports bind these results to source hashes.

Physical touch, HOME return, USB handoff, sleep/wake, speed and long-session
stability remain unverified for this app. QEMU and injected faults do not qualify
those hardware paths. First device test: greet, open/cancel the menu, play,
rest/wake, exit/re-enter to check persistence, then one HOME return. No firmware
image or updater is included in this local manual-test package.

## Chinese text (0.2.0)

The interface and fixed captions are Simplified Chinese. The XFONT1 resource is
reused from the reader/dictionary: GNU Unifont 16.0.04, OFL notices included next
to the application. Common Simplified/Traditional Han, Latin text and punctuation
are supported. This BMP bitmap does not provide full emoji or supplementary Han
coverage; unsupported code points and invalid UTF-8 have visible replacement
handling rather than silently disappearing.

runtime/apps/pet/text.c decodes UTF-8, measures actual 8/16-pixel advances, draws
16-pixel-high text, wraps within a supplied width/line count, clips to the display
and marks truncated text. Fixed translated captions are kept short for this screen.
The general text function can render mixed-language future messages, but no Codex
network bridge or task-message receiver is implemented.

Only a 64-glyph cache is held in RAM (2824 bytes on the target ABI, including
metadata and the file pointer), not the complete 2162704-byte font. The font file
is opened read-only for the foreground session and closed on every normal/stop/
open-failure path. No font file mapping is retained. Static menu/help pages redraw
on interaction, not on every poll. Room animation redraw is capped at roughly
10 Hz; that is a scheduling bound, not a measured device frame rate.

The font input is hash-pinned by the builder and all font/licenses are included in
the launcher file inventory. The player requires font.bin to launch this version;
copy the whole app directory rather than only replacing its executable. Old
0.1.0 test packages are retained and should not be mixed with 0.2.0 assets.

## Application presentation

The application ID is pet. Its title, summary, introduction and artwork live in
runtime/apps/pet/app.json and runtime/apps/pet/assets. The common package builder
creates app-info.json and presentation.bin and inventories both with the source
PNG/SVG. Launcher 0.1.0-dev.19 reads presentation.bin dynamically; changing this
app's artwork does not require recompiling the launcher. An older launcher still
uses its compiled artwork until it is replaced separately.

Pet remains excluded from public CI releases because the character sprites are a
local input. Metadata discovery does not grant a redistribution license. The
market uses catalog descriptions; uninstalled remote packages currently use a
generic icon before payload download. No ID-specific fallback table is maintained.

Use render_market_details.py --app pet with a dedicated work output to inspect
the actual ARM details painter, and render_launcher_preview.py with the new
launcher to check package-provided presentation. These are offline fixtures.
