# RF hardware, modulation and evidence limits

## Latest full-radio physical result (2026-10-30)

The autonomous X1060 TX worker sent ten explicit v1/v2 binary cases without a
live Terminal dependency. It recorded ten MAC completions and no MAC failures.
Cardputer0.1.2/ESP-IDF5.5.1 delivered all eight nonempty cases byte-for-byte,
including251/1469/1470 bytes. Its callbacks did not report the two zero-length
cases; empty application delivery is not qualified. Evidence:
work/autonomous-espnow-test/live/tx01/acceptance.json.

A separate60-second receive run admitted17 matching-source encrypted frames
without installing the sender's LMK on X1060. One retained33-byte v2 frame was
fully MIC8-authenticated and matched the known test payload. For this tested
S3/headless IDF5.5.1 setup, the working profile is nonce prefix00, legacy subtype-
masked AAD, Key ID3, and effective wire key AES-128-ECB(PMK, API LMK). Raw API LMK
alone failed authentication. This is an observed configuration, not a universal
claim across every ESP-IDF initialization/PMK behavior. Evidence:
work/autonomous-espnow-test/live/rx01/acceptance.json. Keys remain ignored/private.

Current native source adds explicit xnow_ccmp_espnow_* primitives for that
profile; it does not silently change the generic management primitives. Host
sanitizers and ARM926/original libc authenticate/recreate the physical frame and
reject bad MIC, wrong key/ID and replay:work/physical-ccmp-profile/report.json.
Encrypted endpoint integration, reverse encrypted RF, larger encrypted frames
and durable peer lifecycle still require validation.

Both physical workers completed stock restoration and authenticated Terminal
access was re-established afterward using the same fixed device code. No Sony
updater, system partition or module file was written. These bounded runs do not
qualify all APF/USB/sleep transitions or explain the previous Wi-Fi interruption.
Earlier statements below that describe only synthetic admission/profile evidence
are historical and must be read with this newer physical result.

Scope: Japanese NW-X1050/NW-X1060. Current physical unit is NW-X1060. The hardware identification sections distinguish stock analysis from physical observations. The ESP-NOW sections also cover explicit channel8 over-air tests; they do not imply unperformed FM/1seg measurements.

## FM

Existing physical observations establish I2C0-0010 named Si470x and /dev/v4l/radio0 named Silicon Labs. FM Tuner. The matching stock module is icx_si470x_radio_tuner.ko. This identifies the family, not the installed subtype or stepping. Do not label the board Si4703/RDS-capable from this alone. Si4702 and Si4703 differ in RDS support; old Si4700/01 naming must not be silently excluded either.

The classic Si470x broadcast receive architecture and band/spacing/de-emphasis registers support investigation of 76-108MHz FM, mono/stereo, 50/75us de-emphasis and 50/100/200kHz channel spacing, subject to subtype and board behavior. Spacing is not IF bandwidth. The project has a 76-108MHz adapter; complete board reception/restoration qualification is separate. Later Si4702/03-C19 documentation describes the family and compatibility, not proof of that revision in a 2009 player.

AM/LW/MW/SW/SSB/CW, airband AM, general narrowband-FM scanning and arbitrary FSK decoding are not established by a broadcast-FM chip. Si473x multi-band and Si471x transmit capability cannot be attributed to Si470x. Internal I/Q blocks do not establish a raw I/Q host interface. Driver exposure is tuner control/status and audio routing; no raw I/Q path was established. R2A15602LG is an audio driver, not the FM RF identity.

## 1seg

Exact commercial tuner/demodulator identity remains unresolved. The shipped dtv.ko is MP200 DTV transport/DMA code with dtv_read/poll/ioctl and suspend/resume, not an identifier of the RF silicon. load_1seg only inserts that module.

SpiderApp contains DtvTunerHAL.cpp, /dev/i2c/0, /dev/dtv and a 188-byte TunerRead check. Control is in user space. In the fixed stock SpiderApp, the initialization region around232360-232478 queries /dev/icx1111_sysinfo with request0x80047306. Matching Sony GPL calls this GET_DS_STAT; named values are SYSINFO_DS_140=1 and SYSINFO_DS_160=2. The branches select control address values0x20/0x30 and initialization routines231a14/231f7c. These are internal selectors, not verified part numbers or RF MHz bands. Do not infer current physical selection without its value, or guess a vendor from those numbers.

The HAL diagnostics include TMCC/partial-reception flag, BER/PER/MER, OFDM mode, guard interval, modulation, code rate, interleave and segment count. These establish useful reverse-engineering targets, not implemented public diagnostics or support for every value.

ISDB-T uses segmented OFDM and defines DQPSK/QPSK/16QAM/64QAM carrier modulation. This is standard-level capability, not a verified per-chip support matrix for this board. 1seg partial reception does not establish full13-segment TV or DVB-T/T2/DTMB/CMMB/ATSC/DAB compatibility. Similar QPSK/OFDM modulation alone is insufficient: bandwidth, framing, synchronization and FEC differ. The established software path is transport stream packets, not raw complex samples. No arbitrary IQ output or reprogrammable demodulator was established.

### Offline HAL control-path analysis

REA 6.5.0 with Ghidra 12.1.4 analyzed the unmodified stock SpiderApp
(SHA256 80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85).
No target code was executed on the player and no hardware operations were performed. Captured REA responses and
independent ARM disassembly remain under ignored work/rf-rea-hal.

- The actual initialization entry is 0x2322bc; 0x232360 lies inside it. It opens
  /dev/i2c/0 and /dev/dtv, queries GET_DS_STAT, selects the 0x20/0x30 control
  value and calls 0x231a14/0x231f7c. A second target value defaults to 0xc0.
- REA pseudocode shows 64 and 25 single-register-write call sites respectively.
  0x2307f8 selects the I2C target with ioctl 0x703 and writes exactly two bytes:
  register index and value. ARM instructions confirm that the supplied address
  value is shifted right one bit before that ioctl. Do not confuse the stored
  value with the bus address or identify a chip from it alone.
- The first branch copies a fixed 50-byte table from 0x483110 and sends it through
  0x23069c; the second copies another 50-byte table from 0x483142 and sends it
  through 0x230740. Both helpers call write, not read. The latter constructs
  FE / secondary target / payload / FE. This is a control-transfer wrapping
  observation, not proof of a physical two-chip layout or an analog IF node.
- 0x230930 copies a 400-byte table from 0x482df0. Its 50 eight-byte rows have
  selectors 13 through 62 and four parameter bytes each. It compares the caller's
  selector and constructs write transactions. That is a channel-programming
  fingerprint, not a sample buffer or a verified frequency/PLL equation.

- REA decompiled 0x230888 as a two-message I2C_RDWR (ioctl 0x707)
  transaction: write one register-index byte, then read the requested byte count
  into a caller buffer. This is a register/block-read primitive; no sample-buffer
  address or IQ payload format was established by that helper.
- 0x2304e0 configures /dev/dtv with reset, interrupt unit 20, serial input 1,
  packet-size selector 0 and byte-order selector 1. Matching GPL definitions map
  these to serial 188-byte TS packets and the driver's little-order setting.
  ARM disassembly confirms packet selector zero where Ghidra omitted the ioctl's
  third argument. This is positive evidence of the normal TS capture setup,
  not an IQ-mode setup. It does not prove all possible hardware test modes absent.

These results recover original control behavior and provide register fingerprints
for matching chip documentation. They do not yet identify commercial silicon,
register meanings, ADC sample rate or an IQ export command. Some decompiler call
prototypes omit arguments, so argument counts/widths must be checked against ARM
instructions before treating pseudocode as an interface definition. Physical
internal DSP stages are not reconstructed merely by decompiling the host HAL.

### Selected-branch status and offline instruction replay

Historical physical /proc/cpuinfo (work/terminal-live/research-20261027T123751Z)
reports Revision 0x0ea1a582. Applying the exact GPL getter expression
((system_rev & 0x1000) >> 12) | ((system_rev & 0x08000000) >> 26) yields 2,
which predicts the 0x30 / 0x231f7c branch on that captured boot. This is not a
new live reading or commercial silicon identification. The later connection
attempt did not reach the player; Windows initially selected its VPN route and
an explicitly Wi-Fi-bound socket then timed out with ARP Unreachable.

REA found 65 incoming references to register reader 0x230888. The status routine
is 0x23262c; its observed caller 0x22f904 associates the output with the original
BER/PER/MER(dB)/MODE/GUARD/MODURATION/RATE/INTERLEAVE/SEGMENT NUMBER/IF AGC DAC/
AGC LEVEL diagnostic columns. For branch 0x30:

| Registers | Observed software use |
| --- | --- |
| 0x60 bit0 | Measurement-ready gating; reuse cached values otherwise |
| 0x9d-0x9f | Assemble a 24-bit count for rate conversion |
| 0x76 bit0 | Pulse after rate processing; actual writes, not a pure read |
| 0x8b-0x8d | Assemble a 24-bit measurement and convert through a fixed MER table |
| 0xb0 | Low nibble acquisition stage; upper fields feed mode/guard conversion |
| 0x80 bit5 | TMCC validity gate; invalid output returns 0x80000000 |
| 0xb2-0xb4 | Extract TMCC-related flags and transmission parameter fields |
| 0x82 | Byte delivered in the IF AGC diagnostic field, not calibrated dBm |
| 0x1e bits0x30 | Conditional control update using IF AGC thresholds 0x4c/0x7d |

The general status routine performs writes. In its automatic-control branch,
IF AGC below76 can set register0x1e bits0x30; above125 can replace those bits with
0x20. This is observed software control behavior; physical gain effects remain
unqualified. Do not call the whole status function as a side-effect-free probe.

work/rf-rea-hal/replay_status.py executes original ARM instructions at0x23262c
under Unicorn with I2C calls substituted. Eight cases pass: ready counter,
cached counter, rate saturation, two MER table extremes, invalid TMCC and two
IF AGC control thresholds. Every intercepted status read is one byte; supplied
counter1 produces internal BER239/PER390652 and a simulated zero MER-table input
produces packed0x1e00, corresponding to the caller's 30.0 display format. These
are synthetic algorithm checks, not live RF measurements or chip calibration.
No ADC/FFT sample stream or IQ test-output selector has been identified in the
examined paths. Unused undocumented silicon modes remain unknown.

### Driver transport and modulation-expansion boundary

Goal: investigate additional UHF demodulation using the installed 1seg hardware.
Statistics alone are not that goal. The ESP-NOW method supplies a useful workflow
(identity, original loading/control path, instruction replay, bounded hardware
validation), but vendor Action-frame handling reuses the Wi-Fi PHY; new 1seg
physical-layer modulation may require a different kind of hardware capability.

REA/Ghidra analyzed the shipped dtv.ko, SHA256
421fb85fa2e90b2019cc2a47fb17761e072121b97fc47cc668dbd9f5c0f76cac.
Named dtv_read/ioctl/callback/open/reset and DMA-start bodies agree with the
relevant published MP200 driver behavior:

