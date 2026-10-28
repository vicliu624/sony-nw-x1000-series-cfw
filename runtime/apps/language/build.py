"""Build external Language with pinned Sony libc. PC only, no device access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from pathlib import Path
import subprocess,json,hashlib,io,zipfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[3];w=ROOT/'work/external-language-app-build';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';version=(ROOT/'runtime/apps/language/VERSION').read_text().strip()
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
sources=['runtime/apps/language/external_app.c','runtime/apps/language/catalog.c','runtime/apps/language/storage.c','runtime/apps/language/preference.c','runtime/apps/language/package.c','runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/start.c','runtime/store/start.S']
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-D_FILE_OFFSET_BITS=64','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_BUILD_VERSION="'+version+'"']
objects=[]
for i,source in enumerate(sources):
 obj=w/(str(i)+'-'+Path(source).stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
folder=w/'HOMEBREW/apps/language';folder.mkdir(parents=True,exist_ok=True);app=folder/'app'
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
data=app.read_bytes();elf=ELFFile(io.BytesIO(data));needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED'];assert needed==['libc.so.6']
checks=[]
for args in [['--selftest'],['--help'],['--version']]:
 r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),*args],capture_output=True,text=True,timeout=15);assert r.returncode==0,(args,r.stdout,r.stderr);checks.append({'args':args,'exit':r.returncode,'stdout':r.stdout})
digest=hashlib.sha256(data).hexdigest();(folder/'app.ini').write_text('api=1\nid=language\nname=Language\nversion='+version+'\ntarget=sony-nw-x1000-jp\nexec=app\nbytes='+str(len(data))+'\nsha256='+digest+'\n')
(folder/'files.sha256').write_text('HBFILES1\n'+''.join(hashlib.sha256(p.read_bytes()).hexdigest()+' '+str(p.stat().st_size)+' '+p.name+'\n' for p in sorted([app,folder/'app.ini'])))
report={'passed':True,'version':version,'artifact':str(app.relative_to(ROOT)),'bytes':len(data),'sha256':digest,'needed':needed,'checks':checks,'hardware_tested':False,'device_written':False,'firmware_created':False,'source_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources+['runtime/apps/language/preference.h','runtime/apps/language/storage.h','runtime/apps/language/package.h','runtime/apps/language/catalog.h','assets/language/required-ids.inc','assets/language/required-ids.json','assets/language/parameter-counts.inc','assets/language/parameter-counts.json','tools/build_external_language_app.py','runtime/apps/language/VERSION']}}
(w/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
