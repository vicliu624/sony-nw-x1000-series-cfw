"""Build/read-only QEMU-check a real C app; never deploy or access player."""
from pathlib import Path
import runpy,subprocess,hashlib,json,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/hello-app';work.mkdir(exist_ok=True);folder=work/'package';folder.mkdir(exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();runtime=metadata['work']
sources=['runtime/apps/hello/hello.c','runtime/store/start.c','runtime/store/start.S']
objects=[]
for i,source in enumerate(sources):
 target=work/f'{i:02d}-{Path(source).stem}.o';subprocess.run(['arm-linux-gnueabi-gcc','-DHB_BUILD_VERSION="'+version+'"','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-c',source,'-o',str(target)],cwd=ROOT,check=True);objects.append(str(target))
app=folder/'app';subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
data=app.read_bytes();elf=ELFFile(io.BytesIO(data));assert elf.header['e_machine']=='EM_ARM';needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED'];assert needed==['libc.so.6']
checks=[]
for args,code,expected in [([],0,'Hello from a native Sony NW-X1000'),(['--help'],0,'No device access'),(['--version'],0,version),(['unexpected'],64,'')]:
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(app),*args],capture_output=True,text=True,timeout=15);assert run.returncode==code and expected in run.stdout,(args,run.returncode,run.stderr)
 assert '/dev/fb/' not in run.stderr and '/dev/icx_touch_screen' not in run.stderr
 checks.append({'args':args,'exit':code,'stdout':run.stdout,'trace':run.stderr})
manifest=f'api=1\nid=hello\nname=Hello Walkman\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={hashlib.sha256(data).hexdigest()}\n'.encode();files={'app':data,'app.ini':manifest};index=b'HBFILES1\n'+b''.join(f'{hashlib.sha256(value).hexdigest()} {len(value)} {name}\n'.encode() for name,value in sorted(files.items()))
(folder/'app.ini').write_bytes(manifest);(folder/'files.sha256').write_bytes(index)
report={'all_bounded_checks_passed':True,'version':version,'artifact':str(app.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'needed':needed,'checks':checks,'physical_device_access':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Real ARM C program run under QEMU with pinned original libc, not physical Sony hardware.','Console-only ABI demo; no successful display/touch/Wi-Fi or Sony application lifecycle qualification.','No Sony binaries, ROMs or firmware image included in the app package.']}
(ROOT/'sources/native-hello-app-build.json').write_text(json.dumps(report,indent=2)+'\n');print('Hello native app:',len(data),'bytes; read-only QEMU entry checks passed.')
