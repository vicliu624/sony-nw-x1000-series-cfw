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
