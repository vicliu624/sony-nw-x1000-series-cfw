# Japanese 1.11 DTV HAL

The normal 1seg path is an unidentified tuner/demodulator feeding serial MPEG
transport packets into MP200 FIFO/DMA, then `/dev/dtv` and Sony's userspace HAL.
No raw ADC/IQ output, extra demodulation mode or commercial silicon identity is
established. The bindings below describe original ARM code, not public SDK APIs.

## Original inputs

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| SpiderApp | 6,424,608 | `80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85` |
| mptapp | 3,144,248 | `d3417610b5d20aaf8678cf07cd5cf0196fdd00b562d0fdc52e5c7aaf771eb59c` |
| Responder | 5,605,016 | `71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261` |
| dtv.ko | 25,532 | `421fb85fa2e90b2019cc2a47fb17761e072121b97fc47cc668dbd9f5c0f76cac` |

The root input and Sony GPL provenance are pinned in [platform knowledge](../KNOWLEDGE.md)
and `sources/kernel-download.json`. A recorded device-file MD5 for `dtv.ko`,
`3840bb125cc9b76e4331d94437fa2963`, matches this input. That establishes file
correspondence, not a readback of loaded module RAM.

## Initialization and bus interface

| SpiderApp address | Role |
| --- | --- |
| `0x2322bc` | HAL initialization: open `/dev/i2c/0` and `/dev/dtv`, obtain DS selector and choose initialization branch |
| `0x231a14`, `0x231f7c` | Initialization for stored control selectors `0x20`, `0x30` respectively |
| `0x2307f8` | Set I2C target with ioctl `0x703`, then write register index and value |
| `0x230888` | Two-message I2C_RDWR (`0x707`): write register index, read requested bytes |
| `0x23069c`, `0x230740` | Configuration write helpers; the latter wraps `FE / secondary target / payload / FE` |
| `0x2304e0` | DTV reset and serial transport-stream capture configuration |
| `0x230930` | Channel-table selection and tagged parameter writes |

Initialization queries `/dev/icx1111_sysinfo` with `0x80047306`, Sony GPL
`GET_DS_STAT`. Named values are `SYSINFO_DS_140=1` and `SYSINFO_DS_160=2`.
They select software branches, not part numbers or frequency bands. The
recorded board revision `0x0ea1a582`, through
`((system_rev & 0x1000) >> 12) | ((system_rev & 0x08000000) >> 26)`, yields 2
and predicts selector `0x30` on that captured boot. Do not substitute it for a
new device's identity.

The single-register helper shifts its supplied target value right by one
before I2C_SLAVE. Stored `0x20`/`0x30` values therefore are not already seven-bit
bus addresses. A secondary stored target defaults to `0xc0`; forwarded
transactions do not establish a physically separate tuner or accessible IF node.

The two branches reference 50-byte tables at `0x483110` and `0x483142`.
Original instruction replay of `0x231f7c` produces 25 register writes and one
50-byte forwarded payload. Register `0x76` receives `0x08`, an argument omitted
by one decompilation. The other branch has 64 single-register-write call sites.
Decompiler prototypes and numeric lookup results must be checked against the
actual virtual address and ARM instructions.

The selector-`0x30` initialization payload contains 25 tag/value pairs. Tags
`0x33..0x36` hold `76 44 92 49`, the channel-13 parameter. Initialization ends
with `09 f0`; ordinary retune uses a different, shorter sequence. These are
configuration writes, not an identified executable loader or sample upload.

## Channel programming

`0x230930` copies a 400-byte table from `0x482df0`: 50 eight-byte rows for
selectors 13 through 62. The four parameter bytes, interpreted big-endian,
increase by `0x01800000` per channel, from `0x76449249` to `0xbfc49249`.
The writer sends `09 f0`, a 20-byte tagged sequence, then `09 f4`. That sequence
has six fixed pairs and four channel-parameter pairs at tags `0x33..0x36`.

The lower writer does not reject selectors 12 or 63. Replay with caller R4
`0x12345678` produces bytes `78 56 34 12`; R4 `0xa5a5a5a5` produces
`a5 a5 a5 a5`. This exposes a caller-state dependency outside valid table
selection. UI bounds and a verified encoder are required before any tuning
extension. The step is a protocol fingerprint, not a PLL clock, IF frequency
or proof of continuous tuning.

