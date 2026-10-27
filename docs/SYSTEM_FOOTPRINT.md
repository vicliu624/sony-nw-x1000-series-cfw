# System footprint and slimming assessment

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
