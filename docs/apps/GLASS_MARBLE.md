# Aqua Link

A calm two-screen aquarium for Japanese NW-X1060 and ESP-Mosaico: a small water
surface, gentle waves and one animated goldfish. The application ID is
`glass-marble`; device programs are native C. Python is PC-only build/test tooling.

## Mounting and controls

The supported physical mounting is Mosaico on the left (camera above, speaker
below, USB on the left) and portrait X1060 on the right. On the tested formal
Mosaico, the correct display compensation is **270 degrees**. Zero degrees was
observed sideways and 90 degrees upside down; physical user feedback confirmed
270 degrees upright with correct flow after recalibration. This is evidence from
that unit, not a universal panel-orientation guarantee for every board revision.

Hold the assembly upright and still for the first half second. Calibration waits
for a useful in-plane gravity reference when the device was booted flat; the
neutral aquarium continues animating during that wait. The BMI270 mean
specific-force vector defines the downward screen direction; it is not subtracted
as if all gravity were sensor bias. Tapping the playfield resets the scene and
re-establishes that reference. `ROTATE` cycles display orientation. `SETUP` contains
independent `FLIP X`, `FLIP Y`, and `INPUT 90` corrections for other mounting poses.
These corrections and layout values are session-only.

The Walkman top-right badge identifies `Aqua a6`. Tap it to show `R` (accepted
scene updates per second) and `D` (last software draw/submit wall time in ms).
These distinguish receive cadence from drawing time without assuming hardware FPS.

Tap the Mosaico top status to show completed draw submissions per second,
simulation time, draw time and queued transmit rate. The draw count is an
application submission counter, not an independently measured panel scan rate;
transmit queue success is not a peer-delivery acknowledgement. The S31 snapshot
used here does not enable the IDF ROM USB-console capability. Do not describe
empty USB diagnostic captures as measured FPS.

Tap `< EXIT` on X1060 and wait for the application list before connecting USB.
The independent radio owner restores original Wi-Fi before the managed launcher
releases the session. Connect stock Sony Wi-Fi before launching. A managed-launch
capability is mandatory; original launchers refuse radio startup.

## Calm water and fish

The default calm model uses 32 surface columns, a conserved cross-sectional water
volume, a filtered gravity slope, critically damped surface response and small
ripples. It deliberately excludes detached spray and large fluid fragmentation.
It assumes an upright assembly and moderate tilts; it is not a three-dimensional,
fully invertible Navier-Stokes solver. The fish swims independently through the
available depth, turns gradually and animates its tail and fins.

The software water material retains the visible tiled floor, subtle refraction,
thin reflection and caustic highlights. The simulation/snapshot producer and the
renderer are separate tasks on Mosaico. Material calculation runs outside the
LVGL mutex; only framebuffer submission and UI updates take that mutex.
The renderer samples a smaller surface buffer and expands it to the panel while
preserving physical millimetre scale. The X1060 renderer also uses that path,
speed-oriented compilation and interpolation between snapshots. The water-mask
construction uses fixed-point row increments instead of per-node software
floating point; the paired material phase is normalized to the encoded cycle.

## Geometry and radio

All positions and fish dimensions use millimetres. Each screen maps its own
physical viewport to pixels, so pixel-density differences do not change fish
size. `SETUP` adjusts both active glass widths/heights, horizontal glass-edge gap
and the X1060 top offset. Defaults are estimates: Mosaico 40 x 40 mm, X1060
37 x 66.6 mm, gap 8 mm, top offset -13.3 mm. Measure or visually align the calm
waterline before claiming exact physical continuity. The bezel is an invisible
corridor with the verified vertical overlap; panel geometry still clips the view.

AQF3 snapshots are exactly **120 bytes**: session/sequence, layout, fish pose,
32 fixed-point surface heights and CRC32. Both endpoints must use AQF3 clients;
AQF2 particle snapshots are not compatible. This application-level marker is not
a new ESP-NOW protocol version. The standard ESP-NOW envelope remains unchanged.
Complete snapshots recover skipped updates without partial scene ownership.

Mosaico uses channel 8 and targets 20 queued snapshots/s. The X1060 owner retains
the first valid source MAC for its session. This local demo is unencrypted; CRC32
is integrity checking, not authentication or secure pairing. There are no account
credentials or session keys in the demo. Actual timing requires physical testing.

