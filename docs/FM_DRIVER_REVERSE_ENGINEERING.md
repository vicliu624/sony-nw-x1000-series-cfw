# Japanese 1.11 Sony FM driver reconstruction

This analysis targets the original Japanese NW-X1050/NW-X1060 platform. It
reconstructs the host driver, not the silicon's internal firmware. Original ARM
instructions were replayed on the PC with synthetic I2C responses, inert mapped
MMIO and substituted kernel services. No player was opened or modified.

## Input and reproducibility

The input is `lib/modules/icx_si470x_radio_tuner.ko` from the pinned Japanese
1.11 root filesystem. SHA-256:

`c65262032cc8dec3d28ee6061ac267c5de61ef7f78a8744fc983de9941113bcb`

Updater, UPG and rootfs identities are recorded in [KNOWLEDGE.md](KNOWLEDGE.md).
The local updater was unpacked with 7z; `scripts/upg.py:unpack` verified and
decrypted the stock UPG. Only the named module was extracted from component 3.
Keep these proprietary inputs and the full disassembly in ignored
`work/fm-driver-audit/`. Do not commit or distribute them.

With that local module present, run:

```text
python tools/audit_fm_stock.py --module work/fm-driver-audit/si470x.ko
python tools/audit_fm_stock.py --upg work/fm-driver-audit/NW_WM_FW.UPG
arm-linux-gnueabi-objdump -dr work/fm-driver-audit/si470x.ko
```

The second invocation optionally re-extracts the pinned module from a local UPG;
it also checks the rootfs hash and requires pycryptodome.
Dependencies: pyelftools and Unicorn, plus ARM binutils for the independent
listing. The replay verifies the module hash and applies its ELF relocations.
It executes the actual read/write helpers, rather than replacing them with
register-value stubs. The 64 cases cover every valid register index, write
boundaries, failed transfers, initialization for all 13 destination entries,
same-cache reset, sleep, mute/stereo/sensitivity and signal classification.
A command-shaped transaction tests byte transport only; no synthetic property
response is presented as chip acceptance.

## Complete low-level register transport

Offsets below are section-relative `.text` offsets, not runtime addresses.

| Function | Offset | Reconstructed behavior |
| --- | --- | --- |
| `si470x_read` | `0x01c8` | One I2C read at seven-bit address `0x10`; starts at register `0x0a`, wraps through `0x0f` to `0x00`, ends at requested register |
| `si470x_write` | `0x03dc` | Changes one word in a persistent 28-byte write cache, then sends its complete prefix from `0x02` through the target register |
| `si470x_initialize` | `0x0468` | Reset, construct cache, initial 28-byte write, enable, delay, 10-byte configuration write |
| `si470x_reset` | `0x0674` | Reset, cached POWERCFG write, delay, cached 28-byte write |
| `si470x_sleep` | `0x06f0` | Read POWERCFG and write it back with `0x0041` set |

Read length for valid index `r` is `2 * (((r - 10) mod 16) + 1)` bytes.
The selected big-endian word is converted to the ARM integer return value.
Thus reading `0x0a` transfers 2 bytes, `0x0f` transfers 12, `0x00` transfers 14,
and `0x09` transfers all 32 bytes. Reads clear the shared read buffer first.
The helper succeeds only when `i2c_transfer` returns exactly one message;
otherwise it logs an error and returns `-1`.

Write length is `2 * (r - 1)` bytes for `0x02 <= r <= 0x0f`. The word is
encoded high byte first. Other unsigned write indices fail. A failed transfer
leaves the modified cache in place; a subsequent write can resend that value.
Reads do not synchronize the write cache. This is important for experiments:
a high-register write can overwrite lower configuration with stale cached data.
The shared buffers have no visible locking in these helpers.

The read helper uses a signed upper-bound comparison and does not reject
negative indices. Never pass unvalidated indices, even for a nominal GET.

## Initialization, byte for byte

`fmHardwareResetPulse` (`0x0178`) operates Sony SoC MMIO: update
`0xec81021c` to `(old | 1) & ~4`; write `0x200` to `0xec050000`, then
`0x02000000` to `0xec050008`; sleep 1 ms; write `0x02000200` to
`0xec050008`. These are observed CPU accesses, not a verified board pin map.

`si470x_initialize(client)` then performs:

