# USB FM reference-design MCU image candidate

## Provenance and scope

A concrete MCU-image candidate was recovered from the third-party
[IanCass/silabsradiodll repository](https://github.com/IanCass/silabsradiodll/tree/1ab1a15112b625958c15a3962dc014f63b432cdd),
commit `1ab1a15112b625958c15a3962dc014f63b432cdd`.
The repository describes support for the Silicon Labs reference USB radio and
ADS Tech Instant FM. `radiodll/FMRadioMCUImage.h` contains a retained binary
array; it is not merely a named but missing download. This provides new input
beyond the ordinary host drivers compared in
[FM_EXTERNAL_IMPLEMENTATIONS.md](FM_EXTERNAL_IMPLEMENTATIONS.md).

This is a USB bridge MCU candidate, not the internal firmware of Si4702/03.
Its origin as an unmodified vendor release is not authenticated. Exact tuner
subtype/stepping and relationship to the Japanese Sony board remain unknown.
No hardware was accessed, application executed, firmware loaded or published.
Keep acquired headers, decoded bytes and listings in ignored work directories.

## Container reconstruction

The header specifies fifteen records of 515 bytes. Each contains a page index,
512 payload bytes and two stored checksum bytes. The observed page order is:

```text
13, 14, 12, 0, 1, 4, 5, 6, 7, 8, 9, 10, 11, 3, 2
```

Every page from 0 through 14 occurs once. Place a page at `page * 512` and
XOR its payload bytes with `0x55`, retaining the index and checksum separately.
The resulting candidate covers `0x0000–0x1dff` (7680 bytes).

Input header SHA-256:
`b3b833cfcdb2e2f16e497784e6bcac58281717aebcc2889252ab4009f7485f89`

Decoded candidate SHA-256:
`858660efc61badf83544b4c00a4f393d813d3e7abbb31d1228430a828fe3f0a5`

Evidence supporting the decoding:

- Reset bytes `02 15 63` are an MCS-51 LJMP to `0x1563`.
- At `0x1563`, recognizable compiler startup clears internal RAM, establishes
  the stack and enters initialization at `0x1ac9`.
- Vector `0x002b` jumps to `0x1a5f`, which begins with interrupt register saves.
- UTF-16LE data at `0x0d55` and `0x0d89` spells the manufacturer name and
  `FM Radio`, respectively.

The stored page CRC algorithm and coverage remain unresolved. Common CRC16
variants did not authenticate the records. Recognizable code and strings do
not replace that check. This image must remain labeled a decoded candidate.
Do not infer the contents of uncovered flash or bootloader space.

## Reproducible PC extraction

```text
python tools/extract_fm_mcu_candidate.py
dis51 -l 0 0x2b < work/fm-mcu-candidate/candidate.hex > work/fm-mcu-candidate/disassembly.txt
python tools/replay_fm_mcu_init.py
python tools/inspect_fm_mcu_usb.py
python tools/replay_fm_mcu_stream.py
```

The extractor checks the exact source hash, unique/complete page indices,
decoded hash and startup bytes. It independently reconstructs all Intel HEX
records and validates their checksums. This checks extraction and file format,
not device behavior or the unresolved original page CRC. `dis51` is a PC-side
MCS-51 disassembler. Its recursive listing is incomplete around indirect
dispatch and must not be interpreted as proving the absence of commands.

## First recovered control path

Startup at `0x1ac9` invokes the routine at `0x0046`. That routine manipulates
P1.2/P1.3 and exchanges bytes through SFR `0xa3`, polling bit `0xff`.
The C8051F320/1 register definitions identify the SPI peripheral; see the
[manufacturer MCU datasheet](https://www.silabs.com/documents/public/data-sheets/C8051F32x.pdf).

At `0x0074` the code writes SPI byte `0x71`, followed at `0x007c` by `0x7f`
and dummy bytes. The response is reassembled with one-bit alignment. At
`0x00b9` it clears bit `0x40` in the low returned byte and sets bit `0x01`.
At `0x00c6` it sends `0x61` and the repacked value. This matches a POWERCFG
read/modify/write that clears DISABLE and sets ENABLE.

The 3-wire protocol has a nine-bit control word. With byte-packed SPI:

```text
control9 = (first_byte << 1) | (second_byte >> 7)
register = control9 & 0x0f
read_bit = (control9 >> 5) & 1
data16   = ((second_byte & 0x7f) << 9) | (third_byte << 1) | (fourth_byte >> 7)
```

Thus `0x71, 0x7f` selects read register 2 and a write beginning `0x61`
with a clear high bit in the second byte selects register 2. `0x61` is a
transport prefix, not a newly discovered Si470x opcode. Compare AN230's
3-wire protocol before classifying SPI constants as hidden commands.

The host source's `BootloadDevice` is a stub returning true. That does not
invalidate the separately retained image, but it supplies no executable
updater or independent CRC/decoding implementation. Its audio constants also
describe a host audio format, not proof of tuner IQ output.

## Outstanding reverse engineering

### Initialization replay and request-handler fragments

`tools/replay_fm_mcu_init.py` interprets the original candidate MCS-51 bytes,
rejecting unsupported instructions. It does not execute a reconstructed C
implementation. The environment substitutes SPI replies/completion, readiness,
STC transitions and the delay helper at `0x1b8a`. This is a bounded instruction
model, not a cycle-accurate MCU or RF simulation.

All SPI transactions in the `0x0046–0x03b2` initialization routine are now
recovered. Let P be the initial POWERCFG and S be the initial SYSCONFIG2:

| Step | Register | Operation |
| --- | --- | --- |
| 1 | `0x02` | Read P; write `(P & ~0x0040) | 0x0001` |
| 2 | `0x05` | Read S; write `S | 0x000f` |
| 3 | `0x02` | Read again; write value OR `0x4000` |
| 4 | `0x03` | Write fixed `0x804a` |
| 5 | `0x0a` | Poll until STC is set |
| 6 | `0x03` | Read and clear `0x8000`, preserving the remaining word |

No initialization access reaches TEST1/TEST2/BOOTCONFIG or the command window.
Three different POWERCFG seeds verify preserved bits; a nonzero SYSCONFIG2
seed verifies the volume-only change. With STC withheld, replay reaches its
instruction budget at the poll and never clears TUNE. No timeout or physical
elapsed-time guarantee is inferred.

The USB request code supplies additional register transport paths. Original
instruction fragments were replayed with synthetic register/payload values:

- GET single-register body `0x0dd9–0x0e3d`: report IDs 1–16 select addresses
  0–15, returning the synthetic word in the response buffer.
- GET whole-map body `0x0e48–0x0ebe`: reads exactly sixteen addresses into
  32 payload bytes; instructions at `0x0ebf` set transfer length to 33.
- SET body starting `0x0f19`, stopping before USB state update at `0x0ffe`:
  IDs 1–16 transmit one word to `report_id - 1`; ID 17 transmits all sixteen
  words. This includes bus transactions addressed to TEST1/TEST2/BOOTCONFIG
  and `0x0c–0x0f`. It proves transport formation, not silicon acceptance of
  writes to reserved/read-only words or implementation of hidden commands.

These 34 request-fragment cases, three successful initialization cases and
one missing-STC case cover 38 bounded scenarios. They do not replay a complete
USB enumeration/control transfer or prove all dispatcher paths reachable.
The trace is retained in `work/fm-mcu-candidate/init-replay.json`.

### Actual USB descriptors and sample producer

`tools/inspect_fm_mcu_usb.py` decodes the image's descriptors at `0x0be1`
and `0x0bf3`. The device advertises VID/PID `10c4:818a` and:

| Interface / endpoint | Advertised format |
| --- | --- |
| Audio streaming interface 1, alternate 1, IN `0x83` | Isochronous, max packet 512, interval 1; two channels, two bytes per channel, 16-bit resolution, 96000 samples/s |
| HID interface 2, IN `0x81` | Interrupt, max packet 64, interval 10 |
| HID interface 2, OUT `0x02` | Interrupt, max packet 64, interval 1 |

The HID report descriptor at `0x0c84` spans 203 bytes. IDs 1–16 are two-byte
feature payloads; ID 18 is a twelve-byte input payload; ID 23 is a sixty-byte
output payload. The remaining feature reports cover whole-map and MCU control
data. They are not Si470x command IDs.

One mismatch matters: feature ID 17 advertises a fifty-byte payload, but the
recovered GET loop obtains sixteen words and sets an actual 33-byte transfer
including the report ID. This mismatch does not establish nine extra hardware
registers. The SET all-register loop also stops at sixteen words.

The routine at `0x1a5f` reads SFRs `0xbd/0xbe`, toggles `0xbb` bit 0,
changes the sign bit of the high byte and writes bytes through MOVX. These
addresses correspond to ADC0L/ADC0H and ADC0MX on C8051F320/1. This is a
concrete MCU ADC sample-production path. The descriptor's stereo PCM format
alone would not prove the source. The buffer-to-FIFO connection is now covered
by the original-byte replay below. There is no recovered link
from the Si470x internal I/Q ADCs to that stream. Board analog routing and
physical operation are separate evidence.

### ADC producer to audio FIFO: original-byte replay

`tools/replay_fm_mcu_stream.py` executes the candidate producer at `0x1a5f`
and consumer at `0x17a5`. ADC values, USB register completion and RAM are
synthetic. The shared bounded interpreter models only encountered opcodes,
with an abstract save/call stack and no concurrent interrupt scheduling.
Unsupported instructions still fail. No USB controller or analog converter
is executed on hardware.

The producer alternates ADC0MX bit 0, obtaining ADC0L/H and flipping bit 7 of
the high byte. It writes a four-plane buffer through MOVX:

| XRAM location at frame index n | Byte |
| --- | --- |
| `0x0000 + n` | First sample low byte |
| `0x0100 + n` | First sample high byte XOR `0x80` |
| `0x0200 + n` | Second sample low byte |
| `0x0300 + n` | Second sample high byte XOR `0x80` |

R1 is the producer index and R2 the consumer index in register bank 0.
After the second channel it advances R1, undoing the advance if it would
collide with R2. Tests cover index wrap and that collision branch. Synthetic
sentinels `0x1234, 0xabcd` yield buffer bytes `34 92 cd 2b`; these are chosen
to expose ordering/bit conversion, not to claim physical ADC precision.

The consumer selects USB FIFO 3 (indirect USB register `0x23`), computes the
available frame count from R1-R2, and copies those same four planes in order
to USB0DAT. It advances R2 for each frame. This connects the producer to the
advertised endpoint `0x83` path; there is no Si470x SPI transaction in the
replayed consumer. One test feeds the producer's actual modeled RAM directly
to the consumer and verifies every resulting FIFO byte.

Nonzero frame counts are capped at 97 per invocation (388 bytes). The tests
cover 1, 2, 96, 97, 98 and 200 available frames and pointer wrap. With zero
available frames and fixed pointers, the DJNZ counter underflows and the
fragment copies 256 frames. That edge result belongs to this candidate and
synthetic scheduling profile; it is not a demonstrated player defect or a
USB delivery claim. It is preserved rather than hidden by a model-only guard.

### Endpoint 2 OUT / report 23 boundary

The HID descriptor advertises output report 23, but a descriptor is not a
handler implementation. The endpoint-2 OUT interrupt branch at `0x12b8`
checks saved OUT-pending bit 2 and Timer 2 run bit. When both are set, it
clears the saved endpoint-3 IN-pending bit and calls `0x1af7`, then `0x1bfd`.
Those routines stop the sampling timer and reset/flush the stream endpoint.
The branch neither reads FIFO 2 nor decodes the OUT payload.

Four original-byte scenarios cover both pending-bit and timer-state choices.
No tuner transaction or audio FIFO payload write occurs in this branch.
This resolves the observed interrupt path; it does not prove that report 23
can never be referenced by another request path or a different firmware.

The new replay has fifteen scenarios (four producer, seven consumer, four
OUT-interrupt), in addition to the 38 prior initialization/request-fragment
scenarios. Reports remain in `work/fm-mcu-candidate/stream-replay.json` and
`init-replay.json`. They establish instruction/data-flow behavior under the
specified substitutes, not measured audio, IQ, or live USB qualification.

### GET/SET handler dispatch and external flash boundaries

`tools/replay_fm_mcu_control.py` starts at the actual GET (`0x0da6`) and
SET (`0x0f14`) handler prologues. It sweeps all 256 report-ID byte values
for each direction and all 256 command bytes for SET report 19: 768 cases.
This is handler-prefix coverage, not end-to-end USB setup parsing. It stops
before the mode helper, flash writer, stall helper or response epilogue.
SPI words and USB readiness remain synthetic. The interpreter now separates
upper indirect IRAM from SFR addresses and rejects uncovered MOVC reads.

| Request | Recovered dispatch |
| --- | --- |
| GET/SET 1–16 | One ordinary Si470x register, address ID minus one |
| GET/SET 17 | Exactly sixteen ordinary register words |
| GET 20 | Reads code space beginning at `0x3600`, outside this image |
| GET 22 | Reaches response epilogue with a two-byte length assignment; payload meaning remains unproven |
| SET 19, command `0x35` | Copies payload byte to state `0x2e`, then calls mode helper `0x0958` |
| SET 19, command `0x34` | Compares payload against code bytes `0x3601/0x3602`; matching static branch calls `0x0958`, then `0x3800` |
| SET 20 | Calls `0x1805`, a flash-maintenance routine |
| Other GET/SET IDs | Reach stall helper, including IDs 21 and 23 |

For command `0x34`, replay stops on the first uncovered MOVC at `0x1011`.
The subsequent compare/call sequence is established by static instructions,
not by supplying invented identity bytes. The image ends at `0x1dff`;
`0x3800` cannot be disassembled from this candidate. The GET 20 replay
likewise stops at its first external code read. Neither missing region is
padded with zeroes or represented as a successful response.

The flash writer at `0x1805` disables interrupts, writes the `a5 f1`
unlock sequence to SFR `0xb7`, sets `0x8f` to 3, and performs MOVX at
`0x3600`. It then sets `0x8f` to 1 and emits 63 payload bytes starting
at `0x3600`, finally clearing that control register and re-enabling
interrupts. These are MCU storage-maintenance operations, not extra tuner
register addressing. The prefix replay stops before this routine; it does
not model flash erase/write as ordinary XRAM writes.

The 768 cases comprise 729 stall boundaries, 18 GET response epilogues,
17 SET register epilogues, two uncovered code reads, one flash-writer
boundary and one mode-helper boundary. No special-command case emits a
tuner transaction before its boundary. Results are stored locally in
`work/fm-mcu-candidate/control-replay.json` with image/tool hashes.
This does not exclude further behavior inside the mode helper or missing
bootloader. It does exclude interpreting report 20 as an additional RF
register block in these recovered handlers.

### Mode helper `0x0958`: bounded state sweeps

`tools/replay_fm_mcu_mode.py` executes the original helper through its return.
Two independent sweeps cover every request/current-mode byte pair and every
current-mode/phase byte pair, with zero initial countdown and peripheral SFRs.
Three additional cases exercise nonzero countdown values: 131075 scenarios
in total, visiting 266 instruction addresses. All complete without calls,
tuner transactions or USB register writes. The computed jump at `0x09fa`
is executed, including its eight three-byte LJMP table entries; those bytes
are not treated as linear data instructions.

The helper consumes pending state `0x2e`, selects state `0x2b`, advances
phase `0x2c` and maintains countdown `0x2d`. Recognized request values include
`02, 04, 10, 20, 40, 80, 01` hexadecimal. Output branches update SFRs
`0xea/0xfc` and port P3.0, including increment/decrement and bit-toggle
patterns. The `0x40` request made before the external `0x3800` call therefore
does not itself establish a tuner test mode. No physical meaning is assigned
to these peripheral changes without checking the board routing.

This is exhaustive across each stated pair of byte inputs, not all joint
RAM/peripheral combinations or timer scheduling. It resolves the previously
stopped mode-helper boundary under those inputs. The independent static
listing is retained locally as `mode-disassembly.txt`; the replay report,
image/tool hashes, visited addresses and final-state digest are retained in
`work/fm-mcu-candidate/mode-replay.json`.

### Host command cross-check: LED identification and unused stream declarations

The pinned IanCass host source provides a stronger interpretation than the
peripheral pattern alone. `CFMRadioDevice::ChangeLED` constructs
`{LED_COMMAND, ledState, 0xff}` and passes it to report 19. Its header defines
`LED_COMMAND=0x35`, with states `01` all colors, `02` blinking green,
`04` blinking red, `10` blinking orange, `20` solid green, `40` solid red
and `80` solid orange (hexadecimal). These match the helper's recognized
requests. Thus this is host-identified LED control, while actual board
colors/electrical behavior remain unmeasured. `BOOTLOAD_STATE` is solid red;
setting state `0x40` before the missing `0x3800` call is consistent with a
bootload indicator rather than evidence of RF mode selection.

The same header also defines report 19 `STREAM_COMMAND=0x36`, with
`STREAM_VIDPID=0x00` and `STREAM_AUDIO=0xff`. Its SetStreamReport helper
serializes the supplied payload through HidD_SetFeature. However, the
candidate's SET-19 command dispatcher accepts only `0x34/0x35`; the
exhaustive command replay places `0x36` on the stall boundary. This is a
concrete difference between declared host API and candidate handler, not a recovered IQ command. A
definition and serializer do not establish that the command is supported
by this candidate or that a caller actually uses it. Do not treat colocated
host source and embedded image as a fully matching firmware release.

The complete source archive at the pinned commit was subsequently acquired
and searched across C++ headers/sources, DLL export definitions and VB test
sources. SetStreamReport occurs only as its declaration and implementation;
the three stream constants occur only as definitions. No call site was found.
The actual exported opening path calls InitializeStream, which uses
`waveInStart` and Windows wave-buffer APIs, not the report-19 serializer.
Therefore the difference does not demonstrate a runtime incompatibility or
establish that a separate stream-command firmware release exists. Prioritize
actual transactions over these unused declarations when searching for IQ.

The GitHub path-history endpoint returned one introducing commit,
`5ae20aa62283c782a7d1e358c9809b57c0e48381`, dated 2008-01-25. Its tree
contains the same image blob `56e1c0b23460c091237cb60b377e92d0d8306d96`
as the current pinned tree. No alternate image was obtained from that visible
path history. Commit date is repository history, not authenticated vendor
firmware release identity. The source archive and API response remain in
ignored `work/fm-driver-comparison/`.

### EP0 setup dispatch prefixes

`tools/replay_fm_mcu_setup.py` executes at `0x0766`, after the setup FIFO
read and byte normalization. All 65536 request-type/request-code byte pairs
are swept, stopping before each selected handler. It independently executes
the compiler switch helper `0x153d` against its actual inline table for all
256 request codes. The abstract stack supplies the original return address
`0x07a6`; table destinations are obtained by MOVC and indirect JMP, not
substituted as helper results. Total coverage is 65792 prefix scenarios.

The first split tests only `(bmRequestType & 0x60) == 0x20`. In that class
branch, request 1 selects GET report `0x0da6` for the IN direction and the
receive-setup helper `0x19ad` for OUT. Request 9 selects receive setup
`0x19e9`; request 10 selects `0x1bcb`; request `0x81` selects `0x1971`.
Other class request codes reach stall. Direction/recipient validation is
not established by this prefix alone.

All other type-bit combinations, including vendor and reserved types, share
the switch table at `0x07a6`. Its request codes and selected handler addresses
are `00:1041, 01:1387, 03:142e, 05:1856, 06:1133, 08:16db,
09:12d1, 0a:15ef, 0b:1a25` (hexadecimal); other codes select stall.
No separate vendor test-command table occurs in this prefix. Sharing the
switch is not proof that downstream handlers accept vendor requests or can
return hidden data: index, length, recipient and state checks remain to be
traced there.

The later receive-completion branch statically checks transfer state zero
and request code 9 before calling SET report at `0x0940`. Its packet-copy
helpers and complete length/state evolution are not covered by this prefix
replay. The local `setup-replay.json` records image/tool hashes and all
standard-switch destinations. No physical USB request was sent.

### SET_INTERFACE alternate-setting storage boundary

`tools/replay_fm_mcu_interface.py` executes handler `0x1a25`, stopping at
the stall helper or successful epilogue. Independent sweeps cover all 256
request-type bytes, all 65536 value words, all 65536 index words and four
nonzero length boundaries: 131332 cases. The normalized setup words are
stored big-endian in IRAM after the earlier FIFO conversion.

The handler requires request type exactly `0x01` and zero length. It stores
the low byte of wValue into indirect IRAM `0x8a` only for wIndex exactly 1.
Other indices pass through without changing that byte. It does not check
the high byte of wValue or restrict its low byte to advertised alternates
0/1. Thus `0x0101` and `0x0001` store the same byte; 2 and 255 are also
stored under this model. No tuner transaction or helper call occurs on
these successful paths. Invalid type/length paths stop before the stall
helper; this is not an on-device USB acceptance test.

This is a concrete parameter-validation boundary, not proof of extra stream
modes. A stored alternate byte must be traced through its downstream readers
before interpreting any value as IQ, a test output, or an operational USB
alternate. The local `interface-replay.json` records hashes, scope and sample
values. Peripheral scheduling and physical delivery remain untested.

### Stream-start path does not select from the alternate byte

The interface replay also executes `0x1668` through its return for all 256
stored alternate-byte values. This routine is called by the USB interrupt
path at `0x1284`. It resets endpoint 3, selects register bank 0 and clears
producer/consumer pointers R1/R2. It writes four literal bytes to FIFO 3:
`c4 10 8a 81`, matching the descriptor VID `0x10c4` and PID `0x818a` in
little-endian order. These are fixed startup bytes, not ADC-derived samples
or evidence of tuner I/Q. The intended host interpretation is not proven.

The routine restores the register bank, configures ADC0MX to 9, writes
ADC0L/H to `00/80`, changes USB interrupt enables and sets Timer 2 run.
Across all 256 cases the recorded USB writes are identical, no indirect
read of `0x8a` occurs, and no tuner transaction occurs. The original endpoint
reset helper is executed, not replaced. The model still substitutes USB
readiness and does not simulate interrupt timing or electrical conversion.

This narrows the alternate-setting hypothesis: the inspected startup path
does not use alternate values to select an RF or ADC output mode. The GET
INTERFACE handler separately exposes a pointer to `0x8a` for interface 1,
which is a concrete readback use, not a sampling-mode consumer. Other
possible readers and the complete USB lifecycle remain unproven. The 256
startup cases are retained in `interface-replay.json` alongside the 131332
SET_INTERFACE cases.

### Descriptor selection: unchecked string-table index

`tools/replay_fm_mcu_descriptors.py` sweeps all 65536 descriptor-type/index
byte pairs at handler `0x1133`. Types 1, 2, 3, `0x21` and `0x22` reach
selection boundaries; other types reach the stall call. No tuner transaction
occurs in these prefixes. This does not validate request type or downstream
USB transfer behavior.

For type 3 the original instructions multiply the index by three and read
three code bytes from `0x0d99 + 3*index` as a generic memory pointer. There
is no index bound check before this lookup. Indices 0/1/2 produce
`ff:0d4f`, `ff:0d53`, `ff:0d87`, the normal code-space string addresses.
Index 3 instead produces `01:0000`, from adjacent constants; index 4
produces `00:c0d0`, straddling constants and the next function's prologue.
These are observed pointer bytes, not authenticated extra descriptor entries.

The replay stops at `0x11a9` before generic-pointer dereference, and before
length clamping or packet copying. It therefore establishes an unchecked
selection boundary, not successful arbitrary-memory readout, hidden register
access or extraction of `0x3800`. No replacement bytes are supplied for
missing code. The local `descriptor-selection-replay.json` retains every
selected pointer, scope and image/tool hashes. Further analysis must follow
the generic-memory reader and transfer length before assigning a usable
data-return capability to an out-of-range index.

### Remaining work

Continue through the EP0 downstream handlers and packet/length state machine;
setup dispatch prefixes, GET/SET handler prefixes and mode-helper sweeps are
covered, but the entire USB state machine is not.
Trace indirect IRAM `0x8a` readers before interpreting unadvertised alternate
values as implemented modes; SET_INTERFACE storage alone is insufficient.
Obtain the external `0x3600` storage and `0x3800` bootloader from a
separately attributable PC-side image before assigning behavior to them.
Validate the original page CRC and identify firmware/tuner version before
claiming a same-revision match.

This candidate has not yet yielded an IQ entry sequence. It creates a new,
concrete reverse-engineering path; the earlier missing-software limitation
must no longer be described as preventing all further PC analysis.
