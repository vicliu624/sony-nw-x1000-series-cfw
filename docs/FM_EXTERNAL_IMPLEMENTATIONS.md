# Si470x external implementations and test software

This comparison extends the [Sony driver reconstruction](FM_DRIVER_REVERSE_ENGINEERING.md).
The actual player's CHIPID remains unknown. B16/B17/C19 and family drivers are
comparison candidates, not confirmed same-stepping matches. Inputs remain in
ignored `work/fm-driver-comparison/`; content identities are recorded in
[the source manifest](../sources/fm-comparison-sources.json).

## Initialization differences with concrete evidence

| Implementation | Significant operation | Interpretation and next action |
| --- | --- | --- |
| Sony Japanese 1.11 | `TEST1 = read_TEST1 & 0x3fff`; preserves TEST2/BOOTCONFIG | No oscillator-enable or special test constant; physical reference-clock source still needs board evidence |
| Rockbox | On selected Sansa builds, sets TEST1 with `XOSCEN | 0x0100`, waits 500 ms before power-up | Explicit source comment mentions Si4702-16; clock startup candidate, not an IQ mode |
| SparkFun | Active TEST1 literal `0x8100`; commented-out `0xbc04` attributed to an older AN230 revision | Inspect power-state assumptions before interpreting constants as hidden functionality |
| Linux v6.12 I2C | Normal POWERCFG enable/disable and family register transport | Useful independent transport reference; no IQ outlet identified in this file |
| Freescale original `mxc_si4702.c` | Reads TEST1 and expects `0x3c04` after power-up; fixed sixteen-byte writes to `0x02–0x09` | The apparent magic value is checked, not sent as an unlock; this writer cannot reach the command window |
| William Gao Si470x | Preserves read state, sets XOSCEN, waits 500 ms, enables POWERCFG; writes only `0x02–0x07` | Another ordinary oscillator sequence, without TEST2/BOOTCONFIG or command-window writes |

