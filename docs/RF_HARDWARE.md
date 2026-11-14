# RF hardware and supported interfaces

This reference covers the Japanese NW-X1050/NW-X1060 on Sony 1.11. Device
identity, a standard's modulation list and a programmable sample interface are
separate facts. Current firmware and hardware acceptance belong in
[status](STATUS.md).

## Hardware summary

| Path | Established identity/interface | Limits |
| --- | --- | --- |
| FM | I2C `0-0010` named Si470x; `icx_si470x_radio_tuner.ko`; `/dev/v4l/radio0` named Silicon Labs FM Tuner | Family identified; subtype, stepping and RDS capability unresolved |
| 1seg | MP200 DTV FIFO/DMA through `dtv.ko` and `/dev/dtv`; userspace I2C HAL in SpiderApp, mptapp and Responder | Commercial tuner/demodulator unidentified; ordinary output is transport-stream packets |
| Wi-Fi | Marvell 88W8686-family path, original `sd8686.ko` and radio firmware | X1000 is a b/g product; exact package/front-end options and 5 GHz operation are not established |

The [DTV HAL reference](reference/DTV_HAL.md) records the original inputs,
register/control paths, calibration comparisons and rejected raw-sample leads.
The [SD8686 reference](reference/SD8686.md) records command, memory, filter,
security and ownership bindings. These are private implementation references;
ordinary apps use [SDK services](sdk/SERVICES.md).

## FM

The Si470x broadcast-receiver architecture supports investigation of 76–108 MHz,
mono/stereo, 50/75 us de-emphasis and 50/100/200 kHz channel spacing. Spacing is
not IF bandwidth. The maintained [Pocket FM app](apps/FM_RADIO.md) implements a
76–108 MHz adapter, bounded tuning/search and original audio-state restoration;
full board reception/audio acceptance remains separate.

The family observation does not identify Si4703 or establish RDS. Si4702/03 and
older Si4700/01 names must not be conflated, and later C19 documentation does
not prove the revision in a 2009 player. Si473x multi-band and Si471x transmitter
features cannot be assigned to Si470x. `R2A15602LG` is an audio-driver identity,
not the FM RF identity.

No AM/LW/MW/SW/SSB/CW, airband AM, general narrowband-FM scanner, arbitrary FSK
or FM-transmit path is established. Internal I/Q blocks do not imply a host I/Q
interface. The exposed software controls tuning/status and audio routing.
See the [stock FM driver reconstruction](FM_DRIVER_REVERSE_ENGINEERING.md).

## 1seg

The normal path configures serial 188-byte MPEG transport packets. ISDB-T's
segmented OFDM defines DQPSK/QPSK/16QAM/64QAM, but this is a standard-level list,
not this board's per-chip capability matrix. 1seg reception does not
establish full 13-segment TV, DVB-T/T2, DTMB, CMMB, ATSC or DAB. Similar QPSK/OFDM
alone is insufficient because synchronization, framing, FEC and bandwidth differ.

Stock diagnostics expose TMCC, BER/PER/MER, mode, guard, modulation, code rate,
interleave and segment information. Several status paths also write registers.
Neither their names nor a read-only device open makes them passive probes.

The following investigated leads do not establish sample export:

- Factory SMPL is a normalized Boolean displayed beside STATE, not a sample array.
- The known `/dev/mem` mapping is OMF acoustic-parameter memory.
- `/dev/mp200_ad` is a power/accessory ADC ioctl path, not continuous RF sampling.
- The DTV kernel can copy synthetic non-TS bytes, but this does not establish an
  upstream ADC/IQ source; the normal HAL additionally checks TS synchronization.
- OMF `dtv/*.mp201` AAC/H.264/power-save components are not identified RF microcode.

New demodulation needs verified silicon identity and a documented raw/test or
FEC-bypass output with compatible capture framing. Register similarity to
Toshiba/Fujitsu products is useful lineage evidence, not permission to apply
another chip's initialization or guessed test modes. Details and source pins
are in the [DTV reference](reference/DTV_HAL.md).

## Wi-Fi

802.11b uses DBPSK at 1 Mbps, DQPSK at 2 Mbps and CCK at 5.5/11 Mbps.
802.11g OFDM uses BPSK/QPSK/16QAM/64QAM through 54 Mbps. These are Wi-Fi frame
PHY modes; no arbitrary waveform or raw-I/Q programming interface is established.
Family a/b/g announcements do not prove a populated 5 GHz path on Sony's board.
Bluetooth coexistence support also does not establish a Bluetooth radio.

The [ESP-NOW implementation](ESPNOW_IMPLEMENTATION.md) reuses the original Wi-Fi
PHY/management machinery with a bounded radio-firmware bridge. It does not turn
the chip into a general SDR. The full endpoint is distinct from the older fixed
32-byte mailbox and its poll-driven chat protocol. No router association is
required, but the peers must use the same actual channel.

Recorded bounded experiments established plaintext and encrypted nonempty
payloads through 1,470 bytes, reverse encrypted traffic and selected replay/
wrong-key refusals. Those experiments and the Settings-managed Core2 composition
have different identities and qualification scopes. Read
[the physical exchange reference](reference/STOCK_WIRELESS.md#recorded-physical-exchange-scope)
and [current status](STATUS.md); automatic category-255 replies, MAC completion
and application delivery are not equivalent results.

## Interface and evidence rules

Opening `/dev/dtv` can mute audio, power regulators and allocate DMA. A GET can
initialize hardware or report only cached state. Driver names, partial code
fingerprints, matching files, seeded register replay and QEMU are different
kinds of evidence. No raw register write, test-pin activation, system remount or
new physical RF operation is authorized by reading a reference.

Original Sony files, private captures, keys and device reports remain ignored.
Maintainable source and provenance live in the repository; use the matching
input hashes and scope in each technical reference rather than treating a
recorded experiment as qualification of every later build.

## Primary sources

- [Sony GPL catalog](https://oss.sony.net/Products/Linux/Audio/NW-X1050.html), with local archive provenance in `sources/kernel-download.json`.
- [Skyworks product-function matrix AN332](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN332.pdf) and [Si4702/03 programming guide AN230](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/application-notes/AN230.pdf).
- [ARIB STD-B31](https://www.arib.or.jp/english/html/overview/doc/6-STD-B31v1_6-E2.pdf): standard-level modulation, not board identity.
- [Marvell 88W8686 family announcement](https://www.marvell.com/company/newsroom/marvell-introduces-worlds-first-ultra-low-power-90nm-wlan-single-chip-solution.html).
- [Manufacturer-submitted module description](https://fccid.io/OMC287380/Operational-Description/Operating-Description-1228683.pdf): PHY comparison, not identification of Sony's module.
