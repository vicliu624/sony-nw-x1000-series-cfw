"""Build external C TXT reader against pinned original Sony libc, PC only."""
from pathlib import Path
import subprocess,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-app';folder=w/'package';folder.mkdir(parents=True,exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';version=(ROOT/'runtime/apps/ebook/VERSION').read_text().strip()
for n,h in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/n).read_bytes()).hexdigest()==h
sources=['runtime/apps/ebook/app.c','runtime/apps/ebook/reader.c','runtime/apps/ebook/storage.c','runtime/apps/ebook/ui.c','runtime/apps/dictionary/dictionary.c','runtime/apps/emulators/platform.c','runtime/native/frontend.c','runtime/native/sha256.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
epub_sources=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'runtime/apps/ebook/epub').glob('*.c'))]+['third_party/epub-miniz/miniz_tinfl.c']
sources+=epub_sources
flags=['-std=c99','-O2','-DMINIZ_NO_STDIO','-DMINIZ_NO_TIME','-DMINIZ_NO_ARCHIVE_APIS','-DMINIZ_NO_DEFLATE_APIS','-Wall','-Wextra','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffunction-sections','-fdata-sections','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-D_FILE_OFFSET_BITS=64','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_USE_POSIX_FILES','-DER_APP_VERSION="'+version+'"']
objects=[]
for i,source in enumerate(sources):
 obj=w/(str(i)+'-'+Path(source).stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
app=folder/'app';subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
checks=[]
for args in [['--help'],['--version']]:
 r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),*args],capture_output=True,text=True,timeout=20);assert r.returncode==0,(r.stdout,r.stderr);checks.append({'args':args,'stdout':r.stdout,'exit':r.returncode})
(folder/'assets').mkdir(exist_ok=True)
for src,name,h in [(ROOT/'work/ebook-data/font.bin','font.bin','05d7a20a4b3d3c8916d18b47bc5deba470fd9d29ea28d46fcab5acc9605c2924'),(ROOT/'work/ebook-data/gb18030.bin','gb18030.bin','cafe6c9007e4366c5d3a79ec351cf4872fc1913899760417dac2851dc6501f17')]:
 assert hashlib.sha256(src.read_bytes()).hexdigest()==h;shutil.copyfile(src,folder/'assets'/name)
digest=hashlib.sha256(app.read_bytes()).hexdigest();(folder/'app.ini').write_text(f'api=1\nid=ebook\nname=EBook Reader\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={app.stat().st_size}\nsha256={digest}\n');(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.relative_to(folder).as_posix()}\n'for p in sorted(folder.rglob('*'))if p.is_file()and p.name!='files.sha256'))
report={'app_version':version,'sha256':digest,'bytes':app.stat().st_size,'checks':checks,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [*[ROOT/s for s in sources],*list((ROOT/'runtime/apps/ebook').rglob('*.h')),*list((ROOT/'runtime/apps/ebook/epub').glob('*.inc')),*[p for d in ['epub-miniz','epub-stb'] for p in (ROOT/'third_party'/d).iterdir() if p.is_file()],ROOT/'runtime/apps/ebook/VERSION',Path(__file__)]},'device_written':False,'firmware_created':False,'hardware_tested':False};(w/'build.json').write_text(json.dumps(report,indent=2)+'\n');print('EBook ARM binary',report['bytes'],digest)
