"""Build and exercise the actual external diagnostic ELF on the PC only."""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess,zlib
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='work/diagnostic-app-review-1');args=parser.parse_args()
work=(ROOT/args.output).resolve();assert work.is_relative_to(ROOT/'work');work.mkdir(exist_ok=False)
lib=ROOT/'work/arm-signal-tests/lib';version=(ROOT/'VERSION').read_text().strip()
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
folder=work/'APPS/diagnostics';folder.mkdir(parents=True);artifact=folder/'app'
sources=['runtime/apps/diagnostics/diagnostics.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/start.c','runtime/store/start.S']
flags=['-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
symbols=subprocess.check_output(['arm-linux-gnueabi-nm',str(artifact)],text=True);assert 'x1000_oabi_call' not in symbols and 'x1000_rt_sigreturn' not in symbols
data=artifact.read_bytes();digest=hashlib.sha256(data).hexdigest()
(folder/'app.ini').write_text(f'api=1\nid=diagnostics\nname=Device Check\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={digest}\n')
(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256((folder/n).read_bytes()).hexdigest()} {(folder/n).stat().st_size} {n}\n' for n in ('app','app.ini')))
fixture=work/'proc';fixture.mkdir();(fixture/'mtd').write_text('dev: size erasesize name\nmtd1: 09400000 00020000 "RootFS"\n');(fixture/'mounts').write_text('/dev/mtdblock/1 / ext2 ro 0 0\n');(fixture/'meminfo').write_text('MemTotal: 65536 kB\nMemFree: 12345 kB\n')
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
help_run=subprocess.run(base+[str(artifact),'--help'],capture_output=True,text=True,check=True,timeout=10);assert 'No log files' in help_run.stdout
dump=subprocess.run(['qemu-arm','-cpu','arm926','-E','HB_DIAG_PROC_ROOT='+str(fixture),str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),'--dump'],capture_output=True,text=True,check=True,timeout=10);assert 'MTD1_BYTES=155189248' in dump.stdout
(work/'fixture-dump.txt').write_text(dump.stdout)
missing=subprocess.run(['qemu-arm','-cpu','arm926','-E','HB_DIAG_PROC_ROOT='+str(work/'missing'),str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),'--dump'],capture_output=True,text=True,timeout=10);assert missing.returncode==1 and 'MTD1_BYTES=UNAVAILABLE' in missing.stdout
ui_report='sources/workflow-profiles/store-setup/native-libc-production-ui-tests.json';ui=verify_report(ROOT,ui_report);assert ui['passed']
preload=ROOT/'work/workflow-profiles/store-setup/libc-production-ui-review/virtual-devices.so'
assert ui['source_hashes'][str(preload.relative_to(ROOT))]==hashlib.sha256(preload.read_bytes()).hexdigest()
prefix=work/'sysroot';(prefix/'lib').mkdir(parents=True)
for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
frame=work/'diagnostics.rgb565'
command=['qemu-arm','-cpu','arm926','-L',str(prefix)]
for key,value in {'LD_PRELOAD':str(preload),'HB_DIAG_PROC_ROOT':str(fixture),'HB_TEST_MODE':'loop','HB_TEST_CHILD':'1','HB_TEST_FRAME':str(frame)}.items():command+=['-E',key+'='+value]
run=subprocess.run(command+[str(artifact)],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stderr)
events=[line for line in run.stderr.splitlines() if line.startswith('VDEV ')]
assert events.count('VDEV CHILD FRAME')==2 and events[-1]=='VDEV CHILD RELEASE COMPLETE',events
(work/'ui.log').write_text(run.stderr)
raw=frame.read_bytes();assert len(raw)==240*432*2 and int.from_bytes(raw[:2],'little')==0x0320
rgb=bytearray()
for i in range(0,len(raw),2):
 value=int.from_bytes(raw[i:i+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
png=work/'diagnostics.png';png.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
tracked=[Path(__file__),ROOT/'VERSION',*[ROOT/p for p in sources],ROOT/'runtime/native/font.inc',ROOT/'runtime/native/linux_devices.h',ROOT/'runtime/native/linux_device_io.h',ROOT/'runtime/native/linux_signals.h',ROOT/'runtime/native/frontend.h',lib/'libc.so.6',lib/'ld-linux.so.3',preload,ROOT/ui_report,*fixture.iterdir(),frame,png,work/'ui.log',work/'fixture-dump.txt']
report={'passed':True,'version':version,'artifact':str(artifact.relative_to(ROOT)),'bytes':len(data),'sha256':digest,'events':events,'ui_return_exit':run.returncode,'storage_writes_implemented':False,'checks':['actual ARM --help','known proc fixture size parsing','missing proc files return unavailable','actual ELF virtual refresh and BACK cleanup'],'hardware_tested':False,'limits':['Fixture MTD values are not measured hardware geometry.','Virtual display/touch only; no Sony GUI or physical handoff qualification.','No proc data is saved by the application; stdout and PC screenshot capture belong to this test.'],'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('passed','artifact','bytes','sha256','checks')},indent=2))
