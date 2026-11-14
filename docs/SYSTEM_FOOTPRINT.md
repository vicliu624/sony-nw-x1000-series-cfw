# System footprint and slimming assessment

## Reviewed root layout model

The reviewed link-key/retirement layout adds **599,867 bytes of regular file
content** over Japanese Sony 1.11. In a complete ext2 allocation model, its
increment is **647,168 bytes (632 KiB)**. The latter includes directory, inode
and indirect-block allocation; compressed UPG size is a separate measurement.

| Ordinary 148 MiB model file | Original Sony root | Current analysis layout |
| --- | ---: | ---: |
| Allocated filesystem blocks, including metadata | 118,374,400 bytes | 119,021,568 bytes |
| Reserved space | 7,757,824 bytes | 7,757,824 bytes |
| Free space after reserved blocks | 29,057,024 bytes | 28,409,856 bytes (about 27.09 MiB) |
| Used inodes | 1,442 | 1,454 |

`tools/measure_layout_ext2.py` verifies the complete capacity/layout receipts,
original NAND partition definition, original formatter and its Sony library
closure. It formats new ordinary files with Sony's BusyBox under ARM user
emulation, populates the whole tree with host debugfs, allocates zero-filled
regular-file blocks and runs read-only e2fsck. It independently reads back every
regular file, inode mode/owner/mtime and symlink target. This model
verified 1,079 original and 1,089 candidate regular files. No image is mounted.
Reports, images, commands and hashes remain in ignored `work/`.

This is a reproducible PC capacity result, not a physical free-space measurement
or permission to flash. Host debugfs substitutes for Sony's kernel/tar extraction;
the static 148 MiB definition does not qualify actual NAND geometry, bad blocks,
installation, recovery or the outstanding lifecycle regressions. The current
layout is not an updater package. The model includes the opt-in link-key owner,
shared-retirement ordering fix and matching parent library. Further component
changes require a new complete review; component file size alone is insufficient.

## Physical measurements and slimming candidates

Read-only device measurements found a148MiB root partition, with ext2 filesystem
total146784KiB, used110884KiB and ordinary available28324KiB (about27.7MiB).
The system is read-only; this review did not delete, remount, stop or replace it.

| Area | Observed allocation | Assessment |
| --- | ---: | --- |
| /usr/local/share | 64.1MiB | Main resources/fonts; not disposable cache |
| /usr/local/bin | 24.0MiB | Sony applications and services |
| /usr/lib | 11.9MiB | Shared codecs, libraries and components |
| Factory mptapp assets | 8.54MiB | Candidate only if factory-test capability is deliberately changed |
| mptapp executable | 3.00MiB | Referenced by gemini's manufacturing-test branch |
| Browser + WBROWSER assets | 7.88MiB +12.73MiB | Feature loss; fonts also referenced by SpiderApp |
| genesys input dictionary | 11.12MiB | Responder reference; do not assume unused |
| Other dictionaries / Sony fonts | 7.24MiB /7.58MiB | Language/input/display dependencies |
| /usr/local/test | 0.86MiB | Cannot remove as a directory: active watchdog and Wi-Fi references |
| All /lib/modules | 2.2MiB | Unloaded now does not mean unused in maintenance/other paths |

Rows overlap and must not be summed. Core GUI resources, fonts and input behavior
remain part of the preserved Sony product.

On PC-only stock ELF copies, `strip --strip-debug` reduced37 of212 ELF files by
1931583 bytes (about1.84MiB). Every allocated section compared byte-identically.
The largest reduction was libcurl (1168604 bytes), followed by wpa_supplicant,
libcares, cnmgr_daemon and libexpat. The4KiB ordinary-data-block model saved1933312
bytes, excluding metadata/indirect-block changes. These are candidates, not a
device-qualified replacement image; keep symbols on the computer for research.

Important deletion traps:

- watchdog_test in the test directory is actually started and running.
- bomberman is a resident service, not an optional game identified by its name.
- Some dictionary .a files begin NJDC, not an ar static-library header.
- libcurl/libcares/libexpat/libcrypto have direct Sony manager/UI dependencies.
- Absent DT_NEEDED/path strings cannot exclude dlopen or constructed paths.

Deleting unused assets/debug data primarily saves disk, not equivalent resident
RAM. The player has about44.8MiB Linux-visible memory and no swap; cache is not
all unreclaimable and old task RSS cannot be blindly summed. QQ buffering/codec
peaks deserve measurement before attempts to disable watchdog/power services.

User storage, /db and root are separate partitions. Cleaning one does not grow
another. Reducing reserved blocks is not removal of redundancy. Core-resource
symlinks into user storage introduce boot/USB/sleep dependencies and are not a
safe automatic slimming method.

Tools: tools/review_system_footprint.py (explicit live read-only query) and
tools/analyze_rootfs_slimming.py (PC-only analysis). Private measurements remain
in ignored work directories. No slim firmware was produced or installed.
