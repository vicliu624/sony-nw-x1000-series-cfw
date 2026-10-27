"""Bounded metadata cache recheck/consumption, host and stock-libc ARM."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os,struct
ROOT=Path(__file__).resolve().parents[1];metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'));work=ROOT/'work/metadata-cache-tests';work.mkdir(exist_ok=True)
large=bytes((i*13)%256 for i in range(32768));body=b'\0\xffmeta\0\r';digest=hashlib.sha256(body).digest();url='https://example.test/meta.bin';key=hashlib.sha256(b'HBMETA1'+url.encode()+digest+struct.pack('<I',len(body))).hexdigest()[:32]
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
(work/'metadata_cache_fixture.h').write_text(array('LARGE',large)+array('SHA_LARGE',hashlib.sha256(large).digest())+'static const char *KEY_LARGE='+json.dumps(hashlib.sha256(b'HBMETA1'+url.encode()+hashlib.sha256(large).digest()+struct.pack('<I',len(large))).hexdigest()[:32])+';\n'+array('BODY',body)+array('SHA',digest)+'static const char *URL='+json.dumps(url)+';\nstatic const char *KEY='+json.dumps(key)+';\n')
sources=['runtime/store/metadata_cache.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/test_metadata_cache.c','tools/payload_cache_faults.c'];bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S'];common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)];wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close,--wrap=unlink'
subprocess.run(['gcc',*common,*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True);runtime=metadata['work']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,wrap,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def call(command,mode,parent,expected=0):
 r=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_META_CACHE_MODE=mode,HB_META_CACHE_PARENT=str(parent)));assert r.returncode==expected,(mode,r.returncode,r.stderr)
def tree(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in base.rglob('*')}
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for scenario in ('complete','empty','short','corrupt','inspect','absent','oversize','link','hardlink','directory','alias','cancel','close-read','replace','mutate','unlink-before','unlink-after','sync','sync-replace','close-parent','process-exit','max-complete','max-short'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'cache';parent.mkdir();selected_body=large if scenario.startswith('max-') else body;selected_key=hashlib.sha256(b'HBMETA1'+url.encode()+hashlib.sha256(selected_body).digest()+struct.pack('<I',len(selected_body))).hexdigest()[:32];target=parent/('.fetch-'+selected_key);actual=parent;(parent/'.fetch-foreign').write_bytes(b'KEEP');(base/'unrelated').write_bytes(b'KEEP')
   if scenario.startswith('max-'):target.write_bytes(large if scenario=='max-complete' else large[:-1])
   elif scenario!='absent':target.write_bytes(b'' if scenario=='empty' else body[:3] if scenario=='short' else b'X'*len(body) if scenario=='corrupt' else body)
   if scenario=='oversize':target.write_bytes(body+b'X')
   elif scenario=='link':target.unlink();target.symlink_to(base/'unrelated')
   elif scenario=='hardlink':os.link(target,base/'other')
   elif scenario=='directory':target.unlink();target.mkdir()
   elif scenario=='alias':actual=base/'alias';actual.symlink_to(parent,target_is_directory=True)
   before=tree(base);bad=scenario in ('oversize','link','hardlink','directory','alias');mode='invalid' if bad else 'inspect' if scenario=='inspect' else scenario if scenario in ('absent','cancel','close-read','replace','mutate','unlink-before','unlink-after','sync','sync-replace','close-parent') else scenario if scenario.startswith('max-') else 'discard'
   if scenario=='process-exit':call(command,'die',parent,77);assert not target.exists()
   else:call(command,mode,actual)
   assert (parent/'.fetch-foreign').read_bytes()==b'KEEP' and (base/'unrelated').read_bytes()==b'KEEP'
   if bad or scenario in ('inspect','absent','cancel','close-read'):assert tree(base)==before,(platform,scenario)
   elif scenario in ('replace','sync-replace'):assert target.read_bytes()==b'KEEP'
   elif scenario=='mutate':assert target.read_bytes().startswith(b'X')
   else:assert not target.exists(),(platform,scenario)
   rows.append({'platform':platform,'case':scenario,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'fixture_sha256':hashlib.sha256((work/'metadata_cache_fixture.h').read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['tools/download_file_faults.c']},'limits':['Known configured metadata key only; partial/corrupt data never exposed to parser.','Observed hash protects discard after inspection, not publisher authentication.','Quiescent temporary filesystem, not Sony FAT/USB or power-loss qualification.','Process exit after unlink verifies recordless cache removal only, not every interruption point.']}
(ROOT/'sources/native-metadata-cache-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Metadata cache inspect/discard:',len(rows),'host/ARM cases passed.')
