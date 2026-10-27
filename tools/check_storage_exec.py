"""Read-only audit of pinned startup mount commands and published FAT/exec source.

Scripts are data only. This does not mount anything or execute Sony utilities.
"""
from pathlib import Path
import hashlib
import io
import json
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
rootfs = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(rootfs).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
kernel_source = (ROOT / 'work/downloads/linux-kernel-2.6.10.local.tgz').read_bytes()
assert hashlib.sha256(kernel_source).hexdigest() == '286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
with tarfile.open(fileobj=io.BytesIO(rootfs), mode='r:gz') as archive:
    raw = archive.extractfile('./etc/init.d/gemini').read()
    script = raw.decode()
    body = re.search(r'run_command\(\)\s*\{(.*?)\n\}', script, re.S).group(1)
    mount = next(line.strip() for line in body.splitlines() if line.strip().startswith('mount '))
    options = re.search(r' -o ([^ ]+)', mount).group(1).split(',')
    assert options == ['iocharset=utf8', 'shortname=winnt', 'dmask=0000', 'fmask=0000']
    assert mount.endswith('-t vfat /dev/mtdblock/2 /contents')
    assert body.index(mount) < body.index('/usr/local/bin/watchman')
    assert 'noexec' not in options and 'showexec' not in options
    mtp = archive.extractfile('./etc/init.d/mtp').read()
with tarfile.open(fileobj=io.BytesIO(kernel_source), mode='r:gz') as archive:
    fat = archive.extractfile('./fs/fat/inode.c').read()
    execute = archive.extractfile('./fs/exec.c').read()
    assert b'opts->quiet = opts->showexec = opts->sys_immutable = opts->dotsOK =  0;' in fat
    assert b'sbi->options.showexec' in fat and b'S_IRWXUGO' in fat
    assert b'& ~sbi->options.fs_fmask) | S_IFREG' in fat
    assert b'!(nd.mnt->mnt_flags & MNT_NOEXEC)' in execute
result = {
    'scope': 'Pinned script/source inspection only; no shell, mount or physical device execution',
    'rootfs_sha256': hashlib.sha256(rootfs).hexdigest(),
    'startup_script_sha256': hashlib.sha256(raw).hexdigest(),
    'normal_mount_command': mount, 'options': options,
    'mount_precedes_watchman_sysmgr': True,
    'source_fat_showexec_default': False,
    'source_regular_file_mode': 'S_IRWXUGO unless showexec extension restriction, masked by fs_fmask',
    'source_exec_checks': ['MNT_NOEXEC', 'regular file', 'MAY_EXEC permissions'],
    'source_hashes': {'fat_inode': hashlib.sha256(fat).hexdigest(),
                      'exec': hashlib.sha256(execute).hexdigest(),
                      'mtp_script': hashlib.sha256(mtp).hexdigest()},
    'conclusion': 'No noexec/showexec restriction is requested by the normal startup command; no remount or system/RAM copy is justified by this evidence alone.',
    'limits': ['Actual mount flags and later Responder remounts are not device-verified.',
               'FAT source behavior is supporting evidence, not complete compiled driver replay.',
               'File availability, full ELF load, APF activation, USB/sleep and application behavior remain separate gates.'],
}
(ROOT / 'sources/native-storage-exec.json').write_text(json.dumps(result, indent=2) + '\n')
print('Stock startup mount requests executable mode bits; no mount options or scripts changed')
