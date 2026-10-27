"""Check stock-libc directory/seek backend against real ARM file operations."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/libc-file-backend-review';work.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
files=['runtime/native/linux_file_ops_posix.c','tools/fixtures/libc_files.c','runtime/store/start.c','runtime/store/start.S'];artifact=work/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_FILES','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*files,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=work) as temporary:
 area=Path(temporary);(area/'payload').write_bytes(b'HELLO');(area/('a'*32)).mkdir();(area/('b'*33)).mkdir()
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(area),str(area/'payload'),str(area/'missing')],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert run.returncode==0,(run.returncode,run.stderr[-10000:]);assert (area/'payload').read_bytes()==b'HELLO'
tracked=[ROOT/f for f in files]+[Path(__file__),ROOT/'runtime/native/linux_files.h',lib/'libc.so.6',lib/'ld-linux.so.3']
report={'passed':True,'artifact':str(artifact.relative_to(ROOT)),'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'checks':['read payload','64-bit llseek offset0x200000011 and return match without writes','seek_end returns5','bad fd EBADF','32-character name retained, 33-character ignored','stop before open and during scan','missing directory and repeated close'],'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['Stock libc under QEMU on host filesystem, not Sony FAT.','llseek exported legacy ABI tested explicitly; unavailable lseek64 not aliased.','No launcher UI/child lifecycle for this new backend yet.']}
(ROOT/'sources/native-libc-file-backend-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock-libc files: real 64-bit seek, directory boundaries, stop and close passed.')
