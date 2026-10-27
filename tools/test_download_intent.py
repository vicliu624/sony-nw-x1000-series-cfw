"""Pure download intent encoding and exact plan binding, host/stock-libc ARM."""
from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/download-intent-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
large_files={'app':metadata['program'],'app.ini':metadata['manifest']}
for i in range(126):large_files['a'*50+'/'+'b'*50+'/'+'c'*50+f'/f{i:03}']=b''
large_index=b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'.encode() for name,data in sorted(large_files.items()))
mf2,ix2,_,_=metadata['fixture']('0.1.1');header=array('MF',metadata['manifest'])+array('IX',metadata['index'])+array('MF2',mf2)+array('IX2',ix2)+array('IX_LARGE',large_index);(work/'intent_fixture.h').write_text(header)
sources=[p for p in metadata['sources'] if p!='tools/test_download_plan.c']+['runtime/store/download_intent.c','tools/test_download_intent.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
runtime=metadata['work'];bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['download-specific envelope, deterministic roundtrip and installer-record separation','every single-byte corruption rejected','wrong ID/version and truncation/oversize rejected','small output capacity reports zero bytes','resource edits including rechecksummed records rejected by exact plan match','invalid plan cannot create usable intent','128-entry near-maximum path record roundtrip within fixed capacity'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge},'fixture_sha256':hashlib.sha256(header.encode()).hexdigest(),'limits':['Pure serialization/binding, no persistence, directory adoption or deletion.','Unkeyed checksum is not publisher authentication or malicious-program isolation.','Not integrated into app candidate; partial-download recovery remains incomplete.']}
(ROOT/'sources/native-download-intent-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Download intent encoding/plan binding passed on host and ARM/QEMU.')