- read() checks iunit * packet-size alignment, waits for ready ring clusters,
  then copies complete clusters to user space. No software TS sync-byte scan,
  PID selection, CRC filtering, OFDM operation or FEC decode was found there.
- The callback advances cluster accounting from the hardware packet position.
  FIFO/DMA/ring errors stop the transfer; these are not software per-TS-packet
  demodulation/error-correction decisions.
- The examined ioctl interface exposes 188/204-byte packet choice,
  serial/parallel capture, byte order and DMA lifecycle. It exposes no raw ADC/IQ
  selector. Hardware synchronization or an undocumented capture mode is still
  unknown; absence of a software filter does not prove unframed input works.
- Compiled defaults are mode1, buffer15040 bytes, debug0. With stock iunit20 and
  packet188, the buffer holds exactly four3760-byte clusters. Changing packet
  selector to204 while keeping unit20 exceeds the driver's four-cluster space
  requirement and rejects. Unit18 fits in a synthetic ioctl test. This does not
  establish that the RF chip emits204-byte packets or usable parity data.
- Opening /dev/dtv itself mutes external audio, enables regulators according to
  DS configuration, changes pinmux/clocks and allocates DMA resources. An O_RDONLY
  open must not be described as a harmless metadata query.

The ignored work/rf-driver-rea/replay/read_replay.py relocates an analysis-only
copy of the original module and executes its ARM instructions with kernel services,
DMA memory and MMIO substituted. Eight read tests pass, including all-zero data
without0x47, arbitrary bytes,204-byte chunks, ring wrap and error cases. Eight
ioctl tests pass, including invalid selectors, alignment/capacity constraints and
active-state rejection. The copy preserves synthetic non-TS bytes exactly. This
proves the software-copy property only; no RF or SoC sampling engine was tested.

### Upstream demodulator fingerprint comparison

Pinned Linux source comparisons are retained with URL/SHA256 under ignored
work/rf-research/comparison. The branch0x30 matches several terrestrial-register
conventions in Toshiba tc90522.c: FE tuner forwarding prefix, reset01=40,
B0 mode/guard fields, B2-B4 TMCC layout,8B-8D measurement and9D counter layout.
Most significantly, the29 Sony table values for2..30dB match that driver's
terrestrial CNR polynomial documented in its comment within0.000247dB (maximum absolute floating-point
comparison difference). This is a strong register/algorithm lineage lead, not
proof that a2009 X1060 contains the later quad-demodulator TC90522 itself.
The Sony diagnostic labels its displayed estimate MER; upstream exposes CNR.
Do not silently equate those labels with independently calibrated RF quantities.

Primary comparison:
https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/c7decec2f2d2ab0366567f9e30c0e1418cece43f/drivers/media/dvb-frontends/tc90522.c

The branch0x20 also has a Fujitsu mb86a20s-style register organization (70 reset,
04/05 indirect registers,6D/6E TMCC selection and64-66 error-count reads), requiring
separate identification. Features of one branch must not be applied to the other.
Neither comparison justifies undocumented register writes on the physical player.