1. Clear the 32-byte read buffer and 28-byte write buffer.
2. Read register `0x09`, obtaining all sixteen registers in wire order.
3. Copy the observed `0x02–0x09` words and `0x0a–0x0f` words into write
   cache order. Replace `0x02–0x06` from the compiled initialization table.
4. Clear bits `15:14` of cached `0x07`; retain its remaining bits. Preserve
   `0x08` and `0x09`. Replace `0x0a–0x0f` with six zero words.
5. Set the initial channel to `(cached_kHz - 76000) / 50` for an in-range
   cached frequency, otherwise channel zero. This overwrites table channel
   `0x006a`; it is not a test unlock value.
6. Look up the NVP destination in a thirteen-entry table. For table indices
   selected by mask `0x1a1e`, clear `SYSCONFIG1 & 0x0800`; otherwise set it.
   Final low byte is `0x84`. Set the SYSCONFIG2 high byte to `0x12`.
7. Send all 28 bytes, registers `0x02–0x0f`.
8. Read `0x02`, OR with `0x0001`, write `0x02`. Sleep 111 ms.
9. Send the first ten cached bytes, registers `0x02–0x06`.

The resulting initial payload is:

| Register | Word sent | Origin |
| --- | --- | --- |
| `0x02` | `0x0001` | Compiled table |
| `0x03` | Channel number | Cached frequency calculation |
| `0x04` | `0x0084` or `0x0884` | Destination-dependent configuration |
| `0x05` | `0x126f` | Compiled table plus forced threshold byte |
| `0x06` | `0x1000` | Compiled table |
| `0x07` | `read_07 & 0x3fff` | Preserved low bits; upper two cleared |
| `0x08` | `read_08` | Preserved |
| `0x09` | `read_09` | Preserved |
| `0x0a–0x0f` | Zero | Compiled table tail |

Sony's GPL MP201 headers and register list identify the reset helper's
MMIO addresses. The mapped `0xec81021c` is `SMU_PCTL_SPI`, and
`0xec050000` / `0xec050008` are GPIO bank 0 output enable and data output.
The latter uses a write-enable mask in the upper halfword. The stock
sequence enables SoC GPIO P9, drives it low, waits 1 ms, then drives it
high. This locates the SoC reset-control candidate for schematic tracing.
It does not establish continuity to a particular tuner package pin.

Interpreted against the [Si4702/03-C19 register map](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/Si4702-03-C19.pdf),
both stock SYSCONFIG1 words select GPIO2's interrupt function and put
GPIO1 and GPIO3 into high impedance. The STCIEN and RDSIEN enable bits
are both clear, matching the driver's STC polling path. This establishes
the documented meaning of the written bits for the C19 register map.
The GPIO2 selector alone provides no evidence of a routed interrupt or
sample stream, and the player's exact part revision remains unmeasured.

No separate oscillator-enable/test-unlock write occurs in this initialization.
The destination is read from NVP item 11 and model ID from item 16 during
module initialization; this code does not establish the physical tuner subtype.

`si470x_reset` is different from full initialization: it reuses the existing
write cache, sends its first two bytes, sleeps 111 ms, then sends all 28 bytes.
Replaying reset against an empty cache is not representative of normal resume.
The same-cache test explicitly checks this distinction.

## Other paths and debug access

`fm_open` initializes hardware, requests stereo, selects sensitivity 6, and
then calls `video_exclusive_open`. Initialization therefore precedes that
exclusive-open result. A read-only open is not a passive register snapshot.
Release sleeps the chip and asserts reset. Suspend, when active and event 2,
mutes and sleeps. Resume phase 0 performs cached reset, mute, stereo and
sensitivity setup; phase 1 tunes the saved frequency and unmutes. Shutdown
sleeps an active tuner. `fmDisableClock` is an empty function in this module.

Other register operations:

- Mute clears POWERCFG `0x4000`; unmute sets it, with Sony ADC mixer handling.
- Mono sets POWERCFG `0x2000`; stereo clears it.
- Sensitivity changes SYSCONFIG2 high byte: input 6 maps to `0x12`, input 11
  maps to `0x2b`, other inputs are shifted into that byte.
- Tuning reads band/spacing from `0x05`, writes the calculated channel to
  `0x03`, waits 2 ms, writes channel OR `0x8000`, waits 20 ms, then polls STC
  up to eight times with 5 ms waits after unsuccessful reads. It does not
  clear TUNE at completion; the next tune's first write clears it.