## Status and post-tune operations

Status routine `0x23262c`, used by `0x22f904`, supplies BER/PER/MER, OFDM mode,
guard, modulation, code rate, interleave, segment count and AGC diagnostics.
It is not read-only: automatic control and counter processing perform writes.

| Registers in selector `0x30` | Observed software use |
| --- | --- |
| `0x60` bit 0 | Measurement-ready gate; cached values otherwise |
| `0x9d..0x9f` | Big-endian 24-bit count for rate conversion |
| `0x76` bit 0 | Pulse after rate processing |
| `0x8b..0x8d` | Big-endian 24-bit measurement converted through the MER table |
| `0xb0` | Acquisition stage in low nibble; mode bits 7:6 and guard bits 5:4 |
| `0x80` bit 5 | TMCC validity; invalid output is `0x80000000` |
| `0xb2` bit 0 | Partial-reception flag |
| `0xb3` bits 7:5 / 4:2 | Layer-A modulation / code rate |
| `0xb3` bits 1:0 plus `0xb4` bit 7 | Interleaving |
| `0xb4` bits 6:3 | Segment count |
| `0x82` | IF AGC diagnostic byte, not calibrated dBm |
| `0x1e` bits 5:4 | Conditional control using thresholds `0x4c` and `0x7d` |

Automatic control below AGC 76 can set `0x1e` mask `0x30`; above 125 can replace
it with `0x20`. Ready-counter, cached-counter, saturation, TMCC, MER and AGC
fixtures test algorithm behavior, not physical reception or register calibration.

Other identified operations are:

| Address | Effect observed in original-instruction replay |
| --- | --- |
| `0x23192c` | Read/modify `0xeb` bit 1 for selector `0x20`, or `0x1e` bits 5:4 for `0x30`; set automatic-control state |
| `0x233528` | Poll `0x80` bit 3 once if clear or up to ten times if set |
| `0x230dd8` | Set `0x60`/`0x77` bit 0; select `0x76` bits 6:4 as `011` |
| `0x230e90` | Set `0x60` bit 0 and `0x77` bits 1:0; select `0x76` bits 6:4 as `011`/`001` using global `0x806ede`, then write its bit 0 and zero |
| `0x230fd8` | Write `0x5c=0`, read it and OR `0x70` before writing back |

The final direct-read sites at `0x231990`, `0x2319d0`, `0x23359c` belong to the
first two helpers. Together, local argument analysis and specified ARM replays
provide length-one evidence for all 65 identified direct read sites. This is
input-dependent coverage, not proof about every indirect call or undocumented
silicon mode. The status replay covers 40 synthetic cases and 43 distinct read
sites; post-tune replay covers 24 cases and the final-site replay 18 cases.
The simple local argument scan is weaker evidence than executed instructions.

## Demodulator lineage and calibration fingerprint

Selector `0x30` resembles the terrestrial register organization in pinned Linux
`tc90522.c`: FE forwarding, reset `01=40`, B0/B2-B4 fields, 8B measurement and 9D
counting. All 29 Sony calibration nodes for nominal 2..30 dB match the upstream
comment equation within `0.000246727519 dB`. That is a strong lineage lead,
not identification of a later TC90522 in this player.

| Input word | Nominal node | Comment equation, dB | Sony ARM at input | Sony ARM at input minus one |
| ---: | ---: | ---: | ---: | ---: |
| 9778432 | 2 | 1.999999895 | 0.0 | 2.0 |
| 5735416 | 3 | 2.999999752 | 2.9 | 3.0 |
| 3903295 | 4 | 4.000000023 | 3.9 | 4.0 |
| 737184 | 10 | 10.000003354 | 9.9 | 10.0 |
| 70125 | 20 | 20.000025311 | 19.9 | 20.0 |
| 7573 | 30 | 30.000206947 | 29.9 | 30.0 |

Sony uses strict thresholds and clipped fractional digits. Upstream integer
code differs from its comment through fixed-point log/rounding, `43827/80`
rather than `549.1`, and unsigned intermediates. It yields 3.997/9.988/19.968/
29.952 dB at the 4/10/20/30 nodes; the 2/3-node intermediates wrap. These
synthetic inputs neither calibrate the board nor establish a physical fault.
Sony labels the diagnostic MER; upstream calls its quantity CNR. They are not
independently established as the same RF measurement.