The stock file inventory contains sd8686.bin for WLAN and OMF dtv/*.mp201 files.
The latter configuration names AAC/H.264/power-save components; their presence is
not evidence of downloadable RF demodulator code. The examined RF init routines
send register/configuration tables, not an established executable image loader.
A chip-resident ROM, hidden RAM/test mode or raw output remains unqualified.

Next discriminating evidence is exact silicon documentation/identity and an
upstream raw/test/FEC-bypass output path. If such data can reach the existing DTV
DMA, the verified copy path can be reused; otherwise driver changes alone cannot
recover modulation information already removed before TS output. No new modulation
has been demonstrated and no device changes were made during this review.

### Joint numerical/register comparison and current read-only corroboration

A later certificate-pinned Terminal connection succeeded using the new supplied
session. Standard proc/sysfs reads repeated Revision0x0ea1a582, loaded module dtv,
mode1 and buffer15040. On-device /lib/modules/dtv.ko MD5 matches the offline file
(3840bb125cc9b76e4331d94437fa2963). This establishes file correspondence, not a
byte-for-byte readback of loaded module RAM. /dev/dtv was not opened and no tuner
register, regulator or RF initialization command was issued.

The joint comparison now separates four quantities for every original table node:
Sony's nominal calibration label, the pinned upstream COMMENT equation, the actual
Sony ARM result at that exact input and at input-minus-one, and the independently
compiled upstream INTEGER expression. The source hashes and29 original input
words are checked; the integer expression agrees on host and ARM926/QEMU.

| Original input | Node label | Upstream comment equation (dB) | Sony ARM exact input | Sony ARM input-minus-one |
| --- | --- | --- | --- | --- |
| 9778432 |2|1.999999895|0.0|2.0|
| 5735416 |3|2.999999752|2.9|3.0|
| 3903295 |4|4.000000023|3.9|4.0|
| 737184 |10|10.000003354|9.9|10.0|
| 70125 |20|20.000025311|19.9|20.0|
| 7573 |30|30.000206947|29.9|30.0|

The maximum COMMENT-equation/node difference is0.000246727519dB across29 inputs.
This is an input/output calibration fingerprint, not merely a common2..30 range.
The original ARM routine uses strict comparisons and clips fractional digits;
exact thresholds therefore do not behave like the labels. The table above is
synthetic register input replay, not a physical low-signal display observation.
The ARM runtime unsigned-division boundary is substituted with exact quotient/
remainder semantics in addition to the simulated I2C boundaries.

The upstream INTEGER code differs from its comment: fixed-point log/rounding,
a linear term43827/80 instead of549.1, and unsigned intermediate behavior.
For example, its extracted math returns3.997/9.988/19.968/29.952dB at the4/10/20/30
nodes. The2/3dB inputs wrap the unsigned intermediate and are recorded separately;
this subset replay does not establish how a complete frontend uses out-of-domain
or unlocked measurements. Do not describe the two full implementations as
bit-identical or infer a physical chip fault from those arithmetic-only tests.

Independent register comparison confirms common addresses AND raw bit fields:
B0 mode[7:6]/guard[5:4], B2 partial bit0, B3 layer-A modulation[7:5]/rate[4:2],
interleaving from B3[1:0]+B4[7], and segment count from B4[6:3]. Sony reads these
one byte at a time; upstream reads a six-byte TMCC block covering more layers.
The8B quality and9D error counters also share big-endian24-bit assembly, but
transaction sizes and rate scaling/reset behavior are not established identical.
Tuner forwarding has a common FE prefix; Sony adds a trailingFE. These differences
must remain in the evidence matrix rather than being rounded into an exact match.

Joint CSV/JSON and source hashes are in work/rf-research/comparison. The strong
conclusion is shared/highly similar terrestrial register/calibration lineage.
TC90514/22/27/32 are distinct candidate products, not assumed package variants.
A later product catalog cannot identify a2009 device. Exact silicon, MER versus
CNR physical definition, raw/test output and extra demodulation remain unresolved.

### Factory program: actual software gates versus sampling-test names

The unmodified stock /usr/local/bin/mptapp is3144248 bytes, SHA256
d3417610b5d20aaf8678cf07cd5cf0196fdd00b562d0fdc52e5c7aaf771eb59c.
Its UI contains RCVCHK,TSO,LOG,SubCH and STATE/SMPL text. Those strings do not
establish ADC sampling access. Four key HAL32-byte prefixes each match uniquely
against SpiderApp with a constant text offset, and both50-byte configuration
blobs plus all29 calibration-node words are identical. This is limited code/data
reuse evidence, not proof that every factory mode equals normal playback.

Original factory ARM at0xd6730 provides a more precise software boundary:

- It requires active state, state5 and a fresh roughly100ms status window before
  invoking the kernel-reader helper. The time helper uses gettimeofday-derived
  milliseconds; simulation substitutes time values.
- The lower helper accepts a188-byte logical request, select()s the fd and reads
  3760 bytes (20 packets). The upper helper caches/splits those into188-byte units.
- It checks the output's first byte against0x47. Non-TS data can already be copied
  into the caller buffer but the helper returns0x80000000 and resets its cache
  index. The kernel read tests preserve non-TS bytes; this HAL policy rejects them.
- A failed kernel read can invoke the original reset helper. Directly reusing this
  SDK path is not a passive byte recorder or a source of arbitrary IQ samples.

Six original-instruction replay cases validate active/lock/freshness/sync/error
branches with time/read/memcpy/reset boundaries substituted. No physical device
or capture engine is represented by those fake boundaries.

The identified IntTestOptionTunerImpl setter copies an8-byte option pair and
seeds a software RNG. Its read wrapper at0xd58dc can convert a successful inner
read into a synthetic error based on an enable flag and floating probability
threshold. Four instruction-replay cases validate this behavior, including
unchanged payload after injected failure. This identified interface is software
failure injection, not an ADC mode. Other test interfaces remain incompletely
mapped; their names must not be used as capability evidence.

The stream-control helper at0xd8904 is separately verified with four replay
cases. Branch0x30 writes register0x1d=0 for enable or0xaa for disable; the enabled
value is the same as normal initialization. Branch0x20 uses indirect50/51 indexd7
and changes low output-control bits. This does not identify electrical pin modes
or an ADC/FFT data selector. The factory TSO API is traced through livePlayer
virtual dispatch; complete live object ownership is not hardware-validated.

REA6.5 can resolve an unrecognized numeric function query through file-offset
fallback. Several wrapper/menu requests therefore returned unrelated functions.
They are explicitly quarantined under work/rf-factory-rea. Adding exact ELF
function symbols to an analysis-only copy resolves those wrappers correctly;
all allocated sections, addresses, sizes and BSS layout remain identical. Keep
VA/instruction checks separate from decompiler types, which can also omit
pass-through arguments. Original firmware and executable files remain unchanged.

Evidence: work/rf-factory-rea/summary.json, replay/*.json, seeded/input-proof.json
and query-resolution-limitations.json. No new UHF modulation or raw samples have
been demonstrated. A future independent byte-capture path can avoid HAL policy,
but still needs a proven upstream sample/test output and compatible SoC framing.

### Same-era integrated receiver comparison

Toshiba announced TC90541WBG/WLG in September2008, with samples scheduled for
October2008 and production in the first half of fiscal2009. This adds a same-era
portable1seg comparison, not an identification of X1060. Its announcement lists
36MHz crystal operation, WCSP60, a UHF low-IF tuner, TS output and I2C control.
The2009 Toshiba technical review places the RF tuner, ADC and OFDM demodulator
on the same die. Its documented signal path is mixer/complex BPF/IFVGA, ADC,
OFDM/FEC, then TS. These publications provide no raw-sample export command or
register map. Internal I/Q mixing does not establish external I/Q pins.

This prevents assuming that a physically accessible tuner-to-demodulator IF node
exists solely from the Sony HAL's forwarded control transactions. Conversely,
it does not prove that X1060 uses an integrated design: neither a package marking
nor a matching register/init sequence was found. TC90541 must not be substituted
for the unidentified device in a driver or test script. The manufacturer's
limited modulation/mode list also illustrates why family/standard capabilities
cannot be assigned wholesale to an unidentified portable implementation.

Primary sources (local copies and SHA256 provenance under work/rf-research/tc90541):
- https://www.global.toshiba/jp/news/corporate/2008/09/pr1701.html
- https://www.global.toshiba/content/dam/toshiba/migration/corp/techReviewAssets/tech/review/2009/12/64_12pdf/f03.pdf

### Third stock HAL copy in Responder

A rootfs ELF marker inventory finds /dev/dtv,DtvTunerHAL and/dev/i2c/0 together
in SpiderApp,mptapp and Responder. Original Responder SHA256 is
71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261.
Seven32-byte helper/init/status prefixes each have one matching Responder entry.
The244 known-helper direct references also match SpiderApp after adding e5570
to Responder source/target addresses, including branch conditions/link flags.
This provides no additional direct bus-access path in that copy. It does not
prove every HAL instruction identical or that no other device interface exists.
The original ELF inventory used file/string markers, not semantic completeness.
Evidence:work/rf-call-audit/stock-elf-interface-inventory.json,
responder-prefixes.json,responder-analysis/comparison.json. No device accessed.

### Factory SMPL producer narrowed to a Boolean flag

Original producer0x3cad8 builds diagnostic object0xad6b48. At3cb54..3cb6c it
loads signed input byte+18 and stores1 to output+1c only if that byte equals1;
otherwise it stores0. Five ARM926 original-instruction prefix replays with input
0,1,2,127,255 produce0,1,0,0,0. The initial gate2ddd8 is substituted; execution
stops before event delivery. Source flag semantics remain unresolved, but SMPL
here is a normalized Boolean, not a sample count/rate or array.

The function constructs event06000001; callback13814 checks that event and
stores the payload pointer through global2ebb2c, which the display reads. Event
layout/delivery has not been fully replayed, so the object-to-display connection
remains a static trace. This supersedes only the producer-unknown statement
below. Evidence:work/rf-call-audit/factory/smpl-producer.json; fixture:
work/rf-tuning-research/replay_smpl.py. No hardware accessed.

### Factory SMPL display is not an established sample-export interface

The factory format at VA254b64 contains STATE:%d SMPL:%d alongside BER/PER/MER,
mode/guard and AGC diagnostics. Its use at151fc prepares snprintf arguments;
15200/15204 load object+18 into the STATE argument and1520c/15210 load object+1c
into the SMPL argument. The object pointer is loaded through the global pointer
literal at14bb8. These are displayed integer fields, not a demonstrated sample
array or sampling control. The producer and exact meaning of+1c remain unresolved;
do not label SMPL as ADC samples, sample rate, or a test-count setting without
tracing that producer. This closes only the text-based inference, not the
underlying factory diagnostics investigation. Evidence:work/rf-call-audit/
factory/smpl-xrefs.json and original instructions151b0..15278; scanner:
work/rf-tuning-research/find_smpl.py. No hardware accessed.

### Physical-memory mapping identified as acoustic parameters

The earlier unresolved33a5d000 mapping now has an exact GPL definition.
include/asm-arm/arch-mp200/mp201_mem.h defines OMF_MC_SDRAM_BASE=33970000,
OMF_MC_ACOUSTIC_PARAM_MEM_ADDR=base+000ed000 and
OMF_MC_ACOUSTIC_PARAM_MEM_SIZE=00001000. Both computed address and4096-byte size
match the original factory mmap arguments. This identifies the documented OMF
acoustic-parameter shared-memory region; it is not evidence of a demodulator
register bank or RF sample buffer. The prior tentative region-identity statement
below is superseded by this exact source-to-binary correspondence. Neither the
running kernel nor physical contents were accessed.

Header SHA256:819a28cad1f14a87fe663d0fe5650f3f3a98f422baa8124512f2c921058b106c.
Evidence:work/rf-research/memory-map/mp201_mem.h,omf-mapping-proof.json.
This closes these two literal /dev/mem uses as a promising RF-sampling lead;
it does not prove all physical-memory or factory interfaces exhausted.

### Factory physical-memory mapping observations

Literal-pointer/ARM-PC-relative-load analysis finds two uses of the /dev/mem
string:19caa8 and1a8088. Both construct mapping offset33a5d000, length1000(hex),
protection3 and flags1. Original ARM success-path replay of19ca9c confirms
open flags1002, a4096-byte read/write shared mapping, then descriptor close.
All libc boundaries are simulated; no real mapping or device access occurs.
The second site's map arguments are from disassembly, not executed replay.

Nearby names include OmfMgr_clearIF and OMF manager configuration; following
code initializes small fields in the mapped page. This suggests a media-manager
interface region but does not identify its physical backing. No DTV sample
export is established. A targeted search of selected platform GPL C/headers for
the literal address found no definition; computed/reserved mappings may not
contain that literal. Neither the two xrefs nor this search prove completeness.
Evidence:work/rf-call-audit/factory/devmem-xrefs.json,devmem-replay.json;
fixtures:work/rf-tuning-research/find_devmem.py,replay_devmem.py.

### Auxiliary ADC node is not the demodulator ADC

The SHA-verified Sony GPL kernel archive contains drivers/char/mp200_ad.c and
include/asm-arm/arch-mp200/mp200_ad.h. The /dev/mp200_ad file operations expose
open/release/ioctl, not a read stream. Eight ioctls select battery, adapter and
other ADC channels. Each conversion uses GPIOCORE_PWC_ADMODE and waits for an
interrupt; the result from GPIOCORE_PWC_ADDATA1+channel*2 is masked to8 bits and
copied as an int. There is no DMA/continuous sample API in this driver. The
separate kernel helper includes an800us delay before polling; this is an
implemented delay, not a hardware maximum-rate specification. Existing cradle
code calls the helper for resistor-coded accessory identification.

This identifies an auxiliary power-control ADC software path, not access to the
RF demodulator's internal ADC. No RF IF/IQ connection to these channels was
established. Do not repurpose the node as a sampling source or infer that its
name supplies an SDR route. GPL source analysis is not a byte-identical check
of the running kernel. Extracted members, SHA256 provenance and assessment:
work/rf-research/adc/. Original archive provenance:sources/kernel-download.json.
No device node was opened or conversion requested.

### Factory versus player direct bus access

A SHA-verified scan of original mptapp finds the same244 direct B/BL references
to the four matching bus helpers (5 indexed writes,4 forwarded writes,170
register writes,65 register reads). Adding0x158f40 to factory source/target
addresses makes the complete sets of call location, target, branch condition
and link flag equal to SpiderApp. Independent GNU ARM objdump confirms the
factory reference set. No factory-only direct reference to these helpers was
found. This is stronger than the earlier four-function-prefix comparison, but
still does not equate all factory behavior or exclude other interfaces/indirect
calls. Factory device-path strings also include /dev/mem and /dev/mp200_ad;
strings alone do not establish RF access or ADC sample export, and neither node
was opened. Those paths require independent call-site and driver analysis.
Evidence:work/rf-call-audit/factory/report.json,device-strings.json and
factory-comparison.json; scanner:work/rf-tuning-research/audit_factory_calls.py.
No device accessed and no physical register writes performed.

### Remaining direct-read sites resolved

A further18 original-ARM cases resolve the three remaining read sites:
0x231990 and0x2319d0 belong to0x23192c, which reads and modifies EB bit1 for
selector20 or1e bits5:4 for selector30; it then sets the existing automatic-control
global. Four byte seeds and both Boolean arguments are replayed for each branch.
0x23359c belongs to0x233528 and polls80 bit3, once if clear or up to10 times if
set. Its length derives from saved r7=1. The fixture substitutes channel writing,
delay, reset helper and mode helper; it does not execute or qualify a full tune.

All65 identified direct read sites now have length1 evidence from local argument
analysis or specified original-ARM executions. The earlier62/65 report is an
intermediate coverage result, not the current remainder. The29-site local scan
remains weaker than executed coverage and arbitrary inputs/indirect calls are
not exhaustively proven. No bulk ADC/IQ/FIFO read was observed through this
helper. Further sample-export research must investigate another interface,
factory-only paths or documented unused silicon modes rather than treating these
normal single-byte status/control accesses as a sample stream.
Evidence:work/rf-call-audit/remaining-report.json,coverage-union.json;
fixture:work/rf-tuning-research/replay_remaining_reads.py. No hardware accessed.

### Post-tune helper behavior

Original branch0x30 tune flow0x23103c invokes0x230dd8,0x230e90 and0x230fd8
after acquisition/TMCC polling. Separate ARM926 Unicorn replay verifies24 cases:
three helpers, four initial-register byte patterns and two values of global
0x806ede. I2C reads/writes are substituted with a writable register model;
physical register semantics, read-only bits and self-clearing behavior are not
modeled or qualified.

- 0x230dd8 sets bit0 of60 and77, then replaces76 bits6:4 with011.
- 0x230e90 sets60 bit0 and77 bits1:0, selects76 bits6:4 as011 or001 according
  to0x806ede, then writes76 with only its bit0 and finally zero.
- 0x230fd8 writes5c=00, reads5c and ORs70 before writing it back. The model
  returns the last stored value; a physical read may differ.

All reads in these cases are one byte; no sample payload, sample destination or
stream-format selector is exposed by these helpers. Registers60/76/77 also occur
in the analyzed status/counter path, but a complete hardware bit definition is
not established. Do not infer ADC export from these operations or replay them
on hardware as a diagnostic shortcut. Evidence:work/rf-tuning-research/
replay_post_tune.py and post-tune-report.json, with original-input SHA verified.

### Direct bus-helper reference audit

An original-SHA-checked scan of executable ELF sections decodes aligned ARM
B/BL immediates targeting the four known I2C helpers. It finds5 indexed-write,
4 forwarded-write,170 register-write and65 register-read references (244 total).
All lie in0x230000..0x233fff. GNU ARM objdump independently agrees on every
source/target pair. This scopes further analysis to the local HAL; it does not
prove all instructions reachable or exclude indirect calls, Thumb code, inline
I2C implementations or another device interface. In particular, absence of an
external direct reference is not proof that hidden test commands do not exist.
Extended original-ARM status replay now covers40 synthetic cases across both
0x20/0x30 branches, five register patterns, ready/not-ready and automatic/manual
control. It observes43 distinct read sites, all with length1. The24 post-tune
cases also record their call sites. Combining these executed observations with
the explicitly weaker local argument scan covers62 of65 direct read sites;
the remaining addresses are0x231990,0x2319d0,0x23359c. No large sample read was
observed. This is input-dependent coverage, not exhaustive hardware or control
flow qualification. Reports:work/rf-call-audit/status-coverage/report.json and
coverage-union.json. Fixture:work/rf-tuning-research/replay_read_coverage.py.

A conservative local argument scan recovers length1 at29 of65 read sites.
The remaining36 sites depend on definitions outside the short straight-line
window and remain unresolved; they are not counted as one-byte reads. This
local scan does not establish predecessor reachability, stack aliasing or callee
memory effects. It is prioritization evidence, not proof that all reads are
single-byte or that a sample-export path is absent. Report:work/rf-call-audit/
read-lengths.json; script:work/rf-tuning-research/audit_read_lengths.py.

Reproducible scan:work/rf-tuning-research/audit_calls.py; evidence and instruction
contexts:work/rf-call-audit/report.json,calls.txt,independent-check.json.

### Related-part pin documentation

The Skyworth8M79B service manual reproduces a tentative Toshiba TC90517FG
specification on PDF pages23..26. It describes low/direct IF and baseband IQ
INPUT, with serial/parallel MPEG TS OUTPUT. Its factory-test pins are documented
as inputs with prescribed ties, not an exposed ADC sampling bus. The excerpt
contains no raw-IQ export register definition. This is comparison evidence only:
it is not the Japanese X1060 schematic, does not identify its silicon, and must
not be used for board wiring or guessed test-pin activation.
Source:https://www.manuallib.com/download/2023-11-07/%E5%88%9B%E7%BB%B4%E7%94%B5%E8%A7%868M79B%E5%BA%95%E7%9B%98%E7%BB%B4%E4%BF%AE%E6%89%8B%E5%86%8C.pdf
The web reader retrieved the excerpt; direct archival download returned HTTP403.
No local PDF hash or archived-copy verification is claimed.

The additional GL861 Friio terrestrial initialization has36 writes; its exact
shared pairs with Sony are01=40,38=01 and71=00 (including repeated71=00 entries).
These sparse matches do not identify hardware or supply a sampling mode.
The em28xx PX-BCUD route inspected here attaches the satellite demodulator;
its satellite initialization is excluded from the terrestrial comparison.
Evidence:work/rf-research/pt3/friio-init-comparison.json and pinned sources.

### Public initialization comparison limits

Pinned Linux tc90522.c explicitly lacks complete chip initialization. PT3
pt3_i2c.c invokes pretranslated initialization stored in board ROM; comparing
Sony against that C wrapper cannot establish a mismatch. Additional pinned PT1,
GL861 and em28xx sources are retained under work/rf-research/pt3 with URL/SHA256
provenance. PT1 has public VA1J5JF8007T configuration arrays for20/25MHz clocks;
these are board/module configurations, not an identified X1060 part. The25MHz
array shares75=0a with Sony, while its1c/1d/1e and76 values differ. One shared
pair is not an identifying fingerprint; different values do not independently
exclude a related core with another clock, IF or TS configuration. Machine-read
pair comparisons are in sony-init-comparison.json. No upstream initialization
or undocumented mode is applied to the device.

### Initialization sequence replay

A separate original-ARM replay of0x231f7c confirms25 direct register writes and
one50-byte forwarded payload in execution order. memcpy and both write helpers
are substituted; no hardware is accessed. In particular, the decompiler omitted
the value argument for register0x76: the executed original instructions supply
0x08. Do not use that incomplete pseudocode call as a valid register API.

The forwarded50-byte payload has25 tag/value pairs. Its33..36 values are
76449249, the channel13 parameter. The subsequent channel writer repeats only
10 pairs (six fixed configuration pairs and four channel bytes), surrounded by
09f0/09f4. The initialization payload instead ends09f0; this is not evidence
that the initialization and retune transactions can be reordered or replaced.
No sample-buffer upload or RF microcode loader is present in this executed
initialization path. Hidden commands and unexecuted paths remain unqualified.
Report and original-SHA-checked fixture:work/rf-tuning-research/init-report.json
and replay_init.py. This is offline control-flow evidence, not a bus capture.

### Channel programming boundary

Original SpiderApp ARM function0x230930 was replayed with memcpy and the I2C
write boundary substituted; no device was accessed. All50 channel entries13..62
reproduce their table payloads. The four-byte parameter, interpreted big-endian,
increases by0x01800000 per channel, from76449249 to bfc49249. The writer sends
09f0, a20-byte tagged parameter sequence, then09f4. Tags33..36 carry the four
parameter bytes; their physical tuner-register interpretation is not established.

Inputs12 and63 are not rejected. With caller R4=0x12345678, both produce
78563412; with R4=0xa5a5a5a5 they produce a5a5a5a5. This demonstrates dependence
on saved caller state outside the valid table-selection path. Factory UI bounds
are separate from this lower-level writer. Do not widen the UI bounds and call
this function with unchecked channel numbers. Any future tuning extension needs
an independently validated encoder and explicit frequency/parameter bounds.

The constant step is a protocol fingerprint, not proof of a PLL reference clock,
IF frequency, continuous tuning range or additional modulation support. No new
frequency or modulation was demonstrated. Evidence and reproducible PC-only ARM
replay:work/rf-tuning-research/replay_channels.py and report.json. The fixture
verifies the original SpiderApp SHA-256 before executing its instructions.

## Wi-Fi

Stock sd8686.ko and its firmware, plus the earlier live sd8xxx loaded-driver observation, strongly identify a Marvell88W8686-family WLAN path. Exact package/stepping and every RF front-end option are not identified. Sony X1000 is a b/g product; do not infer5GHz availability from a family brief or driver channel tables.

802.11b PHY uses DBPSK at1Mbps, DQPSK at2Mbps and CCK at5.5/11Mbps. 802.11g OFDM uses BPSK/QPSK/16QAM/64QAM through54Mbps. These PHY modes are for Wi-Fi frames; no arbitrary waveform/IQ programming interface was established. Bluetooth coexistence means coordination with a separate radio, not built-in Bluetooth capability. Do not equate generic BT files in a shared rootfs with populated hardware.

## Sources

- Local evidence: docs/HARDWARE.md, docs/apps/FM_RADIO.md; work/rf-research/module-inventory.json and extracted GPL/header material. Proprietary files remain ignored.
- Sony GPL catalog: https://oss.sony.net/Products/Linux/Audio/NW-X1050.html ; kernel archive SHA256286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309.
- Skyworks AN332 product-function matrix: https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN332.pdf . Distinguishes FM-only/RDS/AM/SW/transmitter families.
- Skyworks AN230 Si4702/03 programming guide: https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN230.pdf . Do not apply revision-specific commands blindly.
- ARIB STD-B31 English standard: https://www.arib.or.jp/english/html/overview/doc/6-STD-B31v1_6-E2.pdf . Standard-level modulation, not board identity.
- Marvell manufacturer88W8686 announcement: https://www.marvell.com/company/newsroom/marvell-introduces-worlds-first-ultra-low-power-90nm-wlan-single-chip-solution.html . Family announcement mentions a/b/g; board options differ.
- Manufacturer-submitted module operating description hosted by FCC archive: https://fccid.io/OMC287380/Operational-Description/Operating-Description-1228683.pdf .88W8686 b/g PHY modulation comparison; this module is not proof of Sony's exact module.

Remaining identification work: match Japanese-board documentation/markings or a verified safe identity-read interface; map the two DTV initialization register sets to a real datasheet. No unrelated vendor/model is substituted for missing evidence.

## ESP-NOW development status

Target: one Japanese NW-X1060 on the 1.11 platform and an original ESP32-S3
Cardputer on COM17. This is not ADV. The identified XNOW0.1.0-dev.8 worker
passed physical bidirectional96-byte exchange with application ACKs and stock
restoration. It remains a fixed-length, plaintext, poll-driven ESP-NOW v1 subset,
not a complete protocol stack. TCP/IP Terminal is only a control/deployment/log
channel. See [implementation mechanism and remaining work](ESPNOW_IMPLEMENTATION.md)
for the radio hook, memory reservation, mailbox, original loading and SDK design.

### Physical evidence

- Authenticated Terminal reports sd8686-9.70.3.p32-26409.p51-(FP4), Managed
  eth0, Ethernet type1/MTU1500, Wireless Extensions17. Channel8 was observed.
- Native C inventory ran on the player:114 private-command records, hostcmd
  ioctl0x8be4, matching the offline driver table. No monitor/raw Action API
  is named. An Ethernet AF_PACKET socket alone is insufficient.
- Fixed read-only firmware command0x86/action0 returned '$Id:' at c00065a0.
  Four64-byte code ranges (8078,88d4,a314,136b0) match the original image:
  64 words/256 bytes. This qualifies those loaded ranges, not arbitrary writes.
- Cardputer0.1.3 was installed with write verification after an8MiB ROM-loader
  backup (first64KiB equals an independent read). The peer firmware has serial
  controls, not an LCD UI. Three manual32-byte ESP-NOW probes each produced a
  Sony-source Action response, category255, preserving the request sequence
  and random token. ESP32 management-only observation captured those replies.
  This is over-air Sony reception/automatic response, NOT custom app delivery.
- Player helpers live under verified /contents/HOMEBREW/data/espnow. Outputs
  are saved on the PC. Subsequent explicit tests loaded the candidate into radio
  RAM and used its restricted TX mailbox. Original root radio files, Linux
  module, kernel and initrd were not edited. The bidirectional worker exited
  with done0, normal Wi-Fi returned and original code/pool checks passed.

### Original command and frame paths

All addresses below are radio CPU addresses except explicitly named Linux
module section offsets. The two CPUs and their ABIs must not be confused.

Linux sd8686.ko SHA256:
2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69.
The mode handler (section offseta8f4) accepts AUTO/ADHOC/INFRA only, rejecting
monitor6. hostcmd handler3ce8 forwards an8-byte-header command buffer through
QueueCmd; its matching response-copy path exists. No command-ID whitelist was
seen in that wrapper. This does not establish every radio command or safe size.
RX ProcessRxedPacket uses eth_type_trans/netif_rx. sbi_card_to_host is a stub;
real SDIO read/demultiplex is sbi_get_int_status (section19710), with data0,
command1 and event3 types. Textual wireless events are not full Action frames.

Radio command routine8078 reads command&0x7fff and subtracts8-byte header.
Original Thumb dispatch replay shows0098 -> default9b24 -> result2 and response
8098. Neighbor0096/0097 enter real handlers. Upstream libertas command0098
therefore cannot simply be assumed supported here. Command0086 at88d6 writes
an addressed word only for action1; action0 follows88ea-88ee and returns a read.
The installed identity helper has fixed read whitelists, not a SET interface.
CMD_MAC_CONTROL0028 changes flags/registers, but does not prove raw host export.

The later original-instruction replay (tools/test_radio_mac_control.py) covers117
flag/context combinations and two repeated-command sequences. It starts at the
switch after admission, executes54c0/6b6c and their register helpers, and models
MMIO plus a fixed return from hardware-status helper11c4. The12-byte fixture has
flags at body offset0 and a reserved halfword, matching the upstream
[libertas command structure](https://github.com/torvalds/linux/blob/v2.6.32/drivers/net/wireless/libertas/hostcmd.h#L219).
Sony's builder basic block is now checked separately below; command admission,
full kernel startup and physical effects remain unqualified by these tests.

Observed command effects: old flag0x8000 is preserved in c0014528; flag0x80 saves
8000a300 into c000ee00 and ORs0x0b; clearing it restores that backup only if nonzero.
Flag0x100 sets/clears register mask0x40. Upstream calls these flags promiscuous
and all-multicast respectively, but those names do not establish unknown-key
Protected admission on this exact chip/firmware. Upstream flag0x08 is named WEP
enable; its observed Sony path also depends on other context bytes.
See the [upstream flag definitions](https://github.com/torvalds/linux/blob/v2.6.32/drivers/net/wireless/libertas/host.h#L129).

Let F be c0014528, P the byte at the verified context-pointer chain
*(c000ee48)->+8->+c0, Q=c00146e0, A=c0014684, K=c0014686 and R=c0007883.
Original54c0 selects a698 when (F&8) or P or (A!=0 and K==2); a698 ORs mask0x4300
into8000200c, while a674 clears it. Separately,6b6c selects dc94 when (F&8) or
(P!=0 and Q!=0) or (R==2 and A!=0 and K==2); dc94 sets8000a300 mask0x200 and
dd10 clears it. REA/Ghidra review confirms these branches. The different formulas
mean that clearing one MAC flag is insufficient to select both clear branches.
Register masks remain numeric observations, not a complete silicon crypto map.

Repeated enable is not an idempotent snapshot: sequence80,0 restores fixture
baseline10000000, but80,80,0 restores1000000b because the second enable overwrites
the backup. This supports retaining full original reload/restoration rather than
designing cleanup as only a flag clear. No mode change is added to the device
adapter based on these fixtures. Reports:work/espnow-mac-control/report.json and
work/espnow-mac-control-rea/inputs.json. Physical ciphertext preservation and
unknown-key admission remain unresolved.

### Original module startup filter defaults

The pinned Sony module initializes the16-bit adapter field at offset13c4 to0203,
not0003. tools/test_driver_station_init.py executes relocated original ARM
instructions at text+1ef4..1f04 with two old halfword patterns and observes the
same0203 store. It then executes the original post-download station-setup block
at text+1ae0, intercepting command transport with successful fixture responses.
The observed command prefix is0003,0028,0074,0076,001e;0028 receives a pointer
to that0203 field. Replay stops at the power command before its response, so this
is not a complete driver boot/download or an exhaustive search for key resets.

The actual MAC_CONTROL builder at text+c388..c3b8 writes command0028, total size12
and the supplied16-bit flags at offset8. Tests with0203/0283/0003/ffff preserve
sequence/result and reserved bytes. They do not establish how the rest of command
allocation initializes those fields. This agrees with, but is stronger target
evidence than, the upstream12-byte reference structure. Neither block contacts
real SDIO, runs the actual command queue nor produces physical RF effects.

Default0203 and combinations0283/0303/038b are included in the117 radio-side
context/flag cases. The0200 command bit remains present; it is not assigned a
silicon/security meaning based on the unrelated numeric register mask0200.
Do not replace the stock flag word with0003 merely because generic upstream names
identify RX/TX bits. The current native RF initialization performs original
region/TPC/PA/power operations; it is not proof that hardware key slots were reset.
The observed station-setup prefix contains no explicit key-delete command, while
download/startup outside the fixture may still reset keys or other crypto state.
Reports:work/espnow-driver-station-init/report.json and
work/espnow-driver-init/report.json. Hardware key clearing remains unverified.

### Software activation reset is not complete key erasure

The original helperc5e4 takes two reset selectors. First selector clears bytes
c0014684,c0014686 andc00146e0; second clearsc0014685 andc0014687. Either selector
clears command-flag0400 while preserving0008 and other observed flag bytes.
tools/test_radio_security_reset.py executes all four selector combinations on
the pinned radio instructions, checks sampled other context bytes unchanged,
and observes no MMIO writes by this helper. This is activation-state reset,
not evidence that all key buffers or hardware key slots have been erased.

The actual wrapperc0006144 callsc5e4(1,1), then54c0 and6b6c. With stock command
flags8203, the tested wrapper clears the activation bytes in both context cases.
If the separate context byteP is0,8000200c mask4300 clears. If P is1, that mask
remains set, and the wrapper also writes8000a320=7 and8000a350/354=ffffffff.
In both fixture cases8000a300 mask0200 clears after Q is reset. P itself is
preserved. These are instruction/MMIO-model observations; register meanings and
actual key erasure remain unproven. A hardware-status read is substituted.

REA identifies connection-result code atc0004cd8 that copies bytec00078c8 into
P at the root-context pointer chain, invokes this wrapper on selected branches,
then marksc00146e0/e1 according to another context property. Thus wrapper-cleared
activation and later connection state must not be conflated. The CMD005e parser
atc00048c8 passes type0100 TLVs through its veneer to key handlerc720; it is
distinct from c5e4. We do not send those key commands or write any reset fields.

Read-only diagnostic comparisons should record command flagsc0014528, activation
bytesc0014684..4687, Q atc00146e0, the bounded root-context byteP, and numeric
registers8000200c/8000a300 together. No single field is a hardware-safety or
ciphertext-preservation test. Any device reader still requires exact-image and
ownership checks; no new public arbitrary-memory API is introduced here.
Evidence:work/espnow-security-reset/report.json and
work/espnow-security-state-rea/inputs.json. The original boot path and physical
key table were not executed or observed by these fixtures.

Private Radio Inspect0.1.0-alpha.1 now implements this fixed read-only field set
with driver identity, partial stock/full code-profile matching, bounded BSS
pointers, two-sample comparison and no configuration command. Its native CLI
passes original-libc ARM tests with a GET-only ioctl fixture; the observer passes
fourteen actual-code/mocked-state cases. No physical reads or installation have
occurred. Equal samples and a partial fingerprint are observations, not proof of
exclusive access or hardware admission. See
[tool scope](../runtime/platform/espnow/inspect/README.md).

### Espressif software CCMP profile discrepancy

Pinned local ESP-IDF5.5.1 ccmp.c SHA256 is
01296aa4c5b571fb003949b6da84d233b4c88b1b0c7beb2a896e860a6a680222.
The official [v5.5.1 source](https://github.com/espressif/esp-idf/blob/v5.5.1/components/wpa_supplicant/src/crypto/ccmp.c)
derives nonce prefix10 for management frames, but its ESPRESSIF_USE espnow_pkt
decrypt branch overrides that prefix to00 and sets software tag_len=0. The
crypto_ops table binds that source function to the registered CCMP callback.

tools/test_espressif_ccmp_boundary.py compiles the unmodified upstream translation
unit with minimal OS/header shims and AES callbacks that record inputs only.
Host GCC12/ASan/UBSan and ARM926/original libc report identical nonce/AAD values:
ordinary management uses prefix10/tag8; espnow_pkt=true uses prefix00/tag0. The
AAD remains the same22 bytes in this Action fixture. PyCryptodome separately
authenticates current native ciphertext under prefix10 and rejects it under00.
This confirms parameter disagreement, not a working Espressif decrypt result:
the upstream AES stub does not decrypt or authenticate. No MIC check is disabled
in the native implementation.

ESP32-S3 libespnow.a/libnet80211.a objects were extracted with the matching
Xtensa binutils and inspected with symbol/relocation-aware disassembly. They are
ELF32 Xtensa, not ARM; no claim of executing them under ARM/Unicorn is made.
The ordinary software encrypt wrapper references wpa_crypto_funcs; the observed
espnow receive wrapper itself only adjusts buffers after finding an IAV key.
Those facts do not prove which hardware path/nonce/AAD/MIC operations are used
for actual S3 encrypted ESP-NOW transmission/reception. Follow those call-sites
or obtain controlled known-LMK RF frames before changing the native profile.
In particular, software tag0 must not be copied as permission to accept unauthenticated
data; hardware MIC handling before that fallback is unresolved.

Reports:work/espressif-ccmp-boundary/report.json and
work/espnow-espressif-ccmp/inputs.json. Native/Sony radio code, SDKalpha.6 artifacts
and installed apps are unchanged by this analysis. The separate upstream software
test used GCC12 after an intermittent GCC13 ICE; its compiler identity is recorded.

### Pinned ESP32-S3 transmit preparation and queue path

tools/analyze_espressif_tx_path.py pins libespnow/libnet80211/libpp hashes,
extracts fixed object members and reviews their actual Xtensa symbols, section
bytes, relocations and matching-toolchain disassembly. mt_send references the
vendor send wrapper, which calls its constructor then ieee80211_post_hmac_tx.
The constructor gets the IAV peer key and calls the vendor allocator. In the
key-present allocator path, a64-bit software counter increments by1; six PN bytes
are packed into an8-byte ExtIV at MAC-header offset24. The body starts after
that header. Constructor offset1d6 stores Protected40; its key path sets metadata
bit0 and stores the cipher selector into descriptor bits8..11.

The actual ccmp descriptor begins with words3/8/8; relocations at16/20 bind
ccmp_encap/ccmp_decap. Their header/trailer adjustments agree with the two8-byte
values. The vendor preparation path does not directly call the ordinary software
ieee80211_ccmp_encrypt wrapper. This is static instruction/call-site evidence,
not target CPU or hardware execution.

post_hmac_tx queues event5 through pp_post. ppTask's jump table selects section
offset130 for event5 and calls g_net80211_tx_func indirectly. That callback's
registration is now traced: ieee80211_output_init loads ieee80211_output_process
as the argument to ic_register_net80211_tx_cb, which forwards the non-null pointer
to pp_register_net80211_tx_cb. The latter stores it into g_net80211_tx_func.
Pinned literal relocations and reviewed Xtensa load/argument/store instructions
are asserted by the analysis script. This is static registration evidence, not
an executed queue event. ieee80211_output_process has a conditional call to
output_pending_eb; the channel/queue predicates still apply. output_pending_eb
references ppTxPkt, whose security stage references ppProcTxSecFrame. That stage
indexes a length table by cipher-1: selector3 gives12 additional bytes, consistent
with the8-byte trailer and4-byte FCS. This consistency is not a MIC validation
or proof of the actual bytes transmitted. ppProcessTxQ references lmacTxFrame;
the lower path references lmacSetTxFrame and hal_mac_tx_set_ppdu. The latter
configures PLCP/duration/HTSIG/TXOP fields rather than constructing software CCM.
Function-reference extraction is bounded by each symbol's start and size;
references elsewhere in a shared section are excluded.

The pinned hal_crypto_init writes0x30000 to60033800/60033804, clears60033808,
6003380c and60033810, then ORs0x19 into60033840. hal_crypto_mgmt_rx_enabled
selects60033804 for selector1, otherwise60033800, and reads bit17. These are
static numeric observations, not identified nonce/AAD controls or instructions
to access those registers on the Sony device. Remaining hardware descriptor
consumption and the actual authenticated RF profile are unresolved.

An official [2020 coexistence commit](https://github.com/espressif/esp-idf/commit/d17e6a75e06bc7d16ae0575df759f408a0305a3a)
explains why ESP-NOW differs: PMF moved management decryption into software while
ESP-NOW needed backward-compatible hardware behavior; ESP-NOW TX could stay in
hardware. This gives a design reason for the special software branch, not a
complete S3 nonce/AAD/MIC specification. It supports tracing offload instead of
treating the generic management software encrypt wrapper as an ESP-NOW oracle.

Evidence:work/espressif-tx-path/report.json and
sources/espressif-espnow-crypto-sources.json. No native nonce profile, MIC policy,
SDK package, Sony driver or radio image is changed by this static review. Physical
known-LMK frame authentication and full encrypted interoperability remain pending.

### Authenticated known-key capture analysis

Restoration diagnosis must separate manager state from actual reachability.
Current xnow_manager_execute(RECONNECT) returns success immediately for public
state4. For state3 it requires saved configuration, prepare_connect success,
connect success and a final public state4. It is therefore incorrect to describe
the implementation as merely submitting an asynchronous connect request. It is
also incorrect to infer current AP association or a reachable Terminal solely
from the state4 shortcut or a displayed IPv4 address. Whether that shortcut can
observe stale state after a radio-image cycle requires physical evidence; no
such cause is established by source inspection. Before another RF experiment,
collect stock association, manager state, original image identity, residual owner
processes and authenticated host reachability. Preserve original manager behavior
until evidence supports a change; do not insert blind disconnect/reconnect loops.

With only one Cardputer available, the proposed two-device experiment uses it
as the standard encrypted sender and X1060 as the observer. This does not require
assuming local ESP TX promiscuous capture. It does require qualifying X1060's
upstream admission before relying on the new full RX hook. The legacy fixed32
chat acceptance does not qualify this path; no image load or deployment is
authorized merely by the offline tests.

tools/test_radio_full_rx.py now sends12 independent AES-CCM synthetic cases
through the actual compiled radio hook and original4b9c ring-copy instructions:
three candidate profiles, v1/250 and v2/1470, Key ID0/3. It checks ciphertext
and retained source bytes, reconstructs the canonical header from slot metadata
and the verified fixture local MAC, then authenticates with the PC classifier.
All pass, including pool release. These records have no FCS and must not be
passed with --fcs. Duration/sequence normalization does not replace the earlier
A3/fragment validation. This proves only the post-admission capture boundary;
DMA/IRQ input and unknown-key hardware admission remain modeled. A failed real
capture would require tracing that upstream path, not guessing a crypto profile.

Another static compatibility difference is now explicit: initial mt_set_lmk writes
0x0310 at context184, leaving byte185=3. The vendor allocator loads byte185 at
section9f, shifts it by6, ORs ExtIV0x20 and stores frame byte27. Thus this initial
path prepares Key ID3 (ExtIV bytee0), independently of hardware slot byte186.
The native endpoint currently initializes security with Key ID0 and its codec
requires an exact match before MIC processing. The analysis script asserts the
allocator instruction bytes and records the difference. A synthetic ID3 generic
CCMP frame is rejected by the ID0 native context without plaintext or replay-state
commit; subsequent valid ID0 traffic still passes. This is not an actual S3 RF
capture or proof of all warm-context paths. Do not silently accept arbitrary Key
IDs or change the frozen SDK package based only on this static initial path.

RX-side static review adds an important boundary: the S3 function named
ieee80211_decrypt_espnow_pkt does not execute AES in its reviewed body. It looks
up the source peer key, advances the data pointer by24 plus the descriptor header
size and subtracts descriptor header/trailer lengths. sta_recv_mgmt calls it at
sectiona0a after Protected, DS-bit, peer and Key-ID checks. This is consistent
with earlier processing but does not prove where hardware MIC checking happened.
The script records this wrapper's section hash and function-bounded references.
Do not treat its name as a software CCMP oracle. For ciphertext observation,
use a separate observer without the test peer LMK installed; still require actual
MIC authentication to establish that a capture is usable ciphertext. Capture of
the observer's own transmission is not guaranteed by the RX callback.

The pinned LMK installation path is also traced. The local function name is
stripped in manatick.o, so the evidence uses section .text.mt_set_lmk rather than
pretending an exported mt_set_lmk symbol exists. At section137 it sets a11=3;
the call expansion at13a references ic_set_key. That wrapper calls
wDev_Insert_KeyEntry, which builds the key metadata, calls hal_crypto_set_key_entry,
then hal_crypto_enable. The analysis script verifies the literal binding,
instruction bytes and downstream function-bounded references. No actual LMK was
extracted. This establishes hardware key-install call sites but does not assign
undocumented nonce/AAD semantics to their parameters or prove RF encryption.

The HAL slot layout is now reviewed: base60034400 plus40*index holds two
metadata words at offsets0/4; key data is copied at offset8, with copy length
rounded as(length+3)&~3. The first word packs metadata bytes3..6 (the supplied
address prefix); the second combines bytes7/8 with control bits derived from
metadata bytes0..2. Validity uses a separate bit in60033814. The MT initializer
writes halfword0x0310 at context184, and its later call passes byte184 as key
length, confirming16 on that path. The script asserts the pinned literal bases,
slot-stride instructions and initialization bytes. No hardware register was read
or written for this review. Numeric layout does not identify nonce/AAD controls;
the packed control-bit semantics remain only partially understood.

tools/espnow_known_key_frame.py is a PC-only classifier for an owned raw802.11
protected Action frame and an explicitly supplied16-byte LMK. It compares three
labelled hypotheses: generic management nonce10/AAD, nonce00 with the same AAD,
and nonce00 with legacy subtype masking. None is selected as a new native default.
Every candidate must pass an8-byte AES-CCM MIC and complete ESP-NOW body parsing.
Software tag0 from the upstream fallback is deliberately not used.

```sh
.venv/bin/python tools/espnow_known_key_frame.py \
  --frame work/private-capture/action.bin --lmk-file work/private-capture/lmk.bin
```

Input starts with the24-byte MAC header, not radiotap or a pcap container.
Use --hex for hex text and --fcs only when a captured trailing4-byte FCS is
present; this option strips it and does not validate its CRC. Keys can be16 raw
bytes or32 hex digits in a private file, never a command-line key value. Default
output contains authentication/structure results and hashes, not plaintext.
Optional --output-payload accepts only a new file under work/ after exactly one
profile authenticates and decodes. Keep captures, keys and payloads untracked.

tools/test_espnow_known_key_frame.py covers all three synthetic profiles, v1
empty/250-byte and v2 empty/251/1470-byte payloads, binary data, wrong keys,
bad MIC, authenticated invalid bodies and explicit hex/FCS input. The report is
work/espnow-known-key-frame-tests/report.json. Passing these generated cases
qualifies the analysis tool only; it does not establish a physical wire profile.

The separate standard-peer bench0.1.2 now provides explicit capture <source-mac>
and capture off commands. Its S3 promiscuous callback copies only selected-source
protected Action frames into a bounded queue; it checks successful RX state,
unfragmented header, broadcast address3 and59..1564-byte length including FCS.
Capture defaults off and does not transmit. The pinned IDF native RX header
documents sig_len as including FCS. The callback does not decrypt/authenticate;
hardware ciphertext preservation and observer reception remain unqualified.
Host ASan/UBSan boundary tests and an actual IDF5.5.1 S3 build pass. No flashing
occurred, and the working Cardputer chat image was not replaced. See the bench
README for private capture handling and explicit classifier input options.

The 'MAC Mgmt' task entryc0003188 is registered with task4. It consumes internal
RX work (helpere164 and ring markersbeef/befx), obtains a frame wrapper and
calls subtype dispatcha314. Action subtype13 maps to internal event2 for
SyncSrvSta objectc000752c. This is a real subtype path, not an unrelated event13.
Sync constructor5648 configures Sync_Idle/Listen/Roaming, Bss_Active,
IBss_Active and power-transition states. Bss_Active callback1f00 and
IBss_Active callback3404 both pass event2 to136b0.

The full-stack task replay now executes original c000323a..c0003288 with actual
e164 ring polling and4b9c copying, then traverses the ARM veneer c00026a8 and its
target wordc00026b0 into the compiled full RX hook. Plain maximum payload and
Protected maximum body survive unchanged; management-type selection and disabled
fallback are checked. REA confirms this task clause has no existing-peer/key or
Protected-bit rejection. Initial work-node acquisition, DMA producer/MMIO and IRQ
remain modeled. Unknown-key hardware admission and ciphertext preservation before
the DMA ring remain unverified. See [full-stack evidence](ESPNOW_FULL_STACK.md).

Action handler136b0 checks subtype/address. Category0 is consumed; category17
has a specialized path. Other categories below128 are copied into a management
packet and ORed with80 before submission. Category127 therefore becomes255;
this was observed over the air and separately replayed with substituted helpers.
Vendor IE parserc0003004/c00030b0 matches WMM signatures00:50:f2, not ESP-NOW.

Radio TX: allocator d458 -> header builder da00 -> submit d800 -> queue helper
1571c -> queue3 / notify task5,event2. Queue success is not RF completion.
Host reply helperc00062f0 enqueues on the ID in c00078b4 and notifies task0,
event20. Its failure release uses poolc000d604, which has ONE342-byte block;
it is not general heap and must not be permanently borrowed. RX work metadata
has a separate ownership/release path. Do not retain borrowed RX pointers.

### Container and original loading mechanism

sd8686.bin:123980 bytes, SHA256
08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a.
Embedded ID: sd8686-B0,RF868X,FP4,9.70.3.p32; build2008/07/08. This does not
independently identify physical silicon stepping.

Each record has LE32 command/address/length, then a BIG-ENDIAN header CRC.
Command1 length includes a BIG-ENDIAN payload CRC trailer. Both CRCs are
MSB-first polynomial04c11db7, init0, no final xor. All238 header/237 payload
checks pass; parse/serialize is byte-identical. tools/marvell_firmware.py is
the strict PC parser; tests reject damage, truncation, wrap and trailing bytes.

Stock wlan_load_driver.sh supports fw_dir and passes helper_name/fw_name to
the unchanged driver; fw_read uses filp_open. A candidate could therefore live
on visible storage and use original radio loading, without editing root files.
This path passed bounded alternate-image tests and original restoration. Driver reload drops the
Terminal connection; local ownership, reconnect and stock restoration must be
qualified before an unattended test. Do not use Sony's system updater for the
radio-only files.

### Explicit memory reservation candidate

The old c0000e00..c0001000 gap is NOT approved scratch space: a physical GET
survey read128 nonzero words and established no owner. Its contents could be
uninitialized or reserved. Appending after low image17340 is also unqualified:
startup uses stack/RTOS literals near17340 and17d14..17d3c. CP15 cache control
is configured at boot; live instruction patching is not qualified.

A concrete alternative is the original large-packet pool:

| Property | Original | Candidate |
| --- | --- | --- |
| Manager | c000d5a4 | unchanged |
| Block base | c0008b4c | unchanged |
| Stride | 76c (1900 bytes) | unchanged |
| Blocks |4|3|
| Reserved block | none | c000a190..c000a8fc |

Original initializer163ec calls10294 with those values. Replay executes the
original initializer, allocator102dc and release1031c:12 cycles for each4/3-block
configuration. With3 blocks, the fourth is never returned or touched. IRQ helpers
are substituted. A direct pointer scan found no literal into that block; this
is not complete alias/ROM/hardware-use proof. Reducing capacity may affect load.

The candidate performs four coordinated edits: count4->3 at163ee, receive
veneer targetc00026b0 froma315 to the bridge, and two scatter-zero table edits.
Original BSS c0006e70..c0017da4 is split around the reservation; the previously
zero-length final entry supplies the second range. All other zeroing is
preserved. New download records contain the reserved block. No new SRAM address
beyond original pool capacity is introduced. The bridge must NEVER be loaded
into a stock four-block image at runtime.

### Implemented prototype and tests

runtime/platform/espnow contains:

- Cardputer serial peer, shared xnow_frame.h payload codec.
- Native inventory/fixed-GET probes, with PC-only builders.
- radio_bridge.c:420-byte Thumb prototype plus92-byte state. It accepts exact
  fixed32-byte unencrypted XNOW envelopes, publishes an RX snapshot, and services
  a pending TX request when a matching peer frame arrives. Other traffic falls
  back toa314. Version/kind/reserved header fields are validated. Exact PING0,
  token0, zero-body heartbeats clock pending TX without replacing unread RX.
  It is poll-driven, not an independent TX scheduler.
- xnow_mailbox.h/.c: portable native C publication, radio queue status and
  latest RX snapshot APIs over a qualified word-I/O adapter. No filesystem,
  allocator or raw address access. One writer; callers serialize operations.
  Request publication, radio queue acceptance and peer ACK are separate results.
  Uncertain publication must not be blindly retransmitted. Overwrites and torn
  snapshots are handled explicitly. The exact native adapter passed the bounded
  physical test documented in runtime/platform/espnow/VALIDATION.md.

Offline tests execute compiled radio Thumb with substituted RTOS helpers;
check RX/TX, allocation/queue failure and18 fallback cases. Candidate integration
executes actual scatter zeroing, pool init/alloc/free and modified ARM-to-Thumb
veneer, confirming payload survival and RX snapshot update. Native mailbox tests
pass under host sanitizers and ARM926 QEMU with pinned Sony libc. These do not
establish concurrency, capacity under load, driver restoration or physical custom
app RX/TX by themselves. Separate physical results now establish the identified
worker's bidirectional exchange and original restoration; long-duration and
high-load behavior remain unqualified.

Current candidate:work/espnow-radio-candidate-poll-filter,125960 bytes (radio input only),
SHA2565bcd7fc8b935612e6e90826826235766130c8226245a385535c8cc2059b39e70.
Mailbox address:c000a334. Candidate integration also executes100 heartbeats
after a DATA snapshot and checks that it survives. Native builds were refreshed
against the new generated bridge header. The earlier344-byte prototype candidate
remains under work/espnow-radio-candidate with its original reports; it is not
the image expected by current native builds. The current candidate was loaded
into radio RAM for explicit physical tests, not installed into rootfs.
Its review.json enumerates every edit; that offline construction report is not
the later physical acceptance report.
The original fallback and helper are alongside it. Nothing is published.

The candidate integration test requires an explicit matching folder:
tools/test_espnow_radio_candidate.py --candidate work/espnow-radio-candidate-poll-filter.
It checks the image against its report hash before instruction replay.

### RF channel command

The original driver's PrepareAndSendCommand block c838..c87c constructs
command001d with size48, LE16 action at8 and LE16 channel at10. Executing that
ARM basic block produces the same layout as xnow_channel.h. Do not shorten the
request to12 bytes merely because the handler reads only its first fields.

The actual radio command switch reaches8c9a. GET0 executes original de3c and
returns current channel at10. SET1 invokes d8ac, d87c and cb88; its input channel
is truncated to8 bits. Replay substitutes those RF helpers and exercises channels
1/8/13 and0108->8. Action2 makes no helper calls; it is not a supported setter.
The native codec rejects invalid actions/channels before IO and uses1..13 only.

xnow_sd8686 now has GET and a session-gated experimental SET with GET readback.
SET requires the verified candidate plus an acquired session's CONFIGURE action.
The native lab exposes GET only as --channel. No application invokes SET yet.
Host adapter tests substitute socket/ioctl and validate the wire shape, guard
refusals and uncertain readback. The original switch replay begins after the
pre-dispatch gates, so it does NOT qualify unassociated/asleep admission, actual
RF tuning, channel persistence or old-kernel ioctl operation on hardware.
Reports remain under work/espnow-channel-handler.

### Command admission and power-state boundaries

A separate replay now starts at original radio entry8078, rather than inside
the command switch. With synthetic state bytes it executes the original command
prologue, whitelist3668 and feature check4b80. Across12 combinations, command001d
reaches8c9a when c0007859 is0/1 and c000edf4 initially0. State2 rejects it with
status2 before the switch; an initially busy command preserves status4 through
the default branch. Only response memcpy is substituted. Command0021 actions
0030/0031 write7859 between1/2 in the original code, but real transition timing
and RF wakeup are not qualified by seeded bytes.

The prologue sets c000edf4 itself before processing a command. A word GET of
that byte would therefore observe the diagnostic request's own busy state; it
is not a usable external idle preflight. Do not add a busy-GET polling loop or
modify this byte to make a command pass.

Linux-side replay relocates the exact sd8686.ko and executes wlan_do_ioctl up
to wlan_hostcmd_ioctl or refusal. In16 synthetic combinations, private ioctl
8be4 reaches its handler when adapter byte1404 is0 and either byte13fc is0 or
byte13fd is1. Refused cases return-16. An additional field36f4 was varied0/1;
it did not alter this bounded entry result. SetDeepSleep explicitly uses13fc,
calls sbi_exit_deep_sleep and waits for completion; its actual hardware wakeup
and the complete meaning of the other fields remain unqualified. No raw field
write is an implementation strategy. The replay substitutes the netdev/adapter
and thread metadata; it does not run a kernel, queue a command or contact RF.

Reports:work/espnow-radio-admission/report.json and
work/espnow-driver-admission/report.json. These strengthen the static admission
evidence; they do not establish that an unassociated candidate radio will remain
awake. A session runner still needs an original-API wake/restore path and real
readback before its CONFIGURE step can be accepted.

The experimental native WAKE adapter now uses original ioctl8bfb, ASCII0, with
a128-byte in/out buffer, followed by ASCII2 query. Original rodata strings are
setting-to-off, on-space and off-space; the query returns3/4 bytes without NUL.
The handler does not propagate every SetDeepSleep failure, so WAKE requires an
explicit off-space query and then candidate verification. The session orders
LOAD_CANDIDATE->WAKE->VERIFY_CANDIDATE->INITIALIZE->CONFIGURE. Its process adapter performs
WAKE in a child and drains it before continuing or cancelling. Four additional
relocated driver-entry cases reach the deepsleep handler even where hostcmd is
blocked. Adapter tests also pass with ARM926/Sony libc and substituted ioctls.
These do not qualify sbi_exit_deep_sleep, real wake completion or the separate
radio state7859 transition. No production app or live test invokes WAKE yet.

### Original unload process adapter

The native job adapter now invokes /bin/sh /usr/local/bin/wlanapi.sh unload for
UNLOAD/RESTORE_UNLOAD, preserving original ordering and using a fixed clean
environment. The hash-bound original rootfs has no wlanapi.inc. Seven host-shell
replays cover interface UP/DOWN, failure of each of four module removals, and
all modules already missing. No stop/killall, NVP or pipe lifecycle command was
called in these bounded branches. Original iwconfig is in /usr/local/bin; that
directory is included in the adapter's fixed PATH alongside original system
tools. Rootfs script hash:b1d7b114157a4a807ebfd8021fbc2aa413569905225aab75568773af852f26fb.

The script can return0 after a later module removal fails. The parent therefore
drains its child and independently checks /proc/modules for absence of sd8xxx,
mp200_sdio, wlan_pm_register and wlan_pwr_ctrl. Tests cover misleading zero and
nonzero exits; ARM926/Sony-libc fixtures test exact module-name matching. This
is not a lock against concurrent daemon reload and not hardware unload proof.
The control path remains unconnected to the production app.

### Original RF initialization

The original w8_proc_init performs more than module loading: deepsleep0,
read-only nvp zr11/1, region mapping, setregioncode, tpccfg0, hostcmd PA adaptation
configuration and txpower15. The root config's pa_cfg_ext_set selects007e,
action1, EnablePA0, TLV0114 with empty payload. High radio validator c000156c
accepts GET/SET and enable0/1; setter c000141c writes the radio-global adaptation
byte and processes optional TLVs. Further RF/helper effects are not qualified
by this observation. Do not confuse EnablePA with a physical-amplifier switch.

xnow_rf_init.c follows the stock command arguments through fixed execve calls,
with a bounded128-byte NVP capture, strict original region mapping and explicit
wait/reap at every step. It provides no NVP-write command. Every failure stops
later initialization. Both candidate and original-image restoration now include
wake, code verification and RF initialization before channel setup/reconnection.
Fourteen original-script replay cases verify order and mapping; native host and
ARM926/Sony-libc fixtures verify argv, failure and output bounds with executable
effects substituted. Actual NVP output and RF result are not hardware qualified.
The root tools/config must be hash-verified before use; the complete guard and
UI lifecycle are still absent. No such operation was run on the player.

### Native connection-manager ownership

xnow_manager.h/.c implement original C API calls for the session's manager
actions. A single controller process retains cnmgr_init(NULL,NULL) across the
radio phase and saved-network reconnection. Public state must be3 after
disconnect and4 after prepare_connect/connect(current_snapshot). Only then is fin allowed
by the session sequence. An uncertain init/fin prevents blind repetition; process
mismatch, reentry, missing IPC guard and unauthorized disconnect are refused.
Calls may block, so the owner must be separate from the UI. This is one stock
client, not an exclusive reservation against other Sony services.

Original-daemon replay follows connected internal state8 -> disconnect9 ->
IP-stopped10 -> WLAN-disconnected2. A public query then returns3. Preparation
moves to3; saved-network connect enters4, two modeled configuration completions
reach6, WLAN-connected reaches7 and IP-ready reaches8/public4. The client count
remains1 in this isolated fixture until fin. Actual ARM adapter + unchanged
Sony libcnmgr/libpthread + redirected local FIFOs reproduced that sequence with
delayed original-daemon responses. Radio actions are explicit placeholders;
driver/AP context and events remain modeled. No real driver reload or device
connection is part of this check, and the earlier lost Terminal connection is
not explained by it. Reports:work/espnow-manager-lifecycle and
work/espnow-manager-stock-transport. Full owner IPC/USB guarding and production
app wiring remain incomplete.

### USB preflight limitation

The USB connection ioctl does not independently prove MSC authority, as covered
by the original callback replay. The controller's sysfs function attribute only
reports its bound function name. Its /proc/driver/udc handler instead prints
state plus a broad MMIO register dump; original proc_udc_show contains direct
register reads. It is not being added as a harmless polling guard. The kernel
VBUS helper is not an audited user-space ownership query. No new automatic
ownership guarantee is inferred from any of these interfaces; the production
guard remains incomplete pending a verified stock ownership/lifecycle path.

### Evidence and remaining integration

The native code now builds as libxnow.a through
runtime/platform/espnow/build_library.py, with public C/C++ headers and explicit
library VERSION0.1.0-dev.8. Earlier development artifacts are preserved.
SDK0.2.0-alpha.2 also exposes its independent core/device/message modules;
the message helper is optional and does not restrict user applications to chat.
The chat app links that archive instead of compiling
a second protocol implementation. A versioned local SDK ZIP contains only the
archive, headers, guide, no-device example and fingerprints. Minimal and
whole-archive consumers run under ARM926/Sony libc; C++ header/link compatibility
is host-tested only. Candidate/payload/guard bytes and addresses must match at
build time. This is not RF qualification or a production session runner.

The native owner controller now dispatches manager actions, guarded worker
jobs, candidate verification/configuration and original-image restoration.
It exposes a mailbox only while READY, closes access on stop, and waits for a
pending child result before cleanup. Unknown process/client ownership is not
a clean finish. Unit tests cover failed jobs, guards, in-flight stop and restore
retry. The ARM/Sony-library FIFO fixture now runs this actual controller with
modeled platform jobs. The shared original-RAM-IPC guard and explicit tested file/mount guard profile
are available. USB hardware attestation is incomplete; the touchscreen owner
transport subsequently passed the native IPC/recovery test, and the user
reported Chat testing passed. Library linkage does not activate
radio replacement.

Stock verification is stronger than pool count alone: a four-block pool plus
SHA256 of276 stable code/layout bytes, covering the prior four code ranges,
pool initializer and original callback pointer. Expected hash
ea3548def031c67fede1ff197fd2def4f71b1b6b9932c3712c54b58ee1fa5580
comes from the pinned original container. It is not full RAM attestation. ARM
adapter tests use original words in a private PC fixture and reject a flipped
bit. The distributed archive stores the digest/ranges, not those Sony words.

The earlier292-byte verifier falsely rejected the live original radio: boot
scatter inputs17320..17340 had become zero. Original11e0/11f4 explicitly clears
831 words at17304..18000; instruction replay reproduces table reclamation.
Those consumed boot inputs are excluded from runtime identity, but remain
checked in offline candidate construction. Candidate integration now also runs
that original reclaim routine and checks reserved-payload survival. Full boot
ordering is not thereby qualified. The corrected native stock check passed
on the player, followed by channel GET8 and pool GET4/free4. No SET was issued.

After user-restored Terminal access, fresh read-only observations confirmed
matching original driver/radio/helper/script/config MD5 values, a1900-byte
four-block pool with four free blocks, and64 original code words across the
four established ranges. No device file was written or radio mode changed.
The old reconnect journal was recovered: init0, initial public state4,
disconnect0, prepare0, saved-network connect4, final public state3. That attempt
failed to reconnect before its own fin; do not label it a successful cycle or
attribute the initial failure to the later fin. Error-code cause is unresolved.
Private evidence stays under work/terminal-live; never publish pairing codes,
network identity or raw session files. Current connection is authenticated with
the known certificate pin. The later native worker ran this controller on the
device and passed the bounded exchange/recovery test.

Further original-code replay found result4/public3 after ERROR-set failures
before association as well as explicit cancellation. Do not assign a unique
cause to that code. Report:work/espnow-reconnect-result. The official target
connect-info getter uses request24 and copies1004 bytes; the ordinary
connect(non-NULL) path passes that value through request7. Provider-specific
branches remain vendor-managed and are not qualified by this fixture.
An ARM/original-library FIFO probe verifies exact
roundtrip without logging payload. A read-only native probe ran on X1060:
init0, public4, getter0, bounds intact, public4, fin0. Configuration was cleared
from RAM, never logged/saved. Library0.1.0-dev.4 now captures that opaque value
before disconnect and uses it for restoration instead of NULL/request12.
Capture failure refuses disconnect; later stock/candidate tests passed actual
current-config reconnect. Buffers
can contain credentials and must not be serialized with controller state.

The Cardputer public-header rebuild produced a new unflashed candidate; the
known installed and serial-tested0.1.0-dev.2 image remains separately preserved
at work/espnow-cardputer-known-running/chat-0.1.0-dev.2.bin. Do not apply the
installed image's smoke report to the new build solely because VERSION matches.

The current launcher source has a separate lifecycle constraint: after SIGTERM
it waits100 nominal20ms ticks before SIGKILL of the unreaped app process group.
tools/test_xnow_launcher_shutdown.py executes that actual process function with
the host POSIX backend. A250ms cooperative child completes; a5000ms cooperative
child is killed around2.1s before its completion marker. This is not an actual
radio-restore duration measurement. A synchronous restore on chat exit therefore
cannot yet be assumed safe. The global timeout remains unchanged. Accepted RF tests used an explicit
detached laboratory entry. An independent touchscreen owner with RAM IPC passed native exchange and EOF
restoration; the user subsequently reported Chat testing passed. Report:work/espnow-launcher-shutdown/report.json.

The full-link offline fixture executes actual shared C chat/mailbox code against
the compiled Thumb bridge and shared C peer protocol. Both directions deliver
one96-byte message and application ACK, including valid UTF-8 split across
fragments. Deterministic drops/duplicates and uint32 timer wrap also pass.
Missing peer times out once without reporting delivery; its mailbox request
remains pending. This explicitly preserves uncertain-send semantics, not a
cancellation guarantee. The fixture uses host-compiled native C, modeled RF and
word-IO timing, and substituted RTOS helpers. It is not the player executable or
physical wireless link. Report:work/espnow-full-link/report.json.

The original Cardputer on COM17 now runs chat0.1.0-dev.2, application SHA256
0c1299e0ee43768277e123568e8dc4bc13778ccb725913f74aa2518c161098a0.
ROM/no-stub application writing and verification succeeded; original full-flash
and raw-peer0.1.3 rollback files remain preserved. Live serial checks passed
96-byte submission, one-outstanding-message bounds, absent-peer timeout,
invalid-channel rejection, oversized-line rejection and continued discovery
responsiveness. RX drops remained0; a subsequent restart returned idle/unpaired
on channel8. ROM-tool serial residue required a newline before the first status
command after restart; both observations were preserved. The peer's MAC-success
counter is NOT an application ACK. Physical keyboard/LCD acceptance and native
X1060 touchscreen lifecycle remain unverified. A later native worker passed
bidirectional over-air exchange; that is separate from LCD/keyboard acceptance.
Earlier smoke logs and report:
work/espnow-cardputer-ui/live-chat-dev2-20261028-01/.

Raw private evidence remains ignored under work/espnow-audit,
work/espnow-radio-bridge,work/espnow-radio-candidate,
work/espnow-mailbox-arm and work/espnow-cardputer-build/backups. Prior longer
notes were preserved under .tmp/espnow-research before consolidation.

Key reports:live-code-comparison.json,container-verified.json,
observer-verified.json,pool-reservation-tests.json,offline-tests.json,
offline-integration.json and the ARM mailbox report. Match each to its source
and artifact hash; REA automatic boundaries/thunk aliases can be wrong. Use
explicit Thumb entries and original instructions, not failed/ambiguous queries.
The initial label 'pool_config' for15bdc was an analyst guess: its code handles
MAC interrupt/status, not pool construction. Actual packet pool setup isc0004b6c.

Remaining: physical pool/layout checks and broader alias/ownership review;
qualified native word-I/O adapter; local radio reload/reconnect/stock-restore
runner; controlled custom-app receive/send/peer-ACK tests; lifecycle/load tests.
Do not mark the library complete from stock automatic replies or offline tests.
All player persistence stays on verified /contents user storage; RAM queues are
bounded. No system partition, NVP or raw flash is an app-data destination.

Primary comparisons:
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html
- https://raw.githubusercontent.com/torvalds/linux/v2.6.32/drivers/net/wireless/libertas/host.h
- https://raw.githubusercontent.com/torvalds/linux/v2.6.32/drivers/net/wireless/libertas/cmd.c
- https://raw.githubusercontent.com/torvalds/linux/v2.6.32/drivers/net/wireless/libertas/rx.c
- https://raw.githubusercontent.com/torvalds/linux/v2.6.32/drivers/net/wireless/libertas/tx.c

### Physical encrypted endpoint follow-up (2026-10-30)

The alpha.2 autonomous endpoint sent eight byte-exact nonempty encrypted payloads
through1470 bytes to the standard S3 peer. A same-key process restart, without
recreating that peer, repeated the result with durable TX reservations starting
at10241 instead of one. This is process-restart evidence, not a power-loss test.
In the opposite direction, the native endpoint authenticated twelve1470-byte
packets; the first decoded SHA-256 matched the original test payload exactly.
Each run restored stock Wi-Fi and authenticated Terminal access.

Bench0.1.3 fixes its null-pointer/zero-length receive guard. The host regression
fails before the fix and passes afterward under ASan/UBSan. A fresh physical TX
run still yielded eight nonempty callbacks and no empty callbacks despite ten
successful native MAC completions. Calling the standard ESP-IDF5.5.1 send API
with a nonnull buffer and length zero returned12390 (ESP_ERR_ESPNOW_ARG), with
no TX callback. Empty-body wire encoding is therefore not evidence of a supported
standard application message. Do not count these missing callbacks as solved,
or keep repeating this same vector as though IDF accepted zero-length sends.
Local evidence:work/autonomous-espnow-test/live/{enc-tx01,enc-tx02-resume,
enc-rx01,empty-tx01}; all keys remain private and excluded from publication.

### Stale-PN and wrong-key follow-up

The alpha.3 receiver retained durable high-water38 across a sender restart.
Seven incoming datagrams produced REPLAY (-23); five subsequent1470-byte
messages authenticated and the validated durable record advanced to61. This is
stale-PN rejection over air, not exact recorded-ciphertext replay. Disposable
bench keys were intentionally reused for this negative test only.
A separate fresh-key run produced six AUTH (-22) failures with a wrong peer key,
then six authenticated1470-byte packets after selecting the matching sender key.
The accepted payload digest matched, and both workers finished with done0 and
restored authenticated Terminal access. Private reports are enc-rx04-stale-pn and
enc-rx05-wrong-key under work/autonomous-espnow-test/live. No firmware was flashed.
