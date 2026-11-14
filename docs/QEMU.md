# Original Sony interface in QEMU

The default PC viewer runs the unmodified Japanese 1.11 SpiderApp, original libraries,
sysmgrd, appproxy and AppList in an isolated ARM926 system guest. Its screen comes
from the guest framebuffer. The browser displays those pixels and sends touch
coordinates; it does not recreate Sony menus.

This uses a Versatile PB machine, a pinned Debian 2.6.32 kernel and explicit
peripheral adapters. It is not an MP200 emulator or a boot of Sony's kernel.
Audio, DSP execution, physical Wi-Fi/RF, sleep/wake, USB ownership, installation
and recovery remain unqualified. Production firmware is not changed by the viewer.

## Prepare local inputs

Run Python tools from the repository root in Linux or WSL. The Windows helper
defaults to WSL distribution `Ubuntu-24.04` and Python environment
`work/wireless-debug-venv`. Create that environment and install the pinned
`requirements-research.txt` dependencies before preparing the guest.

The PC tools also require the ARM GNU compiler/binutils, `qemu-arm`, `7z`,
OpenSSL with its legacy provider, `dpkg-deb` and `mke2fs`. No Sony executable,
kernel, library, device state or downloaded package is committed to this repository.

To extract verified original inputs from an existing Japanese updater without
network access or application builds:

```sh
work/wireless-debug-venv/bin/python tools/ci_bootstrap.py \
  --stock-only --stock-exe firmware/original/NW-X1000_V1_11.exe
```

Keep the following additional local inputs under ignored `work/`:

- Sony GPL source archive `work/downloads/linux-kernel-2.6.10.local.tgz`.
- Debian package `work/qemu-system-bootstrap/kernel.deb`, containing
  `linux-image-2.6.32-5-versatile_2.6.32-48squeeze6_armel.deb`.
- Extracted Ubuntu Noble `qemu-system-arm` version `1:8.2.2+ds-0ubuntu1.18`
  and its PC shared-library dependencies under `work/qemu-system-bootstrap/extracted`.

The preparation scripts check fixed input hashes and refuse different existing
destinations. They extract into the private project directory, not the host root,
and do not install packages or access a player:

```sh
work/wireless-debug-venv/bin/python tools/prepare_arm_guest.py \
  --kernel-package work/qemu-system-bootstrap/kernel.deb \
  --qemu-root work/qemu-system-bootstrap/extracted
work/wireless-debug-venv/bin/python tools/prepare_stock_manager_inputs.py
```

`prepare_stock_manager_inputs.py` supplies original runtime files, selected GPL
driver ABI sources and matching generic-kernel modules. The kernel and QEMU
identities are checked again when preparing a session. Reports record source,
binary and guest-library hashes; an older report is not a pass for changed code.

## Start and operate

From PowerShell at the repository root:

```powershell
& .\tools\Start-StockGui.ps1
```

The helper starts WSL hidden, prepares a new private session under `work/`, and
opens its localhost viewer. Use `-NoBrowser` to print the URL without opening it,
or `-Distribution <name>` to select another prepared WSL distribution.

The equivalent foreground WSL launch is:

```sh
work/wireless-debug-venv/bin/python tools/run_stock_gui.py \
  --output work/stock-gui-local-1
```

Use a new output directory for each preparation. `--session work/<name>` starts
an existing prepared guest only while its recorded source and binary hashes match.

The first screen can take several seconds. A fresh guest can show Sony's
startup-error notice; dismiss it with the bottom-right confirmation control.
The Home toolbox opens Settings. Music Settings provides a bottom-left return
arrow. Home, Settings, Music Settings and return navigation have been observed.

Click the screen to wake it before using controls. The first contact after idle
may only wake the display. Clicks and drags can take a moment to appear. Drag
lists to scroll. `Release touch` clears a held contact. `Close emulator` stops
the session and discards guest state. Closing the browser tab alone leaves QEMU
running. Original userspace can also stop after its own power/idle flow; inspect
the private logs and start a new session if needed.

The viewer binds only to `127.0.0.1` and uses a per-session token for control
requests. Only the isolated guest receives input; no physical player is accessed.
Do not publish its private `server.json` or logs.

## Optional guest profiles

