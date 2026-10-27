"""Build local external-store candidate only; never run native mode or flash."""
from pathlib import Path
import gzip,hashlib,io,json,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-app-candidate';work.mkdir(exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();candidate=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',candidate/'manifest.json']+[candidate/f['path'] for f in json.loads((candidate/'manifest.json').read_text())['files']]
def snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=snapshot()
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','tools/test_store_main.c','-o',str(work/'entry-test')],cwd=ROOT,check=True)
entry_test=subprocess.run([str(work/'entry-test')],capture_output=True,text=True,timeout=10)
assert entry_test.returncode==0,(entry_test.returncode,entry_test.stderr)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
modules=['install_posix','transaction','stage_posix','cleanup_posix','pending_plan','cleanup_plan','bundle_posix','inventory','package','stock_fs_bridge','stock_stat64','session','session_local','view','canvas','ui_loop','catalog_posix','catalog_view','catalog_loop','browser','termination','app','platform_native','main','start']
sources=['runtime/store/'+name+'.c' for name in modules]+['runtime/store/start.S','runtime/native/frontend.c','runtime/native/sha256.c','runtime/native/syscalls.S']
folder=work/'HOMEBREW/apps/store';folder.mkdir(parents=True,exist_ok=True);out=folder/'app'
flags=['-DHB_BUILD_VERSION="'+version+'"','-DHB_STORE_SONY_LIBC','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(out)],cwd=ROOT,check=True)
binary=out.read_bytes();elf=ELFFile(io.BytesIO(binary));needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
assert needed==['libc.so.6']
checks=[]
for args,code,expected in [(['--help'],0,'X1000 local package store'),(['--version'],0,version),([],64,'')]:
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),*args],capture_output=True,text=True,timeout=15)
 assert run.returncode==code and (not expected or expected in run.stdout),(args,run.returncode,run.stdout,run.stderr)
 assert '/dev/fb/' not in run.stderr and '/dev/icx_touch_screen' not in run.stderr
 checks.append({'args':args,'exit':run.returncode,'device_paths_not_accessed':True})
manifest=f'api=1\nid=store\nname=Local Store\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(binary)}\nsha256={hashlib.sha256(binary).hexdigest()}\n'
(folder/'app.ini').write_text(manifest)
assert before==snapshot()
report={'version':version,'artifact':str(out.relative_to(ROOT)),'bytes':len(binary),'sha256':hashlib.sha256(binary).hexdigest(),'needed':needed,'read_only_QEMU_entry_checks':checks,'candidate_unchanged':True,'physical_device_access':False,'native_ready':False,'firmware_package_created':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Native mode is built but never executed by this tool.','External local-package prototype, not a release or hardware qualification.','No network downloads, self-update protocol or USB qualification.']}
(ROOT/'sources/native-store-app-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('version','artifact','bytes','sha256','candidate_unchanged','native_ready')},indent=2))
