"""Run the unchanged production ELF with QEMU-only LD_PRELOAD virtual devices."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import hashlib,json,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=work_area(ROOT,'libc-production-ui-review')
composition=composition_path(ROOT);manifest=json.loads((composition/'manifest.json').read_text());app=composition/'external/HOMEBREW/launcher/app'
row=next(r for r in manifest['files'] if r['path']=='external/HOMEBREW/launcher/app');assert hashlib.sha256(app.read_bytes()).hexdigest()==row['sha256']
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
source=ROOT/'tools/fixtures/device_preload.c';preload=work/'virtual-devices.so'
compile_flags=['-D_GNU_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fPIC']
objects=[]
for index,path in enumerate((str(source),'runtime/native/syscalls.S')):
 obj=work/('preload-'+str(index)+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*compile_flags,'-c',path,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
subprocess.run(['arm-linux-gnueabi-gcc','-shared','-nostdlib','-Wl,--build-id=none','-Wl,--hash-style=sysv','-Wl,-soname,virtual-devices.so',*objects,str(lib/'libc.so.6'),'-lgcc','-o',str(preload)],cwd=ROOT,check=True)
assert not Path('/dev/fb/0').exists() and not Path('/dev/icx_touch_screen').exists()
with tempfile.TemporaryDirectory(dir=work) as temporary:
 prefix=Path(temporary);(prefix/'lib').mkdir()
 for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
 shutil.copytree(composition/'external/HOMEBREW/apps',prefix/'contents/HOMEBREW/apps')
 run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-0','/contents/HOMEBREW/launcher/app','-E','LD_PRELOAD='+str(preload),'-E','HB_TEST_FRAME='+str(work/'frame.rgb565'),str(app),'--native'],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
 events=[line for line in run.stderr.splitlines() if line.startswith('VDEV ')]
 assert events==['VDEV OPEN FB','VDEV OPEN TOUCH','VDEV FRAME','VDEV UNMAP','VDEV CLOSE FB','VDEV RELEASE COMPLETE'],events
 assert hashlib.sha256(app.read_bytes()).hexdigest()==row['sha256']
raw=(work/'frame.rgb565').read_bytes();assert len(raw)==240*432*2
import struct,zlib
rgb=bytearray()
for offset in range(0,len(raw),2):
 value=int.from_bytes(raw[offset:offset+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
(work/'frame.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
tracked=[work/'frame.rgb565',work/'frame.png',Path(__file__),source,ROOT/'runtime/native/syscalls.S',composition/'manifest.json',app,preload,lib/'libc.so.6',lib/'ld-linux.so.3']
report={'passed':True,'unchanged_candidate_sha256':row['sha256'],'actual_ELF_UI_return_exit':run.returncode,'events':events,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['LD_PRELOAD overrides device I/O only for offline testing; not deployed or firmware content.','Production executable unchanged; virtual geometry, mapping, readiness and touch replace real hardware.','Normal return from launcher demonstrated; original Sony proxy/GUI not running.']}
write_report(ROOT,'native-libc-production-ui-tests.json',report);print('Unchanged selected launcher ELF: virtual frame, touch BACK, unmap/close and exit0 passed.')