The viewer can inspect a locally reviewed candidate root with
`--firmware-review work/<review>/review.json`, or PowerShell's `-FirmwareReview`.
It checks the UPG identity and unchanged first three original components, then
uses the reviewed root and its original AppList without rebuilding production
binaries. It still boots the generic kernel. The updater is never run and no
physical configuration, pairing keys or packet-number journals are imported.

`--settings-layout primary|secondary` selects explicit synthetic model words for
the two original Settings layouts. The Windows equivalent is `-SettingsLayout`.
These are guest routing fixtures, not device NVP readbacks, region-feature changes
or overseas firmware compatibility claims.

For a separate user-volume model, keep the pinned local Ubuntu Noble packages
`dosfstools_4.2-1.1build1_amd64.deb` and `mtools_4.0.43-1build1_amd64.deb` under
`work/fat-pc-tools/`, then run:

```sh
work/wireless-debug-venv/bin/python tools/stock_user_volume.py --prepare-inputs
```

Pass `--ram-user-volume` to Python, or `-RamUserVolume` to PowerShell. A synthetic
64 MiB FAT32 RAM block and matching generic-kernel FAT/NLS modules let original
sysmgrd mount `/contents` with its own VFAT options. An ext2 pre-mount is removed
by original sysmgrd and is insufficient. This profile models neither physical
capacity nor USB ownership; all guest writes disappear when the session closes.

The Python viewer also exposes explicit diagnostic profiles:

- `--homebrew-roundtrip-fixture` supplies only a two-second guest child for
  reviewed-candidate lifecycle investigation. It is not the actual launcher and
  does not establish a successful Homebrew return or Wi-Fi retention.
- `--catalog-trace` delegates original SQLite calls and records filenames/numeric
  errors. An open database alone is not media-startup qualification.
- `--remote-runtime-review` stages matching public Remote binaries and synthetic
  configuration in a new RAM user volume. It requires a matching firmware review
  and `--ram-user-volume`; no physical keys, PN state or radio payloads are copied.
- `--mg-constructor-model` models the verified open/mapping/empty-constructor
  boundary only. Every crypto/key command remains refused. It does not implement
  authentication or repair original media startup.

All such profiles require a new `--output`. Their observations qualify only the
reported guest paths and binaries. Startup-error and incomplete Homebrew paths
remain explicit limitations of this generic machine.

## Source-layout investigation without an installer

`--layout-review work/<layout>/report.json` loads a fresh source-bound system
overlay instead of requiring a generated UPG. The layout records its existing
localization input; the guest verifies that input, the host/library identities
and every overlay file. The original installation components remain unchanged
and no updater is run. `--layout-review` and `--firmware-review` are exclusive.

Use a new session with `--ram-user-volume --homebrew-roundtrip-fixture` to
investigate the actual composed entry and original manager/proxy return with a
two-second synthetic child. It is not the installed launcher, a media decoder
or a hardware release test. Display/input, Wi-Fi, audio and USB conclusions must
retain those model boundaries. Modified source invalidates prepared adapters;
create a new layout/session rather than relabeling earlier results.

For a repeatable entry/return check, use a verified Home screenshot from the
same menu composition as an explicit reference:

```sh
.venv/bin/python tools/test_stock_homebrew_system.py \
  --layout-review work/<layout>/report.json \
  --home-reference work/<reference>/home.png \
  --output work/<new-run>
```

The check waits for the rendered Home screen before tapping the Homebrew icon,
requires the fixture child's console entry and exit records, then requires Home
again. It records timing, image comparisons and failures, checks that source
has not changed, and closes its own viewer. It does not count a click, a live
process or a black screen as success. The fixture writes to the guest console
because Sony may redirect a child application's standard error.

The current warm-handoff composition reaches Home and requests original
playback-state capture. The capture object is in mode1/state7, where the
original state table selects a no-op and emits no completion. The same path
occurs when selecting the original browser with unmodified Sony userspace in
this GUI-only profile, without the CFW host library. This observation does not
identify a CFW-specific failure and cannot qualify a successful application
handoff. Do not skip capture or synthesize its completion to make the test pass.

Captures with different idle durations cannot isolate a regression: automatic
screen blanking and the incomplete power/wake model must be separated from
startup and application-transition failures.

## Native NCAN shutdown

The original exit path stops GctlSys and joins its background worker. That
worker retries a failed NCAN wait ioctl before checking its stopping state.
An adapter that rejects both wait and break can therefore keep original
finalization waiting, even without any CFW library.

