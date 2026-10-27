"""State transaction checks on ordinary work files; no player access."""
from pathlib import Path
import json,hashlib,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/fm-storage-tests';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
 assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/fm-radio/fm_radio.c','runtime/apps/fm-radio/fm_state.c','runtime/apps/fm-radio/fm_storage.c','runtime/apps/fm-radio/fm_storage_native.c','tools/fixtures/fm_storage.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
startup=['runtime/store/start.c','runtime/store/start.S']
flags=['-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wl,--wrap=write,--wrap=fsync']
arm=work/'storage-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,*bridge,*startup,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='arm-',dir=work) as directory:
 p=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm),directory],cwd=ROOT,capture_output=True,text=True,timeout=20)
 assert p.returncode==0,(p.returncode,p.stderr)
 assert not list(Path(directory).iterdir())
host=work/'storage-tests.sanitized'
subprocess.run(['gcc',*flags,'-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='host-',dir=work) as directory:
 subprocess.run([str(host),directory],cwd=ROOT,check=True,timeout=20)
 assert not list(Path(directory).iterdir())
report={'passed':True,'hardware_tested':False,'player_written':False,'checks':['Original libc ARM32 filesystem bridge with real PC file IO','Native host ASan/UBSan','Two slots and fallback from latest damaged state','Short-write/EINTR retry and write/fsync failures','Commit uncertainty after directory sync failure','Root-volume rejection and mount revalidation','Symlink refusal and orphan temporary recovery','Strict stock mount source/filesystem/read-write validation'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in core+bridge+startup+['runtime/apps/fm-radio/fm_state.h','runtime/apps/fm-radio/fm_storage.h','tools/test_fm_storage.py']},'limits':['PC user-volume directory, not Sony FAT or power-loss qualification.','Native mount acquisition is not executed; native parser and FD-bound writer are tested separately.','Exclusive application workspace, not malicious concurrent modification protection.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='sources'},indent=2))