- `fmGetSigStrength` (`0x0ab0`) returns false when `STATUSRSSI & 0x1000` is
  set. Otherwise it compares the low eight RSSI bits strictly greater than
  the SYSCONFIG2 threshold plus an OLED correction. The correction is 6 near
  89700 kHz (strictly inside +/-150 kHz), otherwise zero. The public ioctl
  converts this Boolean to 0 or 65535. Actual RSSI is therefore present and
  discarded by that public API.

The module exposes `/proc/fm` entries `r0` through `r15`, plus `scanth`.
They are register/threshold text readers. `ProcWrite` copies input but returns
an error without issuing a register write. There is no proc test-mode parser.

Private `fm_do_ioctl` branches:

| Command | Meaning / limitation |
| --- | --- |
| `0xc0207629` | Full hardware initialization |
| `0xc020762a` | Register index in byte 0, value in halfword at byte 2; uses cached-prefix writer |
| `0xc020762b` | Index in first word; stores read result at byte `4 + 2*index` |
| `0xc020762c` | Read all; writes 36 bytes although ioctl size is 32 |
| `0xc020762d` | Direct tune using kHz argument |

Single GETREG has no output bounds check: indices `0x0e` and `0x0f` write
outside the declared 32 bytes; indices up through `0x0d` fit arithmetically.
The current application conservatively allows only `0x00–0x0b`. It must not
be extended to all sixteen registers without addressing this ABI. `/proc/fm`
may provide a separate path to the upper words, but its lifecycle, permissions
and cross-read consistency have not been qualified on hardware.

### Identity baseline through the proc reader

The Japanese module's `s_ProcFops` has `ProcRead` at offset 8 and
`ProcWrite` at offset 16, with no open or release callback in the table.
The register branch of `ProcRead` at `.text+0x2f4–0x318` calls
`si470x_read` and formats the result as a register name and hexadecimal
word. The `s_ProcEntry` records for `r0` and `r1` have mode 0440.
The read uses the existing client and issues one 14-byte or 16-byte I2C
read, respectively, through the register wrap at `0x0f`. Opening and
reading these entries bypasses the V4L radio-open initialization path.
The device must already be in a usable state, and the permission mode
does not establish the live owner or group.

The proc formatting path does not reject a failed `si470x_read`. The
latter returns -1 when `i2c_transfer` fails to complete one message.
The proc reader formats that value with a minimum width of four hex
digits, yielding `ffffffff` on the stock ARM32 ABI. A future baseline
must reject that output rather than treating it as a 16-bit register
word. Separately read entries represent separate bus transactions.
Timestamp them and keep the raw strings, especially for STATUSRSSI and
READCHAN, whose states may change between reads. An offline ARM replay now executes `ProcRead`, `GetEntryIndex`, and
the original I2C read helper for all 16 entries, with successful and
failed transfers for each. Synthetic file, inode, adapter, formatting,
and user-copy fixtures supply the environment. All 32 cases pass.
The bytes delivered to the user-copy boundary contain a four-digit
word on success and `ffffffff` on transfer failure. The identity
entries issue exactly the expected 14 and 16 data-byte reads.
The script and trace are in `work/fm-board-evidence/replay_fm_proc.py`
and `work/fm-board-evidence/fm-proc-replay.json`. This replay has not
been used for a live capture.

### Interpreting a future chip-ID capture

