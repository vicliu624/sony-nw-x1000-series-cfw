# NW-X1000 platform knowledge

This is the durable handoff for Japanese NW-X1050/NW-X1060. Read STATUS.md and
HARDWARE.md alongside it. Other Sony families and international NWZ-X images are
comparison inputs, not compatibility guarantees.

## Firmware identity

- NW-X1000_V1_11.exe: 46849232 bytes; SHA-256
  25c8290dbac1065809f39332614491958ef7c93ce6e2e67e8cb5f815009a5a81.
- UPG: 47001096 bytes; SHA-256
  002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b.
- Japanese DES-equivalent key 466c8cd0, marker daefe603, KAS
  695c6b954088447c718f0873b8354c8a. This weak-container key search is not a break of
  a modern public-key signature scheme.
- Components: installation script, kernel, initrd, gzip rootfs. Check marker,
  count, lengths and exact reconstructed bytes, not just tool exit status.
- Kernel SHA-256:
  6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645.
- Rootfs gzip SHA-256:
  c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5.

Official source catalog:
https://oss.sony.net/Products/Linux/Audio/NW-X1050.html. It explicitly includes
Japanese X1050/X1060. Provenance belongs in sources; proprietary inputs stay local.

## Boot and application management

Normal boot enters /etc/init.d/gemini, /usr/local/bin/sysmgr.sh, then
sysmgrd -r /usr/local/bin/moc_repairer.sh /etc/AppList.conf. Special ID1 is
SpiderApp and ID2 Responder. Class 0x0001xxxx denotes resident services,
0x0002xxxx common apps, and **0x0003xxxx proxy-routed apps**.

```text
0x00030001 * /contents/HOMEBREW/launcher/app --native
```

The third token is both executable and lookup name; remaining tokens are arguments.
Do not duplicate the executable in argv. The star follows manager credentials;
it does not create root permission. Root was observed through the current manager,
proxy, launcher and terminal configuration.

The original root child path sets GID, clears supplementary groups and sets UID
before exec. Known helpers: 0x15f14 and 0x15ed4. Modeled successful child paths do
not close inherited descriptors; manage ownership explicitly.

Home has conditional ten/nine-item maps. List modes and Home functional states
are different; numeric modes alone do not identify a model/region. APF slot4 /
0x420015 / command3 finalization differs from slot6 / 0x420024 / queued command6.
Activation events 0x20303/0x580101 synchronize battery state, not display ownership.
APF operation8 queries USB; operation7 is battery-related. Preserve original
asynchronous coordination rather than replacing it with a fixed delay.

## ABI and libc

Kernel: 2.6.10_dev-mp201, ARM926EJ-S/ARMv5TEJ, MontaVista GCC3.4.3 lineage.
Direct ARM syscalls require the verified OABI SWI immediate convention. Modern
r7+svc0 and ELF flags alone do not establish compatibility.

Native app builders use original libc startup and /lib/ld-linux.so.3. Pinned
SHA-256 inputs:

| File | SHA-256 |
| --- | --- |
| libc.so.6 | 5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812 |
| ld-linux.so.3 | 2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de |

They resolve to libc-2.3.3.so and ld-2.3.3.so. Stock pthread is LinuxThreads;
repeated task RSS is not independent physical memory.

Modern headers may redirect ioctl, fcntl, time and socket functions to absent
time64/C23 symbols. Use narrow existing bindings, not incompatible aliases.
runtime/store/target_abi.h and the stat bridge decode original 96-byte stat data;
do not give it a modern struct stat. Preserve legacy signal-return conventions.

## Storage, installation and recovery

Live root is mtdblock/1, ext2 read-only. mtdblock/2 is vfat read-write at /contents.
/var, /db and /ep0 are separate partitions; /tmp is RAM-backed. Root partition
capacity is established on this device, not as a universal installation guarantee.

The original updater formats root before unpacking. It has no automatic rollback
to the previous rootfs. Its visible-storage free-space check does not establish
expanded rootfs fit. Recovery remains a separate unresolved guarantee. Do not
infer safe flashing, bootloader commands, pads or shorts from software extraction.

An app must validate the mounted user device, directory identity, symlinks, free
space and USB ownership. A path or flock alone does not exclude a USB host.
Stock library databases can involve /db; audit destinations before refresh.

## Hardware and network boundaries

See HARDWARE.md for actual nodes and bindings. Opening a read-only device can
initialize hardware: radio open is one example. A GET name is not a side-effect
audit. Driver names do not independently identify precise silicon revisions.

Wi-Fi uses eth0, with original route/DNS configuration. /etc/resolv.conf points to
/tmp/resolv.conf. Original firewall policy is INPUT DROP, OUTPUT ACCEPT, with
loopback/ICMP and ESTABLISHED/RELATED exceptions. Only the inbound terminal needs
a temporary TCP2323 accept rule; outbound QQ HTTPS does not.

The observed 2008 device date matters for ordinary TLS and QQ timestamps. Terminal
pin validation is different from public CA/date validation; do not disable checks.

## Evidence discipline

Instruction replay can verify a wrapper with hardware/services still simulated.
QEMU user/system tests, local TLS servers, file readback and physical RF/audio
tests establish different things. Bind results to exact inputs and artifacts.
Superseded detailed notes live in ignored .tmp/history/docs; generated evidence
stays local. Active documentation records durable facts and outstanding questions.
