# Physical hardware and driver observations

Scope: one Japanese NW-X1060, observed through authenticated WiFi Terminal on
2026-10-27. Commands read standard proc/sysfs metadata, process mappings and
ordinary file checksums. They did not open raw partitions, issue hardware ioctls,
change NVP, switch routes or qualify reception/playback.

## Processor, memory and storage

The running kernel reports ARM926EJ-S, ARMv5TEJ, Hardware MP200. MemTotal is
45896 KiB with no swap. `/proc/iomem` lists normal System RAM at
0x30000000-0x32ffffff and a qfb reservation at 0x33000000-0x334fffff. This does not
independently determine the full physical RAM chip capacity.

| MTD | Purpose | Size |
| --- | --- | --- |
| 0 | Total NAND view | 32 GiB; do not add it to its subpartitions |
| 1 | RootFS | 148 MiB |
| 2 | Contents | 31023 MiB |
| 3 | Var | 4 MiB |
| 4 | Db | 210 MiB |
| 5 | EP0 | 3 MiB |
| 6-8 | EP1-EP3 | Zero; disabled/out-of-range in boot messages |

`/proc/mtd`, `/proc/partitions`, block-sector sizes and boot messages agree on
the relevant sizes. Root is ext2 read-only. User storage is vfat at `/contents`;
/var, /db and /ep0 are separate writable ext2 mounts. /tmp is ramfs, /dev devfs,
and /dev/pts devpts. The snapshot reported root filesystem total146784 KiB,
used110884 KiB and ordinary available28324 KiB. Do not reinterpret that as updater
or recovery qualification.

## Device interfaces

| Interface | Observation |
| --- | --- |
| `/dev/fb/0` | Character29:0, platform mp200_fb; terminal owns it while active |
| `/dev/icx_touch_screen` | Character238:0, I2C0-0020; terminal owns it |
| `/dev/input/event0` | Character13:64; physical-key stream |
| `/dev/v4l/radio0` | Character81:64, name Silicon Labs. FM Tuner |
| I2C0-0010 | Driver-provided name Si470x; probe/attach logged |
| I2C0-001e | Driver-provided name i2c R2A15602LG driver |
| `/dev/sound/mixer`, `dsp` | Character14:0 /14:3, stock OSS-style interfaces |
| `/dev/sound/icx_sound_smas` | Character239:0, Sony-specific sound interface |
| `/dev/ptmx` | Character5:2; real interactive terminal works |
| USB | S1R72V17 module; boot log Chip Rev0x0008 |

ALSA reports no soundcards and no PCM devices in this state, with only a timer
entry. Do not assume a modern default ALSA playback device. OSS/custom nodes and
the codec binding are not proof that every audio route is working.

## Display and touch protocol evidence

Offline original-code analysis establishes FBIOGET_FSCREENINFO0x4602 and
FBIOGET_VSCREENINFO0x4600, plus Sony queue/ready requests in shared adapters.
The current adapter requires 240x432, stride480, 16-bit RGB565 with the verified
two-page mapping. The initial simple size formula and original screenshot tool's
larger mapping describe different uses, not interchangeable initialization.

Touch NORMAL_MODE0x5404 changes state. GETVAL0x80045401 actually copies11 bytes,
despite the encoded pointer-size field. Coordinates are big-endian13-bit values:
x=raw_x*240/2929, y=431-raw_y*432/5281 with the original saturation rule. These
are screen coordinates; Sony's view transforms/hit testing are separate.

The terminal has physically displayed and accepted navigation, but this is not
universal display restoration or multi-touch qualification.

## USB and Wi-Fi

Live g_nwm parameters: mode1 (MSC), product921 (0x0399), iserial_len1;
g_nwm_msc backend `/dev/mtdblock/2`, removableY. The older kernel does not export
modern `/sys/class/usb_gadget`; missing that path does not mean missing Gadget.

USB connection requests: 0x80046701 reads state, 0x40046702 allows access,
0x40046703 prohibits it. Prohibition may mask the observed state as disconnected.
Therefore a zero query is not proof that no USB host owns storage.

Wi-Fi's interface is eth0, not wlan0. Its observed carrier, route and DNS worked;
a public u.y.qq.com ICMP response was received. This is not QQ HTTPS/account
validation. libcnmgr and its daemon match the analyzed stock files, but helper
ownership/cancellation and cold connection still need device tests.

## Process and component correspondence

The live manager/proxy/launcher/terminal chain used UID/GID0. The terminal's parent
was the launcher. At the captured instant the launcher had no fb/touch descriptor;
the terminal held both. A snapshot does not qualify every stop/USB/sleep path.

Ten ordinary executables/libraries/modules matched stock MD5: sysmgrd, appproxy,
libc, loader, Si470x, codec, touch, USB controller, g_nwm and g_nwm_msc. The matching
stock archive has a pinned SHA-256. MD5 here is non-adversarial version
correspondence, not a whole-device integrity certificate.

## Still unknown

- Exact FM silicon subtype/revision: no DEVICEID/CHIPID register read yet.
- Extended-band RF reception, sound, route restoration and antenna behavior.
- Full physical RAM arrangement and unlisted hardware capabilities.
- USB mode switching, all display/audio handoffs, suspend/wake and recovery.
- Performance and memory peaks of QQ conversion on this physical player.

Private raw observations remain in ignored work/terminal-live. Durable findings
are here; device identifiers, connection secrets and account traces are not.