Sony reads these registers one byte at a time, while upstream can read a
six-byte TMCC block covering more layers. Sony also adds trailing FE forwarding.
The implementations are not bit-identical. Selector `0x20` instead has
mb86a20s-like reset `0x70`, indirect `04/05`, TMCC `6d/6e` and `64..66` counts;
features from one branch must not be assigned to the other.

Pinned `tc90522.c` lacks full chip initialization. PT3 gets pretranslated init
from board ROM. PT1's VA1J5JF8007T 20/25 MHz arrays are board configurations,
not X1060 identities: the 25 MHz array shares `75=0a` but differs at `1c/1d/1e`
and `76`. Friio's 36-write terrestrial sequence shares only sparse pairs
`01=40`, `38=01`, `71=00`. The inspected PX-BCUD/em28xx route is satellite and
must not be substituted as terrestrial initialization.

## Kernel transport and HAL policy

`dtv.ko` is MP200 transport/DMA code. It performs no observed OFDM/FEC decode,
TS sync-byte scan, PID selection or software CRC filtering in the examined
read path. It waits for complete ring clusters and requires iunit times packet
size alignment. DMA/FIFO/ring errors stop transfer.

Defaults are mode 1, buffer 15,040 bytes, debug 0. Stock iunit 20 with 188-byte
packets gives four 3,760-byte clusters. Packet selector 204 with iunit 20 fails
the four-cluster capacity requirement; iunit 18 fits a synthetic ioctl test.
This does not establish a physical 204-byte output or usable parity bytes.

The normal HAL configures reset, interrupt unit 20, serial input 1, packet-size
selector 0 (188 bytes) and byte-order selector 1 (driver little order). The
ioctls also expose serial/parallel choice and DMA lifecycle, not an identified
ADC/IQ selector. Kernel replay copies arbitrary and zero/non-`0x47` bytes,
including wrap/error cases; that proves copying only, not hardware framing.

Factory reader `0xd6730` requires active state, state 5 and a fresh roughly
100 ms status window. Its lower helper select/reads 3,760 bytes and its upper
cache splits them into 188-byte units. A first byte other than `0x47` returns
`0x80000000` and resets the cache index. A failed read can invoke a reset helper.
This HAL is therefore not a passive arbitrary-byte capture interface.

Opening `/dev/dtv` itself can mute external audio, enable regulators, change
pinmux/clocks and allocate DMA. An O_RDONLY open is not a harmless query.

## Factory interfaces that do not establish raw samples

| Interface | Resolved behavior |
| --- | --- |
| IntTestOptionTunerImpl / `0xd58dc` | Copy an eight-byte option pair, seed a software RNG and optionally convert successful reads to synthetic failures using a probability threshold |
| Stream helper `0xd8904` | Selector `0x30`: `0x1d=0` enables, `0xaa` disables; selector `0x20`: indirect `50/51` index `d7` changes low output-control bits |
| SMPL producer `0x3cad8` | Signed input byte +0x18 becomes output +0x1c equal to 1 only for input exactly 1; other tested values become 0 |
| SMPL display `0x151fc` | Object +0x18 supplies STATE, +0x1c supplies SMPL to format at `0x254b64`; these are displayed integers |
| `/dev/mem` sites `0x19caa8`, `0x1a8088` | Map physical `0x33a5d000`, length `0x1000`, protection 3 / flags 1: documented OMF acoustic parameters |
| `/dev/mp200_ad` | Power-control auxiliary ADC ioctls returning eight-bit conversions as ints; no read stream or continuous DMA API |

The SMPL producer constructs object `0xad6b48` and event `0x06000001`.
Callback `0x13814` checks that event and stores its payload through global
`0x2ebb2c`; display code uses pointer literal `0x14bb8`. The producer's Boolean
normalization is replayed; complete event delivery remains a static trace.
SMPL is not an established sample array, rate or sampling control.

