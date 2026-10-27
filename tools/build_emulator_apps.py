"""Build external X1000 emulator apps; PC/WSL only, never access player."""
from pathlib import Path
import subprocess,json,hashlib,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/emulator-apps';work.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';version=(ROOT/'runtime/apps/emulators/VERSION').read_text().strip()
base=['-std=c99','-O2','-Wall','-Wextra','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffunction-sections','-fdata-sections','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-D_FILE_OFFSET_BITS=64','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_USE_POSIX_FILES','-DHB_STORE_SONY_LIBC','-DIS_LITTLE_ENDIAN','-Ithird_party/gnuboy','-Ithird_party/tama-id/core']
common=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/apps/emulators/platform.c','runtime/apps/emulators/storage.c','runtime/apps/emulators/app.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/start.c','runtime/store/start.S']
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
 assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest,name
all_reports=[]
for name,title in [('gbc','Game Boy Color'),('tamagotchi-id','Tamagotchi iD')]:
 out=work/name;out.mkdir(exist_ok=True);folder=out/'package';folder.mkdir(exist_ok=True);objects=[]
 extra=['runtime/platform/pcm_output.c','runtime/platform/pcm_posix.c','runtime/apps/fm-radio/fm_audio.c','runtime/apps/emulators/gbc_core.c','runtime/native/sha256.c']+['third_party/gnuboy/'+n+'.c'for n in ['lcd','refresh','lcdc','palette','cpu','mem','rtc','hw','sound']] if name=='gbc' else ['runtime/apps/emulators/tama_platform.c','third_party/tama-id/color.c','third_party/tama-id/core/tc_all.c']
 flags=base+([] if name=='gbc' else ['-DHB_TAMA_ID','-DTC_HOST','-DA918_COLOR_MENU','-DA918_COLOR_PERF','-DA918_EXTERNAL'])
 for i,source in enumerate(common+extra):
  obj=out/(str(i)+'-'+Path(source).stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
 app=folder/'app';subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
 data=app.read_bytes();elf=ELFFile(io.BytesIO(data));needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED'];assert needed==['libc.so.6']
 results=[]
 for args in [['--selftest'],['--help']]:
  run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),*args],capture_output=True,text=True,timeout=20);assert run.returncode==0,(name,args,run.stderr);results.append({'args':args,'exit':run.returncode,'stdout':run.stdout})
 digest=hashlib.sha256(data).hexdigest();manifest=f'api=1\nid={name}\nname={title}\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={digest}\n';(folder/'app.ini').write_text(manifest)
 files={p.name:p.read_bytes() for p in [app,folder/'app.ini']};(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(b).hexdigest()} {len(b)} {n}\n'for n,b in sorted(files.items())))
 report={'id':name,'app_version':version,'artifact':str(app.relative_to(ROOT)),'bytes':len(data),'sha256':digest,'needed':needed,'checks':results,'hardware_tested':False,'ROM_included':False,'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in common+extra+[str(p.relative_to(ROOT)) for p in (ROOT/'runtime/apps/emulators').glob('*.h')]+['runtime/apps/emulators/VERSION','runtime/platform/pcm_output.h']}}
 report['source_hashes'].update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['third_party/gnuboy','third_party/tama-id'] for p in (ROOT/folder).rglob('*') if p.is_file()})
 report['source_hashes']['runtime/apps/fm-radio/fm_audio.h']=hashlib.sha256((ROOT/'runtime/apps/fm-radio/fm_audio.h').read_bytes()).hexdigest()
 (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');all_reports.append(report)
(work/'build.json').write_text(json.dumps(all_reports,indent=2)+'\n');print([(r['id'],r['bytes'],r['sha256'])for r in all_reports])
