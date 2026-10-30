# SDK validation and capability limits

Current SDK: **0.2.0-alpha.8**. Public ESP-NOW core/message/device/full/security/
full-device/owner consumers pass original-libc ARM926 checks; owner headers also
pass C++ syntax checks. These are offline SDK integration checks. Separate X1060
hardware experiments establish encrypted TX/RX through1470 bytes and same-key
native-process counter continuation. They do not qualify all applications,
over-air replay rejection, power-loss behavior, USB or sleep/wake transitions.
See [ESP-NOW services](ESPNOW.md) for the API and required caller storage policy.

The historical validation scope below records the original callback/native
service migration and its tests; those results are not new alpha.8 device tests.


SDK0.2.0-alpha.1 targets the Japanese1.11 platform only. NW-X1060 has earlier
selected terminal/device evidence; this SDK has not been installed or tested on
a physical player as a new acceptance run. The user reports the16 previous
local app builds passed on their unit; exact personal package identities were
not supplied. NW-X1050 has no equivalent device report. Existing sleep,
USB, recovery and application-specific hardware questions remain open.

The validation entry is `python tools/test_sdk.py` on Linux/WSL after setup.
Host and ARM fixtures exercise lifecycle success, partial-open failure, failed
init, input failure, present failure, close failure, cancellation and finish.
They test clipping, invalid text/image inputs, button drag/release behavior and
storage denial after cancellation. ARM fixtures run under the pinned original
loader and libc, with synthetic display callbacks; no native driver is opened.
They also deliver actual SIGTERM through the original libc from inside an
application callback and verify immediate xw_is_stopping visibility.

Host storage tests use a dedicated work/ directory: bounded save/load, missing
settings, ownership denial, symlink/hardlink/FIFO rejection, stale-temp rejection,
ownership loss before publication and explicit uncertainty after publication.
The SDL2 backend is also exercised with a dummy video driver: real window/texture
creation, present, synthetic mouse events and shutdown, without a desktop/device.
The maintained counter and canvas apps are compiled for host rendering and ARM;
their real packages are verified and changed executables are rejected. The
counter's scripted tap creates its four-byte settings on the computer.

The SDK source bundle is additionally tested after extraction into a new work/
checkout: all source hashes are checked, no proprietary inputs are included,
setup prepares inputs from the pinned updater, all three templates are generated,
host/ARM builds and package checks run without old work files or installed apps.
The bundle contains no host or ARM application executable, ROM, save, account
state or original Sony libc. CI uploads only the explicit source SDK archive.

The16 existing apps additionally adopt native services. Their source logic and
effective include graphs are audited against the frozen pre-SDK commit. A clean
same-path build compares runtime/resources/inventories, normalizing only proven
GCC temporary STT_FILE names outside program load ranges in memory. Raw hashes
and normalization records remain separate. See [service migration](SERVICES.md).
An independent native-service client also builds/runs from the extracted SDK.

These checks establish software behavior for exact checked source inputs. They
do not establish physical display/touch restoration, USB exclusion, suspend/wake,
FM reception, audio output, installation safety or recovery. The device storage
provider deliberately remains unknown by default. No toolkit operation flashes
firmware or contacts a real account. Do not turn a passing preview or QEMU result
into a hardware-qualified badge.

## Optional ESP-NOW services in0.2.0-alpha.2

The original16-app migration excluded ESP-NOW. It is now an independent optional
SDK addition: generic binary transport, an optional message helper and the
explicit device backend. See ESPNOW.md. Public-header ARM tests are offline.
The identified native XNOW0.1.0-dev.8 library separately passed physical
bidirectional96-byte exchange with application ACKs and stock restoration.
That component result does not qualify every new SDK application or UI lifecycle.

##0.2.0-alpha.6 malformed datagram handling

The full-runtime fixture reproduced a malformed plaintext IE causing application
failure-1 despite an unfaulted backend. Wire-error normalization fixes this
collision with IO/UNCERTAIN. Host ASan/UBSan and ARM926/original libc now discard
malformed IE/version inputs, accept following valid unknown plaintext, continue
encrypted1470-byte traffic, and still stop on an injected actual read failure.
No installed app or physical radio behavior is implied. Alpha.5 artifacts are
retained; the source/API implementation identity advances independently.

##0.2.0-alpha.5 managed owner source service

Adds explicit espnow-owner selection and seven public forwarding headers. The
public ARM926/original-libc consumer performs bounded command checks, STOP and
RAM-only anonymous-pipe handoff; C++ header syntax is checked independently.
No radio/volume acquisition or device installation occurs. Existing application
SDK dependency pins advance without new installed-app acceptance. Full owner
hardware/APF/USB/sleep and encrypted Espressif interoperability remain pending.

##0.2.0-alpha.4 full service delivery

Clean extraction of the source-only SDK passes manifest/hash/path checks, pinned
original-input setup, minimal/touch-ui/canvas-game build/package checks, existing
native-service regression and old/full ESP-NOW public ARM926 consumers. Host
C++11 syntax checks pass for full public headers. XNOWdev.10 minimal/whole-archive
original-libc linking passes. These are offline delivery checks: no installed
app, driver, radio image or firmware is changed and no physical full ESP-NOW
qualification is implied. See ESPNOW.md for module selection and platform guards.
