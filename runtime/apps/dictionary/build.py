"""Build the external offline dictionary, pinned stock libc; PC only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from pathlib import Path
import subprocess,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[3];w=ROOT/'work/dictionary-app';folder=w/'package';folder.mkdir(parents=True,exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';version=(ROOT/'runtime/apps/dictionary/VERSION').read_text().strip()
import sys
subprocess.run([sys.executable,str(ROOT/'tools/build_dictionary_data.py')],cwd=ROOT,check=True)
for n,h in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/n).read_bytes()).hexdigest()==h
sources=['runtime/apps/dictionary/app.c','runtime/apps/dictionary/dictionary.c','runtime/apps/dictionary/input.c','runtime/apps/dictionary/ui.c','runtime/apps/emulators/platform.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
flags=['-std=c99','-O2','-Wall','-Wextra','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffunction-sections','-fdata-sections','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-D_FILE_OFFSET_BITS=64','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_USE_POSIX_FILES']
objects=[]
for i,source in enumerate(sources):
 obj=w/(str(i)+'-'+Path(source).stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
app=folder/'app';subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
checks=[]
for args in [['--help'],['--lookup',str(ROOT/'work/dictionary-data/lexicon.dic'),'hello'],['--lookup',str(ROOT/'work/dictionary-data/lexicon.dic'),'DICTIONARY']]:
 r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),*args],capture_output=True,text=True,timeout=20);assert r.returncode==0,(args,r.stdout,r.stderr);checks.append({'args':args,'stdout':r.stdout,'exit':r.returncode})
(folder/'assets').mkdir(exist_ok=True)
for n in ['lexicon.dic','font.bin']:shutil.copyfile(ROOT/'work/dictionary-data'/n,folder/'assets'/n)
digest=hashlib.sha256(app.read_bytes()).hexdigest();(folder/'app.ini').write_text(f'api=1\nid=dictionary\nname=English Chinese Dictionary\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={app.stat().st_size}\nsha256={digest}\n')
(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.relative_to(folder).as_posix()}\n'for p in sorted(folder.rglob('*'))if p.is_file()and p.name!='files.sha256'))
report={'app_version':version,'sha256':digest,'bytes':app.stat().st_size,'checks':checks,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [*[ROOT/s for s in sources],*list((ROOT/'runtime/apps/dictionary').glob('*.h')),ROOT/'runtime/apps/dictionary/VERSION',Path(__file__)]},'assets':json.loads((ROOT/'work/dictionary-data/report.json').read_text()),'device_writes':False,'firmware_created':False,'hardware_tested':False}
(w/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('Dictionary ARM binary',report['bytes'],digest)
