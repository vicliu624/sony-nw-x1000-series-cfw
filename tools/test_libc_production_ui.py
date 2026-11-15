"""Run the unchanged production ELF with QEMU-only LD_PRELOAD virtual devices."""
from pathlib import Path
from actual_app_fixture import prepare
from workflow_paths import work_area,write_report
import hashlib,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=work_area(ROOT,'libc-production-ui-review')
base = prepare()
composition=base['composition'];app=base['app'];lib=base['lib'];preload=base['preload']
row=next(r for r in base['manifest']['files'] if r['path']=='external/HOMEBREW/launcher/app')
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
tracked=[work/'frame.rgb565',work/'frame.png',Path(__file__),*base['inputs'],composition/'manifest.json',app,preload]
report={'passed':True,'unchanged_candidate_sha256':row['sha256'],'actual_ELF_UI_return_exit':run.returncode,'events':events,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['LD_PRELOAD overrides device I/O only for offline testing; not deployed or firmware content.','Production executable unchanged; virtual geometry, mapping, readiness and touch replace real hardware.','Normal return from launcher demonstrated; original Sony proxy/GUI not running.']}
write_report(ROOT,'native-libc-production-ui-tests.json',report);print('Unchanged selected launcher ELF: virtual frame, touch BACK, unmap/close and exit0 passed.')