`--ncan-wait-model` adds the idle non-Digipod wait/break contract to the existing
virtual NCAN control profile. Wait `0xc0046308` blocks until break `0x6309`
produces event word `0x200`. A new wait clears an older break in this selected
variant; the original Digipod comparison variant has different ordering.
No NC engine, sensor changes or physical timing are supplied. Unknown requests
remain refused. The original worker and application-manager code still decide
when to exit; no native completion is inserted.

```sh
work/wireless-debug-venv/bin/python tools/test_stock_ncan_wait.py
work/wireless-debug-venv/bin/python tools/run_stock_gui.py \
  --output work/usb-ncan-observation --ram-user-volume \
  --usb-transition-model --ncan-wait-model
```

With this explicit model, original Sony userspace and the source-bound CFW
composition have reached actual Responder entry. Responder then fails because
`/dev/mgscsi` is absent. This establishes neither gadget initialization nor
physical storage access. Do not turn missing SCSI requests into success.

## USB connection observation

The default peripheral profile always reports USB disconnected. It cannot
exercise the application's response to plugging in a cable. An optional
`--usb-transition-model` supplies controlled connection notifications through
a third guest UART. It preserves the original manager, player and AppList:

```sh
work/wireless-debug-venv/bin/python tools/test_stock_usb_connection.py
work/wireless-debug-venv/bin/python tools/run_stock_gui.py \
  --output work/usb-observation --ram-user-volume --usb-transition-model
```

The contract check executes the pinned original `icx1087_usbconn.ko` status,
access and poll instructions in Unicorn, comparing each operation with the C
model. It also checks the GPL header's ARM ioctl values, host sanitizers and
original-libc ARM execution. Kernel scheduling, wait queues and copy-to-user
effects are fixtures; the module is never installed or loaded into a kernel.

Connection statuses 0 (disconnected), 4 (start-connect) and 1 (connected) are
supported. Status queries do not consume a notification; poll consumes it once.
Changes coalesce while pending. Prohibited access masks a connected status as
disconnected. Firmware-update and MTP states are refused.

When enabled, the token-authenticated local viewer endpoint `POST /usb` accepts
`{"status": 0}`, `{"status": 4}` or `{"status": 1}`. The request-correlated reply
confirms only receipt of a test input. `handoff_acknowledged` remains false:
input acceptance does not prove player retirement, Responder startup or storage
ownership. Without this profile, USB input is refused. The transport has one
notification observer per process and covers the original manager's poll path.
Generic select observers, multiple observers and USB-gadget operation are not
qualified by this transport.

Add `--task-trace` only for diagnosis. It briefly pauses original tasks and
records registers, possible return addresses and selected Root/APF words after
a connection change. A possible return address is not an unwound stack frame.
The pinned 2.6.32 guest uses `/proc/<pid>/stat` when per-task `comm` is absent.
These observations change scheduling and do not qualify timing.

This diagnostic profile also observes the existing read-only player-library
exports on the GUI display owner. `GUEST_PLAYER_BINDING` reports whether the
queries are available, whether the owner anchor bound, and whether original PID
delegation resolved. It calls no service or native event. Binding success is
distinct from radio readiness, a client grant and physical acceptance.

Without the NCAN wait model, USB notifications have been observed reaching original command3 with both
unmodified Sony userspace and a source-bound CFW library. The captured Root
state and relative library wait position match in these no-active-Remote cases;
this is not an active Remote/SDK drain test. Complete original finalization,
Responder startup, host enumeration and physical USB ownership remain unqualified. With the wait model,
Responder entry is observed, while its SCSI setup remains unsupported. A black screen
alone cannot distinguish display blanking, preparation or a blocked application.
Do not bypass native completion to manufacture a successful handoff.

## Model verification

The maintained bounded checks execute model contracts on host sanitizers and/or
ARM926 with the original Sony libc:

```sh
work/wireless-debug-venv/bin/python tools/check_repository_layout.py
work/wireless-debug-venv/bin/python tools/test_stock_silent_mixer.py
work/wireless-debug-venv/bin/python tools/test_stock_dsp_idle.py
work/wireless-debug-venv/bin/python tools/test_stock_mg_constructor.py
```

The silent mixer produces no sound. The idle DSP profile provides bounded memory
and an empty queue, with no DSP instructions or fabricated boot-completion event.
The default GUI profile instead uses an empty OpenMAX registry. These models
support interface investigation and do not replace physical-device acceptance.
