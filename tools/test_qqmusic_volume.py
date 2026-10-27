"""Read-only volume observer: real fd/stat/space, synthetic mount/path mapping."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-volume';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('volume','storage','asset','source','output','directory','stage','stage_volume','protocol','session')]+['runtime/store/https_url.c','runtime/native/sha256.c','tools/fixtures/qqmusic_volume.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64']
host=work/'volume-tests.sanitized'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='host-',dir=work) as directory:
 subprocess.run([str(host),directory],cwd=ROOT,check=True);assert not list(Path(directory).iterdir())
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
arm=work/'volume-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='arm-',dir=work) as directory:
 process=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm),directory],cwd=ROOT,capture_output=True,text=True,timeout=15)
 (work/'observer.trace').write_text(process.stderr)
 assert process.returncode==0,(process.returncode,process.stderr[-5000:]);assert not list(Path(directory).iterdir())
report={'passed':True,'scope':'native_user_volume_observer_and_file_transactions','physical_device_tested':False,'synthetic_mount_and_path_mapping':True,'real_stat_metadata_and_space':True,
 'checks':['actual space overrides caller values','pinned workspace identity','directory replacement rejects recheck','readonly mount rejects','changing snapshots reject','symlink rejects','wrong source rejects','actual free space limit','observer and reader never open for write','asset exact bytes and digest','asset wrong digest and size reject','asset traversal and symlink reject','completed staged source actual hash before read','source random access larger than 4KiB and EOF','source stop and idempotent close','tampered source digest rejects and releases descriptors'],
 'output_checks':['exclusive MP3 temporary namespace','collision preserves existing output','byte count and actual readback hash','synced completion remains temporary','stop aborts owned output','readonly volume aborts owned output','completion length mismatch aborts'],
 'directory_checks':['UTF8 artist and album directories with spaces','existing directories reused with same inode','traversal rejected','filename identity mismatch rejected','symlink directory rejected without replacement'],
 'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['runtime/apps/qqmusic/qqmusic_'+n+'.h' for n in ('volume','source','output','directory','stage')]},
 'limits':['Kernel mount labels/path locations are translated by fixture; not actual Sony FAT qualification.','No reservation, publication or enabled application writes.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
