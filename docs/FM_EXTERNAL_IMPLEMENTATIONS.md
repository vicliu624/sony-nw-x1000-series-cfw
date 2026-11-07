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
stepping match. The ZIP has not been acquired: the tested Silicon Labs endpoint
returned Access Denied HTML, and a candidate Skyworks migration path returned
HTML. Neither response was treated as usable software or executed.

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

Both legacy endpoints returned HTTP 403 HTML during acquisition. A successful
connection or a `.zip` suffix must not be counted as a recovered software pack.
An Internet Archive item search returned manuals and unrelated material, not
an identified software release. The archive-index request did not yield a
usable package; this is not proof that no historical copy exists.

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
