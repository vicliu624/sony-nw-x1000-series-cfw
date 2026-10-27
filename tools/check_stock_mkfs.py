"""Run stock ARM mkfs on a NEW ordinary local image only; never an updater/device."""
from pathlib import Path
import hashlib,io,json,stat,struct,subprocess,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1]
measurement=json.loads((ROOT/'sources/native-local-ext2-measurement.json').read_text())
sysroot=(ROOT/measurement['experiment_directory']/'tree').resolve()
assert sysroot.is_relative_to((ROOT/'work').resolve())
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    original=tar.extractfile('./bin/busybox').read()
    assert (sysroot/'bin/busybox').read_bytes()==original
    for path in ('lib/ld-linux.so.3','lib/libc.so.6'):
        member=tar.getmember('./'+path)
        target=(Path(path).parent/member.linkname).as_posix() if member.issym() else path
        assert (sysroot/path).read_bytes()==tar.extractfile('./'+target).read()
area=Path(tempfile.mkdtemp(prefix='stock-mkfs-',dir=ROOT/'work')).resolve()
image=area/'empty-rootfs.img'
assert image.parent==area and image.is_absolute() and not image.exists()
with image.open('xb') as f:f.truncate(148*1048576)
assert stat.S_ISREG(image.stat().st_mode) and not image.is_symlink()
command=['qemu-arm','-cpu','arm926','-L',str(sysroot),str(sysroot/'bin/busybox'),'mke2fs','-F','-b','4096',str(image)]
result=subprocess.run(command,capture_output=True,text=True,input='',timeout=60)
(area/'mkfs.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stdout+result.stderr
with image.open('rb') as f:f.seek(1024);sb=f.read(1024)
assert struct.unpack_from('<H',sb,56)[0]==0xef53
inodes,blocks,reserved,free,free_inodes=struct.unpack_from('<5I',sb)
block_bytes=1024<<struct.unpack_from('<I',sb,24)[0]
inode_bytes=struct.unpack_from('<H',sb,88)[0]
features=struct.unpack_from('<3I',sb,92)
assert blocks*block_bytes==148*1048576 and block_bytes==4096
check=subprocess.run(['e2fsck','-f','-n',str(image)],capture_output=True,text=True,timeout=60)
(area/'fsck.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stdout+check.stderr
report={'scope':__doc__,'busybox_sha256':hashlib.sha256(original).hexdigest(),'tool_version':'mke2fs1.37 bundled in Sony BusyBox1.1.0',
        'command':command,'image':image.relative_to(ROOT).as_posix(),'image_bytes':image.stat().st_size,
        'block_bytes':block_bytes,'inode_bytes':inode_bytes,'inode_count':inodes,'block_count':blocks,
        'reserved_blocks':reserved,'free_blocks_after_format':free,'format_metadata_used_bytes':(blocks-free)*block_bytes,
        'available_nonreserved_after_format_bytes':(free-reserved)*block_bytes,'feature_words':features,
        'fsck_readonly_exit':check.returncode,'physical_device_access':False,'capacity_qualified':False,
        'limits':['New ordinary file under ignored work only; -F bypasses regular-file check, not device safety checks.',
                  'Uses stock executable/loader/libc in qemu-user but host kernel/filesystem; not physical MTD behavior.',
                  '148MiB from stock module definition, not actual-device measurement.',
                  'Image is empty after formatting; original tar extraction and candidate population not measured here.']}
(ROOT/'sources/native-stock-mkfs.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
