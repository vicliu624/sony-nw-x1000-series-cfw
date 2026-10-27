"""Bounded remote catalog parsing and metadata binding, host and Sony libc ARM."""
from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/remote-catalog-tests';work.mkdir(exist_ok=True)
mf=metadata['manifest'];ix=metadata['index']
row=['demo','0.1.0','https://example.test/apps/demo/0.1.0/',str(len(mf)),hashlib.sha256(mf).hexdigest(),str(len(ix)),hashlib.sha256(ix).hexdigest()]
def listing(fields):return 'HBSTORE1\n'+'\t'.join(fields)+'\n'
invalid=[]
for index,value in [(0,'../demo'),(0,'Demo'),(1,''),(1,'bad version'),(2,'http://example.test/'),(2,'https://example.test/x'),(2,'https://example.test/?x/'),(2,'https://example.test/#x/'),(2,'https://example.test/'+('a'*513)+'/'),(3,'0'),(3,'1025'),(3,'01'),(3,'99999999999999999999'),(4,'g'*64),(4,'f'*63),(5,'32769'),(6,'A'*64)]:
 fields=row.copy();fields[index]=value;invalid.append(listing(fields))
invalid += [listing(row)+'\n',listing(row).replace('\t',' ',1),listing(row).rstrip('\n')+'\textra\n']
# Entry/count boundary, sorted IDs, no duplicate IDs.
valid32='HBSTORE1\n'+''.join('\t'.join([f'app{i:02}',*row[1:]])+'\n' for i in range(32))
invalid.append(valid32+'\t'.join(['zzz',*row[1:]])+'\n')
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
header=array('VALID32',valid32.encode())+array('CATALOG',listing(row).encode())+array('MANIFEST',mf)+array('INDEX',ix)
header+='static const char *INVALIDS[]={'+','.join(json.dumps(s) for s in invalid)+'};\n'
(work/'remote_catalog_fixture.h').write_text(header)
sources=[p for p in metadata['sources'] if p!='tools/test_download_plan.c']+['runtime/store/remote_catalog.c','tools/test_remote_catalog.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
runtime=metadata['work'];bridge=['runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['catalog snapshot and valid metadata plan','version mismatch invalidates plan','manifest/index hashes and lengths bound','empty listing','bad magic/NUL/CR/truncation/oversize rejected','duplicate IDs and excess entries rejected','invalid URL/id/version/size/digest/field count rejected'],'generated_invalid_rows':len(invalid),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge},'fixture_sha256':hashlib.sha256(header.encode()).hexdigest(),'limits':['Parser and metadata binding only; no remote bootstrap fetch, listing UI or publisher signature.','HTTPS base limited to512 ASCII bytes, LF-only catalog, at most32 unique sorted app IDs.','No hardware, device filesystem or firmware qualification.']}
(ROOT/'sources/native-remote-catalog-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Remote catalog parser/metadata binding passed on host and ARM/QEMU.')