For the B17 and C19 Si4702/03 register layouts, split DEVICEID into
`PN = (r0 >> 12) & 0xf` and `MFGID = r0 & 0xfff`. The documented
`0x1242` identifies the Si4702/03 family and Silicon Labs manufacturer.
Split CHIPID into `REV = (r1 >> 10) & 0x3f`,
`DEV = (r1 >> 6) & 0xf`, and `FIRMWARE = r1 & 0x3f`.
The [B17 datasheet](https://atta.szlcsc.com/upload/public/pdf/source/20241021/434AA0351445080BBE4991FA31C3A850.pdf)
uses REV 2 for B, while the
[C19 datasheet](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/Si4702-03-C19.pdf)
uses REV 4 for C. In both published layouts, active DEV 1 denotes
Si4702 and active DEV 9 denotes Si4703. Preserve raw values and the
POWERCFG enable state alongside each decode. B17 can report DEV 0
before power-up without distinguishing the variants. C19 specifies
pre-power-up DEV 0 for Si4702 and DEV 8 for Si4703.

Use the part-specific document to interpret REV, DEV and FIRMWARE
together. Do not translate an unknown revision code into a suffix
or assume these field widths apply to the older Si4700/01 family.
These are reference values. The Japanese device's ID words are
still unmeasured.

### Stock factory test utility

The Japanese root archive includes `usr/local/test/icx_si470x_test`
(version 0.10), SHA-256
`0a6215e018939b7233a0f89fed9d9c3b72a36352535955d7fcb295a817842815`.
The ELF inspected locally matches the archived entry byte for byte.
The 14-entry command table at `0x123c4` dispatches initialize, tune,
seek, scan, single and whole-map reads, continuous register reads, a
register write and help. It also contains a terminating entry.
The help advertises interface selection and a separate RSSI command,
but those names have no command-table entries.

The continuous `rt` path at `0x905c` loops over `tuner2GetReg` and
printing, with no delay in that loop. It uses the existing private
GETREG ioctl `0xc020762b`. The whole-map helper at `0x8d64` calls
`0xc020762c`, then copies 32 bytes from the local argument at offset 4.
These are repeated stock register operations. The ELF imports no raw
read/write or bus-transfer function. Main opens `/dev/v4l/radio0`
before dispatch, invoking the initialization path described above even
for a read command. The utility was examined statically.

The Japanese factory GUI `usr/local/bin/mptapp` was also matched to
the stock root archive (SHA-256
`d3417610b5d20aaf8678cf07cd5cf0196fdd00b562d0fdc52e5c7aaf771eb59c`).
Its direct radio-device string reference at `0x22e34` loads
`/dev/v4l/radio0` and passes zero open flags. The adjacent tuner
register helper at `0x22ea8` reads register 5 with `0xc020762b`,
clears its low nibble, adds the supplied volume value and writes
register 5 with `0xc020762a`. This is SYSCONFIG2 volume control.
Separate DSP and I2C pathname references in the same executable are
insufficient to associate those devices with FM. This static inspection
covers the located direct radio helpers, not the entire factory GUI.

An ARM branch-reference scan locates the factory GUI tuner open at
`0x101e4`, tune call at `0x10250`, and volume call at `0x102d8`.
The tune helper at `0x22e48` shifts the supplied frequency left four
bits and passes it to stock `VIDIOCSFREQ` (`0x4004760f`), then
issues `VIDIOCSAUDIO` (`0x40287611`). A second caller of the radio
open helper occurs at `0xd4b0`. The located tuning and volume callers
use the ordinary V4L path. This scan covers immediate ARM branches to
the identified helpers and leaves indirect dispatch and the separate
audio helpers open.

The FM entry block at `0x101e4–0x10218` calls the common audio-mode
helper at `0x1a6348` with selectors 8 and then 6. On its active
hardware branch the jump table maps them to source values 1 and 2,
respectively. Both paths join at `0x1a63f8` and issue
`AUDIO_SET_SOURCE` (`0x40046103`) at `0x1a6414`. Sony's GPL audio
header names these source values LINE and TUNER. This independently
connects the factory FM entry to the same codec input-selection path
as SpiderApp, and records a preceding LINE selection. These ioctls
set the playback source. The subsequent shared audio helpers and
their relationship to DSP capture are not resolved by this trace.

## Hidden-mode and IQ findings

The recovered host driver has no implemented raw-sample capture, IQ buffer,
sample-rate negotiation, alternate I2C target, bank-selection sequence or
nonzero command written into `0x0f`. Its register helpers address only the
sixteen-word window. The special-frequency code adjusts station detection
thresholds; it does not change RF output mode. Initialization accesses the
test/reserved region, but preserves `0x08–0x09` and the low bits of `0x07`;
this is not evidence of an IQ unlock.

This bounds the **Sony module**, not all silicon capabilities. Undocumented
commands, test pins or chip-internal modes remain unexcluded. There is no
measured IQ output, and no basis to claim that such an output is impossible.

A concrete additional avenue is the Rev C-or-later command processor, which
uses registers `0x0c–0x0f` while RDS decoding is disabled. GET_PROPERTY can
return SNRDB (`0x0c00`, 2 dB steps) and CALCODE (`0x0700`, power-up calibration).
These are documented in AN230 sections 4 and 5, unlike a hypothetical IQ mode.
They are properties, not physical register addresses. Sony does not use this
interface in the recovered module. Earlier claims that only SNR thresholds
were available were incomplete. See the vendor's
[AN230 programming guide](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN230.pdf).

The original cached-prefix writer can physically form the required 28-byte
command transaction. However, writing `0x0f` also resends cached lower words,
and the stock single-read ioctl cannot safely return `0x0f`. Capability is
conditional on actual DEVICEID/CHIPID and a corrected, owned diagnostic path.
A property named read-only still requires command writes and is not a passive
hardware operation. No property command was sent to the player.

## Next evidence needed

The [external implementation comparison](FM_EXTERNAL_IMPLEMENTATIONS.md)
tracks oscillator constants, USB bridge commands and EVB software candidates.

First obtain exact silicon identity and a normal register baseline under an
explicitly authorized, lifecycle-controlled hardware session. If Rev C or
later is confirmed, qualify VERIFY_COMMAND and known SNR/calibration property
reads before investigating undocumented command IDs. Preserve lower-register
state and use bounded polling and an audited output path. Do not brute-force
reserved writes through the unsafe ioctl.

For IQ, the next PC research targets are same-revision factory tools and other
original drivers with different test sequences, followed by a board-level
output-path inventory. A credible IQ claim needs a reproducible entry sequence,
an actual data outlet, clock/rate information and measured quadrature samples.
Continuous raw RSSI, tune completion, actual channel and conditional SNR are
already stronger concrete data candidates than the Sony binary signal field.

### Property-response capture boundary

The original AN230 Rev 0.61 two-wire example uses a 28-byte write
beginning at register `0x02`, preserving the lower ten register words
and placing seven argument bytes plus opcode `0x08` at the end.
The eight-byte tails for SNRDB and CALCODE are respectively
`00 00 00 00 0c 00 00 08` and `00 00 00 00 07 00 00 08`.
These are documented command encodings, conditional on an identified
Rev C or later device in power-up with RDS disabled.

A single 12-byte two-wire read beginning at `0x0a` contains
STATUSRSSI, READCHAN, RESP0 through RESP6, and command STATUS in that
order. Read byte 11 for command status. AN230's example returns
`0x08` while busy and `0x00` when the response is valid. Only then
interpret bytes 4 and 5 as the big-endian property value. SNRDB uses
the low byte in 2 dB steps in the later guide. CALCODE uses the
whole word. Rev 0.61 documents SNRDB but does not list CALCODE.
[AN230 Rev 0.9](https://www.digikey.ch/htmldatasheets/production/1732787/0/0/1/Si4700-03-Prog-Guide.pdf)
documents both. This difference in coverage does not date the first
firmware that implemented CALCODE.

The original driver reads all 12 bytes for index `0x0f` but returns
only the final word. Reading `/proc/fm/r12` and `r15` would produce
separate transactions. A future diagnostic needs a safe owned
transport that preserves the response and status from the same
transaction, as well as the pre-command configuration. No property
command or response has been measured on the player.

The PC audit runs the original ARM read and write helpers for both
property encodings. It checks the complete 28-byte writes and the
12-byte read messages at I2C address `0x10`. Busy and ready responses
are separate synthetic inputs for each property. The trace retains
the entire bus message and extracts the property word only for the
ready fixture. The original helper still returns only the final word.
This verifies transport and capture boundaries, with no simulated
command processor or measured property values.

## Japanese firmware audio route below the mixer

The stock SpiderApp FM wrapper selects source 2 through mixer ioctl
`0x40046103` and selects source 0 on exit. The existing wrapper replay
stops at the ioctl. The Japanese stock kernel's `SetPlaybackSrc` at
`0xc016f7dc` passes that source to the specific-driver callback at offset
`0x50` (`0xc016f870`).

The Japanese root archive contains `lib/modules/r2A15602LG_d.ko`, SHA-256
`064b36391df6fdd675e0ea410f275675e0e1ff5f71ec93e3ec104571bf8be578`.
The inspected module matches the archived entry byte for byte. In
`.init.text`, the instructions at `0x118–0x11c` install the relocated
`set_playback_src` function (`.text+0x9b4`) at offset `0x50`. The
registration call is at `.init.text+0x2c8`. Local branches in this module
have R_ARM_PC24 section relocations, so unrelocated disassembly displays
misleading branch targets.

For source 2 the relocated jump-table entry at `.text+0xab0` points to
`0xb8c`, which calls `enable_main_adc_input(1)`. If the ADC enable state
changes, the inner function invokes its control callback with selector
and mask/value pairs `f3:80/80`, `fa:01/01` and `f9:01/01`. The
source-2 branch then calls `s_device_output.set_hp(1)` at `0xbc0`.
The literal at `.text+0xda8` relocates to `s_device_output`, and
`r2A15602LG_output_init` installs `set_hp` (`.text+0x44c0`) at offset
`0x1c` via `.text+0x54b4–0x54c0`. The callback checks its cached state
and updates headphone-output controls on its active path. This resolves
the callback as a headphone setting rather than evidence of serial ADC
routing. The source handler issues selector/value pairs `c2:c0` and `c3:00` on the
common path and requests an MP200 clock-gate close at `0xc58`.
These are module-local callback arguments. Their physical register
semantics and the ADC-to-host transfer remain unresolved. The clock-gate
identity is established below.

This connects the Japanese FM source selection to the audio module's
main ADC input enable. The [Sony NWZ service manual mirror](https://manualzz.com/doc/3476369/sony-mp3-user-s-manual)
covers export models and its searchable text does not resolve the tuner
part number or the pin-level audio route. Japanese board continuity,
GPIO connections, sample rate and availability of an FM capture stream
remain open. Generic ALSA capture symbols in the kernel do not establish
that this route feeds a capture device.

### Codec PCM interface state

A [Renesas product-change notice](https://www.renesas.com/en/document/pcn/unification-jedec-tray-and-embossed-carrier-tape-lqfp-package-pc-wrp-a001ae?r=1055021)
lists the full part code `R2A15602LG#U00S`. It provides packaging
change information and does not specify PCM register fields or audio
routing. It therefore cannot resolve the module's `0xc2/0xc3` values.
The `#U00S` suffix is a document search identifier, not a verified
marking on the Japanese player's chip.


The R2A15602LG module names two one-byte cache variables
`reg_pcm_if_0` and `reg_pcm_if_1`, both initialized to `0xff`.
In `power_down`, selectors `0xc2` and `0xc3` are read into the two
caches before the routine writes `c2:c0` and `c3:00`. In `power_up`,
the corresponding cached values are restored when the tested cache
byte differs from `0xff`. The FM source handler writes the same
`c2:c0`, `c3:00` pair on its common source-switch path. This identifies
the two selectors as PCM-interface controls and shows that the observed
pair is shared with a power transition. It does not decode the field
values or establish active serial output.

The same module's relocated diagnostic register table independently labels
`0xc2` and `0xc3` PCM Interface 0 and PCM Interface 1. The neighboring
Noise Shaper Control 0 entry has a PCM input-selection annotation at
`0xc8`; that label describes a noise-shaper input and cannot establish
the direction or source of serial PCM data.

The stock `r2A15602LG_init` executable (SHA-256
`c4754678052b0aa6c5b3ee2657ce4f6c54e02d79e38c1a81ae28d22c38abb7b2`)
loads the `data_1_*` and `data_2_*` audio parameter files and sends
them through `AUDIO_SET_BINARY_DATA` (`0x40046113`) on
`/dev/sound/dsp`. The call site is at `0x8778`. The GPL kernel
dispatches that ioctl to `set_binary_data_from_user`. Presence of
the DSP device path here identifies parameter loading. The loader
takes two little-endian words at offsets 0 and 4 as descriptor ID and
payload length, and passes file offset 8 as the data pointer.

Both default files match the Japanese root archive byte for byte and
use ID `0xaa000001`. Their payload lengths are 11,821 and 1,633 bytes,
respectively, exactly the file sizes minus eight. The payloads begin
with `0x84` and `0x04`. In `set_binary_data` the high-bit branch
masks off bit 7 and dispatches `0x84` to `.text+0x2328`. The low-bit
dispatch table sends `0x04` to `.text+0x2bf0`.

The latter branch swaps byte order in several coefficient blocks and
uses a fixed series of codec selectors, including `0xc8` for the noise
shaper and `0x42/0x43` for block transfers. The `0x84` branch has both
fixed selectors and computed block-transfer arguments. Neither branch
contains a direct immediate `0xc2` or `0xc3` register write. The
computed arguments, callbacks and downstream transfer addresses have
not been exhaustively resolved, so this is a bounded static finding.

Default file SHA-256 values in file order:

- `53abf1a2ee54a16667f11e8234cb44ebb18eb6166b0738a09bbc1045d26a59b7`
- `e5ce7b4f8b72ccc64d47a7bc8edb0ebc30fa8299a186a42272cb8cce816c85c3`

An offline ARM replay of `set_binary_data` with the two pinned payloads
and a length-bearing buffer descriptor resolves the computed arguments
at the device-callback boundary. It runs each payload with the
`device+0x24` state word set to 0 and 1. All four cases return zero with
synthetic successful callbacks. Each block tuple below gives the first
two selector arguments and the length in bytes.

| Input | Block transfer tuples (hex selectors, decimal length) |
| --- | --- |
| `data_1_default` | `00:00/6232`, `20:fe/6`, `21:00/3066`, `31:00/2334` |
| `data_2_default` | `42:00/512`, `42:80/512`, `43:00/512`, `41:80/96` |

No captured callback uses `0xc2` or `0xc3` as its first selector.
Codec I/O and the callback's interpretation of these arguments are
outside the model. The replay script and trace are in
`work/fm-board-evidence/replay_codec_data.py` and
`work/fm-board-evidence/codec-data-replay.json`.

The device constructor stores the relocated `write_ram` address
(`.text+0x17fc`) at device offset `0xe0` via `.text+0x14fc–0x1504`.
A second offline replay follows that callback through the stock
message construction to a substituted `i2c_transfer`. In all four
cases each block became one write message to seven-bit address
`0x1e`, with its two selectors as the first two bytes, followed by
the payload and a total message length of payload length plus two.
This identifies the on-wire prefix at the driver boundary. It is
a codec RAM upload, distinct from the Si470x register target `0x10`.
Single-register callbacks and transfer results are still synthetic.
Neither the meaning of the uploaded DSP code nor its effect on the
physical PCM output is established by this replay. Local artifacts:
`work/fm-board-evidence/replay_codec_wire.py` and
`work/fm-board-evidence/codec-wire-replay.json`.

The relocated source jump table at `.text+0xaa8` supplies a comparison
with known PCM playback:

| Sony source | PCM-interface writes in source-switch branch | Main ADC request |
| --- | --- | --- |
| PCM (0), WAT (4) | `c3:01`, then `c2:00` | Disable |
| LINE (1), TUNER (2) | `c2:c0`, then `c3:00` | Enable |
| NC listening (5) | `c2:c0`, then `c3:00` | Enable |
| MIC (3), NC earpiece (6) | No direct write in these jump-table branches | MIC preserves state here; NC earpiece requests disable |

The PCM/WAT path at `0xad8` bypasses the common LINE/TUNER pair at
`0xc18`. The different programming establishes distinct interface
states for PCM playback and tuner playback. Since the same tuner pair
is also used in power-down, its presence does not establish that the
FM ADC is exported as serial PCM. Direction and individual bit
definitions remain unknown.

The module also treats source 2 differently when enabling the reference
clock. In `set_playback_src`, the comparison at `.text+0xa8c` skips the
gate-open call at `0xa98` for source 2. In `power_up`, the comparison
at `.text+0x124` likewise skips `icx_sound_open_codec_clock` at `0x12c`
when the saved source is 2. With the FM source's later REFCLKO gate
close, this is evidence that the driver treats tuner playback differently
from sources using the codec reference-clock setup. The register field
definitions and external bit/frame clocks remain needed to infer ADC
capture behavior.

### MP200 DSP read path

In the same pinned Japanese kernel, `DspOpen` at `0xc01710ec` passes
the descriptor at `0xc027a938` to `mp200_audio_attach`. The descriptor
has an input stream pointer `0xc027a990` at offset 4 and hardware init
callback `DspHwInit` at offset `0x18`. The input descriptor contains
`0x400c0028` at offset `0x48`. Sony's
[NW-X1050 GPL kernel archive](https://oss.sony.net/Products/Linux/Audio/NW-X1050.html)
identifies that address as the read-only `PM0_RXQ` in
`arch/arm/mach-mp200/mp201regs.c`. In `sound/oss/icx1087-sound.c`,
the matching input stream uses `MP200_DMAC_P2M_LCH4` and the PCM0 receive
queue at base plus `0x28`. Its default is stereo `AFMT_S16_LE`.
The PCM0 port is configured as a slave with left-justified 16-bit slots
and a 32-bit frame. These settings describe the host receiver and still
require an external source of bit and frame clocks.

On successful attach, the routine installs `audio_read` at file-operations
offset 8 (`0xc016e920–0xc016e928`). The read path loads the input stream
from descriptor offset 4, prepares a buffer, calls `audio_prime_rx` and
`audio_read_wait`, and uses `__arch_copy_to_user` at `0xc016ce44`.
`audio_prime_rx` calls `audio_process_dma` at `0xc016c450`. Thus the
stock MP200 DSP interface has a receive DMA-to-userspace path independently
of the generic ALSA capture code.

The FM source-2 branch passes clock-gate token `0x0200000f` to
`mp200_pmu_close_clockgate`. The MP201 branch of
`include/asm-arm/arch-mp200/pmu.h` maps this token to
`MP200_CLOCKGATE_REFCLKO`. The PM0 serial and peripheral gates have
distinct tokens, `0x0100001a` and `0x01000018`. The FM branch gates a
reference output. This does not identify the codec's resulting serial
clock source or prove that PCM0 receives frames during FM operation.

The GPL `DspIoctl` speed handler reports nominal 11025, 22050 or 44100 Hz
by programming the reference divider. These are software-reported rates.
For PCM0 as a slave, actual frame cadence depends on the source of
the external clocks. Still needed are the codec serial output settings,
the PM0 input pin mapping and confirmation that the FM ADC signal is
routed to that output. The archive SHA-256 is
`286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309`.

The [Sony export NWZ service manual 9-889-490-01](https://manuals.plus/m/4baa3c7c6295eda8eca33aae1921553760461028d92bcd07edbafd9fe2aa95b8.pdf)
does not supply a full MAIN board schematic. Page 27 explicitly limits
the circuit drawing to a switch-service excerpt. Page 28 provides MAIN
board component placement for both sides and named test points, including
`CL101` (LINE_OUT_L) and `CL201` (LINE_OUT_R). These labels describe
line output and do not identify the Si470x LOUT/ROUT nets. The drawing is useful
for locating designators but insufficient for establishing tuner-to-codec
or codec-to-PCM0 continuity. The accompanying export assembly list
cannot identify the Japanese assembly or installed tuner stepping.
The [Brazilian certification exhibit index](https://fccid.io/ANATEL/00825-09-04437)
lists external photos, labels, a manual and certificate for both export
capacities, with no internal-board exhibit in that index.


### Sony FCC internal photographs

Sony's [AK8NWZX1000 internal-photo exhibit 1065471](https://fccid.io/AK8NWZX1000/Internal-Photos/Internal-Photos-1065471.pdf)
contains three pages naming NWZ-X1050/X1051/X1060/X1061. The local
PDF and its native JPEGs are retained in `work/fm-board-evidence/`.
Page 2 shows both main-board faces, while page 3 provides a closer
view of the WLAN area with and without its shield.

A small marked QFN near the board corner and printed M12 area is
visible in the close view. Its position and package can be compared
with the service placement drawing, but the photo's native 640-by-480
resolution is insufficient for a reliable full marking transcription.
It is a candidate location for the tuner. This exhibit supplies
actual export-board imagery but does not identify the Japanese tuner
stepping or establish audio-net continuity.

### Control-bus bandwidth bound

The Sony GPL `icx1087_fu_defconfig` selects the MP201 and built-in MP200 I2C
driver. `drivers/i2c/busses/i2c-mp200.c` initializes the adapter to standard
mode and names 100 kHz as its default clock parameter. That parameter also
appears in polling delays, so its value alone is not a measurement of SCL.
The following are conditional wire-rate bounds at 100 and 400 kHz,
excluding START/STOP, clock stretching, scheduling and bus contention.

| Read model | 100 kHz SCL | 400 kHz SCL |
| --- | ---: | ---: |
| Ideal unbroken byte stream, nine clocks per byte | 11.1 kB/s | 44.4 kB/s |
| One stock sixteen-word register snapshot, 297 clocks including address | 336 snapshots/s | 1,347 snapshots/s |
| Ideal 16-bit I plus 16-bit Q, if a sample stream existed | 2.78 kpair/s | 11.11 kpair/s |

The stock read starts at register `0x0a` and wraps through the sixteen-word
map. It exposes register snapshots, with no established sample FIFO or
continuous sample mode. The idealized rates are ceilings for a hypothetical
stream at the stated clocks. They provide neither evidence of sample
production nor an observed I2C clock rate on the target.
