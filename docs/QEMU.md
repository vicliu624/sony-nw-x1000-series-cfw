# Original Sony interface in QEMU

The PC viewer runs the unmodified Japanese 1.11 SpiderApp, original libraries,
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