The shared XNOW source adds guarded packet-span transfers. They validate the
complete owned interval, retain per-access lease admission and revalidate the
radio identity, ticket, pointer and length before publishing RX data. This avoids
repeating all remote metadata reads for every word. A 1208-byte direct guard
fixture falls from 3322 raw commands to 322; this is a transport-call count, not a
physical throughput benchmark. Generic TX/RX, errors, revoked leases, changed
tickets and old Sony-libc ARM execution are separately tested. No kernel module
or radio-side ABI change is required by this optimization. Rebuild full-backend
consumers against the matching XNOW headers/archive; old SDK ZIPs remain frozen.

## Native build

```sh
.venv/bin/python tools/test_glass_marble.py
.venv/bin/python tools/test_glass_marble_owner.py
.venv/bin/python runtime/apps/glass-marble/build.py
```

The builder uses the current XNOW source and pinned Sony-libc inputs documented in
[BUILD](../BUILD.md). It constructs a fresh radio candidate from the retained
review-3 original inputs, and writes its new identities under `work/glass-marble`.
No previous hardware pass is inherited. The package is under
`work/glass-marble/HOMEBREW/apps/glass-marble`. The separately generated candidate
belongs under `/contents/HOMEBREW/data/glass-marble/candidate/` on an explicitly
prepared test unit; it never belongs in Sony system paths. The builder does not
copy it to a device. Local Sony radio inputs are not public redistributable files.
The build receipt remains `deployable=false` pending graphical/platform testing.

## Mosaico firmware build

Use official sources at these revisions:

- [ESP-Mosaico BSP](https://github.com/esp-mosaico/esp-mosaico-bsp),
  `7cbfb390638dcb93522fc3cde094b2d43cf907c2`.
- [ESP-IDF](https://github.com/espressif/esp-idf),
  `d445e947156f276dfe0db5804e4edf6ae90fe6fb` (6.2 development snapshot).

The BSP detects the board variant from eFuse. BMI270 presence alone does not
identify a board revision; no guessed pin mapping is supplied. A board without
valid revision identification fails explicitly. The application only uses the
display, touch and IMU, not expansion modules, audio, NAND or magnetic topology.

With the matching ESP-IDF environment activated:

```sh
export MOSAICO_BSP="$PWD/work/mosaico-bsp"
python runtime/apps/glass-marble/mosaico/build.py
```

Use the builder's `--menuconfig` option to adjust persistent build defaults.
The builder stages source and managed dependencies under ignored `work/` and
outputs firmware to `work/glass-marble-mosaico-firmware`.
Build output includes the application, bootloader, partition table and flashing
arguments. Building does not flash. Original factory firmware should be retained
before a separately authorized installation. NVS initialization never erases the
existing partition automatically on an initialization error.

## Validation boundary

### Main-task stack regression

The alpha.2 Mosaico image used the IDF default 3584-byte main task stack. Actual
S31 compiler frames for `app_main` and `gm_step` alone required at least 6224 bytes,
excluding deeper driver calls. Physical feedback reported a frozen initial scene,
periodic black-screen restarts and subsequent X1060 link loss. Alpha.3 moves the
serialized fluid workspace and transmit packet into static storage and reserves
16384 bytes for the main task. Its corresponding two compiler frames total
576 bytes. The firmware builder now runs `tools/test_aqua_stack_budget.py` against
the actual S31 compilation flags and configured task capacity. This catches the
original stack overrun; it does not claim a complete driver call-graph bound.
That alpha.3 correction retained AQF2 compatibility with the alpha.2 client.
The later calm revision uses AQF3 and requires matching clients on both endpoints.

`tools/test_glass_marble.py` runs the actual shared code on host and ARM926 with
original libc: snapshot CRC/length rejection, transactional decode, sequence wrap,
volume conservation, bounded surface waves, slope response, independent axis
correction and paired renderer geometry. It generates static and animated previews. The app builder executes safe CLI and rendered-preview entries under
QEMU. These are offline results, not hardware or refresh-rate qualification.
The paired preview is synthetic and uses estimated display dimensions.
The production owner loop and gate also pass a host-process fixture with modeled
radio/manager operations: real pipe EOF, duplicate owner exclusion, IO-error stop,
restoration-cookie record and EOF ordering. This is not actual Sony restoration.

No device installation, flashing, NVP/partition changes or live RF tests are part
of these checks. Current full-radio APF/USB/sleep admission, forced-stop behavior,
long-duration load and exhaustive recovery remain to be qualified. Separately
authorized installations were readback-verified, and the user confirmed the
alpha.6 display, connection and flow after upright recalibration. Those bounded
observations do not qualify every lifecycle or another device model.