Primary source: [Rockbox si4700.c](https://github.com/Rockbox/rockbox/blob/master/firmware/drivers/tuner/si4700.c),
especially `si4700_sleep`. Its selected-target build paths and comments must not
be generalized to every Sansa or Sony board. Another path uses GPIO3 as a
mono/stereo indicator, showing a legitimate non-IQ alternate output function.

Primary source: [SparkFun driver](https://github.com/sparkfun/SparkFun_Si4703_Arduino_Library/blob/master/src/SparkFunSi4703.cpp).
The old `0xbc04` line is commented out; its presence is not evidence that the
current driver executes it. Vendor B17 register 07 documentation explains that
low bits are preserved as `0x0100` in powerdown and `0x3c04` in powerup.
Setting XOSCEN produces `0x8100` or `0xbc04` respectively. This explains the
apparent magic constants without identifying the internal purpose of each
reserved bit. See [original Silicon Labs B17 datasheet, register 07](https://media.digikey.com/pdf/Data%20Sheets/Silicon%20Laboratories%20PDFs/Si4703-B17.pdf).

## USB commands: identify the actual recipient

The [Linux v6.12 USB driver](https://github.com/torvalds/linux/blob/v6.12/drivers/media/radio/si470x/radio-si470x-usb.c)
defines register HID reports 1-16, whole-map report 17 and RDS/status report 18.
It also describes scratch pages, streaming and bootloader/flash reports.
Its comments identify flash upgrading as belonging to the **C8051F321**, the
USB bridge microcontroller. Therefore those commands are not evidence of a
Si4703 flash loader, hidden register bank or IQ stream. The source explicitly
marks report 23 as unused; its packet capacity alone establishes no signal path.

[Vendor AN264](https://media.digikey.com/pdf/Application%20Notes/Silicon%20Labs%20Application%20Notes/USBFMRADIO-RD_AN264.pdf)
names `AN264SW.zip` as the software/firmware/source package. It describes
Si4701 analog audio being digitized by the C8051F321 ADC. That stream is decoded
audio, not direct tuner IQ. This is an older-family comparison, not a Si4703
stepping match. The [archived vendor ZIP](https://web.archive.org/web/20140722174009id_/http://www.silabs.com/Support%20Documents/Software/AN264SW.zip)
was recovered and inspected statically. See the [MCU evidence](FM_USB_MCU_REVERSE_ENGINEERING.md#recovered-silicon-labs-an264-software)
for archive hashes, page verification and the flasher source.

An additional [community attachment lead](https://whycan.com/t_2221.html)
identifies `AN264SW.rar`. The file URL returns a download landing page; its
actual download endpoint requires an account plus forum points or payment.
No package was obtained or authenticated. The original `.cn` hostname also
fails TLS validation. A filename and an uploader's attribution do not prove
that the package contains an unmodified vendor source release.

## Original Freescale driver: transport and debug-path comparison

The original [Freescale mxc_si4702.c](https://git.toradex.cn/cgit/linux-toradex.git/plain/drivers/char/mxc_si4702.c?id=2731b2eadeaa141e6f305fa8086106608112bbaa)
is preserved in Toradex's kernel distribution at commit
`2731b2eadeaa141e6f305fa8086106608112bbaa`. The file carries Freescale's
2008-2010 copyright and GPL-2.0-or-later notice. Unlike a new generic library,
this is a period OEM platform driver with an explicit diagnostic interface.

Its read helper always obtains the full 32-byte register image. Its write
helper updates that image, but sends exactly sixteen bytes covering registers
`0x02–0x09`, regardless of the supplied register index. Consequently, the
helper accepting an index below 16 does not mean it can transmit `0x0c–0x0f`.
The TEST1/TEST2 words in each transaction come from the retained image; all
actual write call sites target POWERCFG, CHANNEL or SYSCONFIG1/2/3.

Startup enables supplies, reads DEVICEID before any write, enables the board
clock, waits 100 ms, writes POWERCFG `0x4001`, waits 500 ms, then reads TEST1.
It logs a diagnostic if that value differs from `0x3c04`. It next configures
channel zero, SYSCONFIG1 zero, volume and platform-specific band/spacing/seek
parameters. The variable named `magic` receives a read result: it is never
passed to the write helper. This is independent source evidence that the
power-state-dependent TEST1 value should not be mistaken for an unlock code.

The sysfs command table advertises start/halt/reset, volume, seek, mute,
selection, seek threshold and delay. The switch implements only a subset;
`delay` merely logs its argument. There is no arbitrary-register, IQ, test
output or patch-download command in that handler. Its ioctl path likewise
uses ordinary tuner controls. No extra command-processor sequence was found.

The [Freescale i.MX31 PDK 1.5 Linux reference manual, chapter 40](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/imx-processors/93599/1/pdk15_imx31__Linux_RM.pdf)
independently names this driver and its header. This establishes a period
platform lineage; the Toradex snapshot is not asserted to be byte-identical
to the manual's BSP release or a verified B16/B17/C19 instance.

## Product-maker firmware and programming jig: The Public Radio

The manufacturer's [2014 design update](https://www.thepublicrad.io/updates)
explicitly identifies Si4702 plus ATtiny25 and links its public repositories.
The [firmware repository](https://github.com/The-Public-Radio/Firmware/tree/9992fcd29607f820a7c01bc8fa092ffb1ce17514)
was acquired at commit `9992fcd29607f820a7c01bc8fa092ffb1ce17514`, including
the one-touch programming jig. This is a concrete product-maker source and
production-programming input, not Silicon Labs factory characterization
software or a confirmed Sony stepping match.

In `Firmware/main.c`, actual write call sites end at registers 2, 3, 6 or 7.
The writer uses read-order shadow offsets: register 2 is byte offset 16,
register 7 offset 26, and transfer length is `upto_reg - REGISTER_02 + 2`.
Thus the register-7 call sends twelve bytes covering registers 2 through 7;
the declared enum entries for TEST2/BOOTCONFIG do not establish writes there.

Startup explicitly assigns TEST1 `0x8100`, then waits 600 ms before the
separate POWERCFG ENABLE write. A production comment says this delay was
increased from 500 ms after some units started with static. Another comment
reports that setting XOSCEN with `0x3c04` failed on the author's hardware.
These are attributed upstream observations, not reproduced measurements or
an authenticated silicon revision. The active source subsequently configures
ordinary band, spacing, volume and seek thresholds. It supplies no identified
IQ unlock sequence.

The one-touch jig's active packet builder sends channel high/low bytes and
CRC16 high/low bytes. Band, de-emphasis and spacing fields are present in a
commented block. Firmware also maintains working/factory parameter blocks in
the AVR EEPROM. These production-programming operations must not be confused
with programming Si4702 internal firmware or accessing RF test registers.
Only static inspection was performed; no jig, transmitter or device action
was run. No exact Si4702 suffix/CHIPID match was established from this input.

## Factory/EVB software trail

The original distribution links have now been recovered from a historical
product-page copy, rather than inferred from modern URL conventions:

- `https://www.silabs.com/Support%20Documents/Software/AN264SW.zip`
- `https://www.silabs.com/Support%20Documents/Software/USBRadio.zip`

The direct legacy endpoints returned HTTP 403 HTML. Archived captures
provided both ZIPs. The [2012 USBRadio capture](https://web.archive.org/web/20120905181717id_/http://www.silabs.com/Support%20Documents/Software/USBRadio.zip)
passed ZIP integrity testing and contains exactly one member, USBRadio.exe.
Its SHA-256 is `1ce9698a98bb0c906bda95610e0aefe457c1014e07a470fb184011186774927a`,
and it matches the AN264 GUI executable byte for byte. The standalone
distribution therefore adds no MCU address coverage. The ZIP SHA-256 is
`e6c634ad803d4a3ccb5ef9a38ab7f5358db7ad0162d211753b6ae9b8bd8468d5`.

The [July 2012 USBRadio capture](https://web.archive.org/web/20120723141526id_/http://www.silabs.com/Support%20Documents/Software/USBRadio.zip)
has the same ZIP hash as the September capture. Availability queries
targeting 2006, 2008 and 2010 returned that July 2012 capture for
USBRadio and the same July 2014 capture for AN264SW. The queried dates
did not yield an older payload. The [ADS RDX-155-EF mirror listing](https://www.driverguide.com/driver/detail.php?driverid=1024841)
names `InstantFMSetup.EXE`, but its file link is CAPTCHA-gated. No OEM
executable was obtained from this listing.

An Internet Archive software-title search found two
[RDX150_121.ISO catalog entries](https://archive.org/details/rdx-150-121),
both listing a 135,630,848-byte image. Their uploader descriptions
identify the media as ADS Instant Music RDX-150, with Spin It Again
and Nero software. This identifies a different model from the
RDX-155 FM receiver. One image was acquired and its SHA-1 matched the Archive file
metadata. SHA-256:
`3aa1785cbb5031d6e62d02437dd131f6ea27d01a36efdc5f4eefe8d242140372`.
Its ISO9660 directory inventory has 39 records. The launcher identifies
`RDX150_121.dbd` and DemoShield; the software directories contain
Acoustic, PhotoShow and Acrobat Reader installers. No standalone
radio, MCU HEX or firmware file appears in this directory inventory.
Static 7-Zip inspection identifies the Acoustic installer as
Acoustica Spin It Again with an embedded Wise installer payload.
The PhotoShow setup uses NSIS; its archive listing contains no
Si470x, Silicon Labs, firmware, HEX or driver filename match in
the inspected listing. The Wise payload was not decompressed by
7-Zip, so its internal files remain unexamined. Executables were
not run. Local listings and PE resources remain under
`work/fm-driver-comparison/rdx150-*`.
Searches restricted to Si47xx/Si4700/Si4703
titles returned manuals and case designs, with no EVB software
image in those results.

A broader Archive software search found
[Snap Music V1.01](https://archive.org/details/snap-music-v-1.01).
The uploader identifies a bundled KWorld SnapMusic700 Mobile disc.
The catalog lists `SnapMusic_V1.01.iso`, 281,247,744 bytes, SHA-1
`6efd1db8f807fe8f413165e7450bd020b1478b8f`.
The full ISO was acquired and its SHA-1 matched that metadata.
SHA-256 is `4efb3dbad6ee818c1e1faef13023df8e7fe78afcb04d36181f0fd67017f9e3e8`.
The autorun configuration names SnapMusic Mobile 700. The disc also
contains Studio 715 manuals and a C-Media audio driver, so each
component needs its own target identification.

Static extraction of the Snaptune bootstrapper found an MSI container
and two embedded CABs. The main CAB yielded 47 files. Its
`SnapRec.exe` imports HidD_SetFeature and HidD_GetFeature and contains
the device identifier `vid_1b80&pid_d700`, matching the Linux Si470x
driver's KWorld FM700 identity. SnapRec SHA-256:
`4ca9947dd138357add2a69c773c9348bfa21972bebbcdfc351df08cd734baae4`.
The previously recovered encoded and decoded MCU images do not occur
as complete contiguous byte arrays in this file. Its HID request
builders and any independently encoded images still require analysis.
The located direct calls through SnapRec's HidD_SetFeature import thunk
join a helper at VA `0x439960`. In the first inspected request builder,
the 64-byte report begins with ID 4 and a big-endian word with bit
`0x8000` set. The following poll asks for report 11 and tests mask
`0x4000`, with a 3000-unit timeout argument. The caller then clears
the high command byte and resends the report. This matches the ordinary
CHANNEL/TUNE and STATUSRSSI/STC report layout. Equivalent direct call
sites occur in two other located regions. This is static request
formation evidence. Branch reachability, indirect calls and the
timeout unit have not been qualified. No TEST or bridge boot command
has been established from the located direct calls.

The separate SnapMusic InstallShield cabinets were subsequently
extracted with unshield 1.5.1, yielding 74 files. The application
directory includes both `FM5767DLL.dll` and `FM700ExtDLL.dll`.
The FM700 library SHA-256 is
`6085571f3a360b4954da60f9495ef8e5f928eb2f6f65811b8bf5fdc1bae2399c`.
It exports tune, seek, band, spacing, de-emphasis, RSSI, RDS and mute
functions. Imports include HID feature operations and Windows waveIn/
waveOut audio APIs. Its device-name strings include the Silicon Labs
reference radio, USB FM Stick and ADS InstantFM Music. These provide
another concrete host implementation to inspect beyond Snaptune.
The FM700 library's device matcher at VA `0x100029d9–0x10002a43`
accepts `10c4:818a`, `1b80:d700`, and `06e1:a155`, covering the
reference board, KWorld FM700 and ADS RDX-155. The generic register
writer's whitelist includes feature report IDs 8, 9 and 10, matching
TEST1, TEST2 and BOOTCONFIG in the reference protocol. Another sender
requires report ID 19. Those helpers establish serialization capability.
Direct callers now identify report 19 command `0x35` with a
caller-supplied state and trailing `0xff`, matching reference LED
control. The general register sender at VA `0x1000435d` has direct
callers for reports 3 and 4 plus a wrapper at `0x10004294`.
The wrapper's located callers select reports 5, 6 and 3 during
initialization. No located direct caller selects TEST reports 8–10.
A second report-19 sender has no direct call reference in the scanned
code section. The scan covers immediate x86 calls and leaves indirect
calls unresolved. It has not established a boot command or a tuner
test sequence.

A scan of all 74 extracted files found neither the known 7,725-byte
encoded application records nor the 7,680-byte decoded image as a
complete contiguous array. Independently encoded firmware remains
unexcluded. A startup helper at VA `0x10002e14` is a strict version gate.
It returns true only when the object has a device handle and the
parsed MCU software/hardware version bytes are 7 and 1. The entire
function through `0x10002e50` contains comparisons and returns,
with no calls or USB operation. Its caller at `0x10001d66` first
loads scratch report 20, checks this gate, then proceeds to radio
initialization. The scratch parser copies the stored version bytes
from scratch offsets 1 and 2 into the compared fields. This
start-up path enforces an existing bridge version and supplies no
firmware upgrade when the comparison fails. Those versions describe
the USB bridge and board, not the FM silicon stepping.

The FM700 library initializes its WAVEFORMATEX at object offset
`0x24c` to PCM format 1, two channels, 96,000 samples/s, 16 bits
per channel, four-byte block alignment and 384,000 bytes/s
(VA `0x10001bb6–0x10001bf3`). `waveInOpen` receives that structure
and the enumerated input-device index at `0x1000209b` and
`0x10002103`. `waveOutOpen` uses the same format at `0x10002313`.
This establishes a Windows audio input/playback path at the advertised
reference-board format. The library's audio format does not identify
the analog signal as tuner IQ or establish the Sony capture path.
The FM700 library's sole PE resource is a 908-byte version resource,
identifying KWorld Inc., version 1.0.0.1 and description
`ADS+KWorld+Silicon ID`. There is no separate firmware resource in
the resource tree. The `.rdata` and `.data` virtual sizes are
2,577 and 1,052 bytes. A scan for full absolute pointers to the two
report-19 sender addresses found none in the PE sections, in addition
to the earlier immediate-call scan. Runtime-computed dispatch is still
outside that scan. These facts reduce the evidence for an updater in
this library without excluding code-embedded or transformed data.
The other library's filename alone does not identify its target tuner.
No installer or extracted program was run.

Local inputs and listings are retained under
`work/fm-driver-comparison/snapmusic-*` and `snaptune-*`.

Wayback availability lookups under the same legacy directory returned no
capture for the candidate filenames `Si47XXGui.msi`, `SilabsAudioGui.msi`,
`Si470XFMTunerGUI.zip`, or `AN235SW.zip`. These lookups test specific
guessed paths and do not establish how the EVB packages were distributed.

The [vendor Si4700/01/02/03 EVB guide](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/user-guides/Si4700-01-02-03EVB.pdf)
provides more precise package and target-identification evidence:

- The installation illustration names `Si47XXGui.msi` and `Readme(2.5.2).doc`.
  The broader [Si47xx EVB guide](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/user-guides/Si47xxEVB.pdf)
  shows a later `SilabsAudioGui.msi`. These names improve archive matching but
  do not identify a package we have obtained.
- The older EVB uses a C8051F320. Its J2 programming connector updates that
  MCU, distinct from the C8051F321 used in the USB-radio reference design.
- The GUI describes device-firmware boot and initialize-only choices, register
  editing, band-scan logs and raw-RDS/channel logs. Those labels establish
  neither raw-IQ capture nor an externally writable tuner firmware store.
- Its example register-map screenshot is labeled Si4709 Rev B, despite this
  guide's title. Screenshot-only extra fields must not be assigned to Si4703.

The next package inspection should therefore identify its supported part and
stepping before interpreting the firmware-selection or register-map code.
An installer bearing the shared GUI name can include other chip families.

[Vendor AN235](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN235.pdf)
identifies the Si47xx Development GUI on the EVB CD and USB HID identity
`VID_10C4&PID_8193`. This is a concrete software/board identification lead,
not an acquired factory executable. The older GUI name `Si470XFMTunerGUI`
also appears in the original EVB guide; its package still needs recovery and
static inspection.

[Vendor AN388](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN388.pdf)
provides reproducible receiver tests, including a Si4700/01/02/03 standard
configuration and audio-analyzer SINAD measurements. The document includes
other families; its digital-output setup section explicitly targets later
parts, not Si4702/03. Its baseboard codec/SPDIF functionality must not be mistaken
for raw samples from the FM chip. The old AN234 procedure was consolidated
into AN388 according to its change list.

## Remaining search targets

### Historical command-table conflict

A locally acquired original Silicon Labs AN230 Rev 0.61 (May 2008), retained by
[SparkFun](https://cdn.sparkfun.com/datasheets/BreakoutBoards/AN230_0.61.pdf),
contains an internal contradiction: printed page 30, Table 20 lists
SET_PROPERTY/GET_PROPERTY as `0x06/0x07`, while the detailed command encodings
on pages 31-32 specify `0x07/0x08`. The two-wire and three-wire examples on
pages 27-28 also use `0x08` for GET_PROPERTY. Thus a search result quoting
`GET_PROPERTY = 0x07` is not evidence of a separate chip command set. It is
consistent with a summary-table error. No hardware experiment resolved that
contradiction in this project. Do not probe both opcodes indiscriminately:
the detailed specification assigns `0x07` to a modifying command.

The scope states firmware 15+ and example code version 2+, with example code
distributed through mysilabs.com. We acquired the document, not that example
code. Its exact PDF hash and source location are in the source manifest.

### Windows USB host implementation inspected

The [SkyRadio device implementation](https://github.com/skynetto/RadioRds/blob/e0b2b15b72491f5aab627f8071b318fb46620e53/SkyRadio/RadioDevice.cpp)
and its `Enums.h` were acquired at fixed commit
`e0b2b15b72491f5aab627f8071b318fb46620e53`. This is a third-party Windows
implementation, not an authenticated vendor GUI release or a same-stepping
driver. It adds a concrete host-side comparison with the Linux USB code.

Its register SET helper explicitly permits POWERCFG through BOOTCONFIG,
including TEST1/TEST2, but the inspected initialization writes SYSCONFIG1/2/3
and POWERCFG. No test-register unlock call was found in that device file.
Scratch reports persist configuration/versions through the USB device; they
are not an IQ capture buffer. A 61-byte endpoint-2 buffer is allocated and
freed, but has no producer/consumer transaction in the inspected file.
Allocation and endpoint capacity alone do not establish a hidden output.

The header uses the older CHIPID DEV mask `0x0200` and firmware mask `0x01ff`.
Do not copy its identity decoding to a later device with a four-bit DEV field.
This is another reason to separate family compatibility from a stepping match.

### Shared GUI name is not a receiver-family identity

An original [Silicon Labs Si270x EVB guide retained by Arrow](https://static5.arrow.com/pdfs/2010/10/2/16/44/45/919/slab_/auto/si270xevb.pdfsrcsupportdoclibrary.pdf)
adds a useful software-search boundary. Its installation list also names
`Si47XXGui.msi`; section 5 explicitly explains that the Si270x GUI retains
the Si47XXGui name because it concurrently controls the Si473x AM/FM
receiver on the baseboard. Thus neither the executable/installer name nor
an amplifier firmware-selection screen identifies Si4702/03 support.

This broadens package discovery to related EVB distributions, but any
recovered package still needs internal target/plugin and revision inspection.
Do not import Si270x amplifier firmware or Si473x commands as Si4703 hidden
register evidence. The indexed original vendor guide was inspected; the
direct PDF acquisition did not complete, and no installer was acquired from
this lead. No package hash or same-version claim is available.

### Open work

A [retained USB MCU image candidate](FM_USB_MCU_REVERSE_ENGINEERING.md) is now
available for further static analysis. It supersedes the earlier general
missing-input blocker, while vendor GUI and exact silicon identity remain open.

Further comparison of the acquired [William Gao implementation](https://github.com/w-gao/Si470x/blob/main/Si470x.cpp)
did not supply a new test-mode sequence. Its downloaded bytes were checked
against the repository's Git blob identity. This is a modern third-party
library, not period factory software or an established stepping match.

Some investigation paths remain limited by missing inputs: the identified
vendor GUI/example packages have not been acquired, and no external candidate
has provided an attributable nonstandard test transaction or measured signal
outlet. Additional ordinary libraries cannot establish the absence of hidden
silicon modes. The useful next input is an attributable EVB CD/software image,
factory utility, MCU firmware image, or a same-revision test transaction trace.
Exact player identity would select candidates more accurately but would not
by itself reveal an undocumented IQ command. Hardware actions remain separate.

No external implementation reviewed here establishes an IQ extraction mode.
The search remains open, with these next concrete targets:

1. Recover the EVB CD/GUI and AN264SW archive from an attributable distribution.
   Inspect command builders and scripts without running the installer or updater.
2. Trace any Si4702-16/B17/C19-specific test sequences in OEM sources. Record
   the exact chip revision and transaction recipient for every apparent opcode.
3. Compare genuine nonzero TEST2/BOOTCONFIG writes or command IDs outside the
   known property interface, if found. Current compared sources supply no such
   verified IQ sequence.
4. Locate a signal output, clock and mode selection before calling any digital
   data IQ. GPIO stereo status, RDS words, MCU ADC audio and chip-internal I/Q
   blocks are distinct evidence.

The player's actual stepping is a future hardware identity question. It does
not prevent further PC research, but it prevents claiming that these candidates
are already compatible with this unit. No device tests were performed.
