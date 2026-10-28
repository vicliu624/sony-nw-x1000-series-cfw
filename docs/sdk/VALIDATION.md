# SDK validation and capability limits

SDK0.1.0-alpha.1 targets the Japanese1.11 platform only. NW-X1060 has earlier
selected terminal/device evidence; this SDK has not been installed or tested on
a physical player. NW-X1050 has no equivalent device report. Existing sleep,
USB, recovery and application-specific hardware questions remain open.

The validation entry is `python tools/test_sdk.py` on Linux/WSL after setup.
Host and ARM fixtures exercise lifecycle success, partial-open failure, failed
init, input failure, present failure, close failure, cancellation and finish.
They test clipping, invalid text/image inputs, button drag/release behavior and
storage denial after cancellation. ARM fixtures run under the pinned original
loader and libc, with synthetic display callbacks; no native driver is opened.

Host storage tests use a dedicated work/ directory: bounded save/load, missing
settings, ownership denial, symlink/hardlink/FIFO rejection, stale-temp rejection,
ownership loss before publication and explicit uncertainty after publication.
The SDL2 backend is also exercised with a dummy video driver: real window/texture
creation, present, synthetic mouse events and shutdown, without a desktop/device.
The
maintained counter and canvas apps are compiled for host rendering and ARM;
their real packages are verified and changed executables are rejected. The
counter's scripted tap creates its four-byte settings on the computer.

The SDK source bundle is additionally tested after extraction into a new work/
checkout: all source hashes are checked, no proprietary inputs are included,
setup prepares inputs from the pinned updater, all three templates are generated,
host/ARM builds and package checks run without old work files or installed apps.
The bundle contains no host or ARM application executable, ROM, save, account
state or original Sony libc. CI uploads only the explicit source SDK archive.

These checks establish software behavior for exact checked source inputs. They
do not establish physical display/touch restoration, USB exclusion, suspend/wake,
FM reception, audio output, installation safety or recovery. The device storage
provider deliberately remains unknown by default. No toolkit operation flashes
firmware or contacts a real account. Do not turn a passing preview or QEMU result
into a hardware-qualified badge.