GPL `mp201_mem.h` defines `OMF_MC_SDRAM_BASE=0x33970000`, acoustic parameter
offset `0x000ed000` and size `0x1000`, matching both mmap sites. Header SHA-256:
`819a28cad1f14a87fe663d0fe5650f3f3a98f422baa8124512f2c921058b106c`.
The success path at `0x19ca9c` opens with flags `0x1002`, maps read/write shared
memory and closes the fd. It is not an identified DTV sample buffer.

GPL `mp200_ad.c` exposes open/release/eight ioctls. Conversion uses
`GPIOCORE_PWC_ADMODE`, waits for interrupt, masks `GPIOCORE_PWC_ADDATA1+channel*2`
to eight bits, and supports accessory/power sensing. A helper's 800 us delay is
not a hardware maximum sample-rate specification. No RF connection is established.

## Code reuse and analysis limits

The four known bus helpers have 244 aligned ARM B/BL references in SpiderApp:
5 indexed writes, 4 forwarded writes, 170 register writes and 65 reads, all
inside `0x230000..0x233fff`. Factory references match after offset `0x158f40`;
Responder references match after `0xe5570`, including branch conditions/link
flags. Factory configuration blobs and all 29 calibration words also match.
This establishes the specified direct-reference sets, not every indirect path
or full HAL equivalence.

REA numeric queries can fall back to file offsets and return unrelated code.
Use explicit ARM virtual addresses, independent disassembly and analysis-only
symbols whose allocated sections/addresses/BSS remain unchanged. A function
name or factory string alone is not capability evidence.

## Identification and further work

TC90514/22/27/32 remain distinct comparison products. Toshiba's same-era
TC90541 announcement describes a 36 MHz, WCSP60 low-IF tuner/ADC/OFDM/FEC
receiver with I2C and TS output; it does not identify this board or expose a
raw-sample command. Its integrated architecture also prevents assuming a
physically accessible tuner-to-demodulator IF solely from forwarded controls.
The tentative TC90517FG excerpt in a Skyworth service manual documents IQ
inputs and TS outputs, not an ADC sampling output; its factory-test ties are
not wiring instructions for a Sony board.

New demodulation requires verified silicon identity/documentation and a real
raw/test/FEC-bypass output with compatible SoC framing. The existing kernel
copy path can carry bytes only after such an upstream output is established.
OMF `dtv/*.mp201` AAC/H.264/power-save components are not evidence of RF
demodulator microcode or arbitrary waveform programmability.

## Sources and reusable evidence

- [Pinned Linux terrestrial frontend comparison](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/c7decec2f2d2ab0366567f9e30c0e1418cece43f/drivers/media/dvb-frontends/tc90522.c).
- [Toshiba TC90541 announcement](https://www.global.toshiba/jp/news/corporate/2008/09/pr1701.html) and [technical review](https://www.global.toshiba/content/dam/toshiba/migration/corp/techReviewAssets/tech/review/2009/12/64_12pdf/f03.pdf).
- [Skyworth 8M79B comparison manual](https://www.manuallib.com/download/2023-11-07/%E5%88%9B%E7%BB%B4%E7%94%B5%E8%A7%868M79B%E5%BA%95%E7%9B%98%E7%BB%B4%E4%BF%AE%E6%89%8B%E5%86%8C.pdf): excerpt comparison only; no locally archived PDF hash is established.

| Ignored evidence directory | Content |
| --- | --- |
| `work/rf-rea-hal/` | Original initialization/status disassembly and instruction replay |
| `work/rf-driver-rea/` | Kernel read/ioctl replay with DMA/MMIO substituted |
| `work/rf-call-audit/` | Independent direct-reference sets, factory/Responder comparisons and read coverage |
| `work/rf-tuning-research/` | Status, initialization, all 50 channels, post-tune and final read-site fixtures |
| `work/rf-research/comparison/` | Pinned upstream sources, original nodes and comment/integer/ARM comparison |
| `work/rf-research/pt3/`, `tc90541/`, `memory-map/`, `adc/` | Initialization comparisons, manufacturer material, acoustic-map proof and auxiliary ADC sources |

Original-instruction replays substitute named bus, time, DMA or kernel effects.
Their reports are tied to input/source hashes and never qualify physical RF,
electrical pin behavior or an undocumented output mode. Private logs remain
ignored; current firmware acceptance belongs in [status](../STATUS.md).
