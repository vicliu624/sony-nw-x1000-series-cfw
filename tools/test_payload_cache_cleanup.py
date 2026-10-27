"""Intent-bound exact-key payload cache cleanup; unrelated cache entries stay."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'));work=ROOT/'work/payload-cache-cleanup-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
mf2,ix2,_,_=metadata['fixture']('0.1.1');(work/'cache_cleanup_fixture.h').write_text(array('MF',metadata['manifest'])+array('IX',metadata['index'])+array('MF2',mf2)+array('IX2',ix2))
sources=[p for p in metadata['sources'] if p!='tools/test_download_plan.c']+['runtime/store/download_intent.c','runtime/store/download_record.c','runtime/store/payload_cache_cleanup.c','tools/test_payload_cache_cleanup.c','tools/payload_cache_faults.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S'];common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)];wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close,--wrap=unlink'
subprocess.run(['gcc',*common,*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True);runtime=metadata['work']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,wrap,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def tree(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in base.rglob('*')}
def call(command,mode,parent,cache,expected=0):
 run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_CACHE_MODE=mode,HB_RECORD_PARENT=str(parent),HB_CACHE_PARENT=str(cache)));assert run.returncode==expected,(mode,run.returncode,run.stderr)
rows=[];paths=metadata['paths'];keys=metadata['keys'];files=metadata['files']
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('review','partial','complete','absent','corrupt-in-range','oversize','link','hardlink','directory','cache-alias','identity','bad-record','cancel','replace','resize','new-target','unlink-before','unlink-after','replace-after','sync','close-record','close-cache','cancel-mid','process-exit'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();cache=base/'cache';cache.mkdir();actual=cache
   call(command,'save',parent,cache)
   (base/'unrelated').write_bytes(b'KEEP');(cache/'.fetch-unrelated').write_bytes(b'FOREIGN');(cache/'unknown-dir').mkdir();(cache/'unknown-dir/keep').write_bytes(b'KEEP')
   bundle=parent/'.bundle-demo';bundle.mkdir();(bundle/'keep').write_bytes(b'KEEP')
   targets=[cache/('.fetch-'+key) for key in keys]
   if mode!='absent':
    for i,(path,key) in enumerate(zip(paths,keys)):
     if mode=='new-target' and i==2:continue
     data=files[path] if mode=='complete' else files[path][:min(len(files[path]),20 if i==0 else 2)]
     targets[i].write_bytes(data)
   if mode=='corrupt-in-range':targets[0].write_bytes(b'X'*20)
   elif mode=='oversize':targets[1].write_bytes(b'X'*(len(files[paths[1]])+1))
   elif mode=='link':targets[1].unlink();targets[1].symlink_to(base/'unrelated')
   elif mode=='hardlink':os.link(targets[1],base/'other')
   elif mode=='directory':targets[1].unlink();targets[1].mkdir()
   elif mode=='cache-alias':actual=base/'alias';actual.symlink_to(cache,target_is_directory=True)
   elif mode=='bad-record':receipt=parent/'.download-demo.intent';data=bytearray(receipt.read_bytes());data[-1]^=1;receipt.write_bytes(data)
   before=tree(base);package_before=tree(parent)
   invalid=mode in ('oversize','link','hardlink','directory','cache-alias')
   operation='invalid' if invalid else mode if mode in ('review','identity','bad-record','cancel','replace','resize','new-target','unlink-before','unlink-after','replace-after','sync','close-record','close-cache','cancel-mid') else 'discard'
   if mode=='process-exit':call(command,'die',parent,cache,77);call(command,'discard',parent,cache)
   else:call(command,operation,parent,actual)
   assert tree(parent)==package_before and (base/'unrelated').read_bytes()==b'KEEP' and (cache/'.fetch-unrelated').read_bytes()==b'FOREIGN' and (cache/'unknown-dir/keep').read_bytes()==b'KEEP'
   if invalid or mode in ('review','identity','bad-record','cancel'):assert tree(base)==before,(platform,mode)
   elif mode=='replace':assert targets[1].read_bytes()==b'KEEP' and Path(str(targets[1])+'.saved').exists() and targets[0].exists()
   elif mode=='resize':assert targets[1].read_bytes().endswith(b'X') and targets[0].exists()
   elif mode=='new-target':assert targets[2].read_bytes()==b'KEEP' and targets[0].exists()
   elif mode=='replace-after':assert targets[0].read_bytes()==b'KEEP' and targets[1].exists()
   else:assert not any(p.exists() or p.is_symlink() for p in targets),(platform,mode)
   rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['tools/download_file_faults.c']},'limits':['Exact plan-derived payload keys only; unknown cache names and bundle/record untouched.','Provisional content may be corrupt within size bound; this is discard authority, never install verification.','Quiescent temporary filesystem, no concurrent writers/Sony FAT/USB/power-loss qualification.','One real process exit after an unlink, not exhaustive kill-point coverage.','No app-controller/UI integration or metadata-fetch cache recovery yet.']}
(ROOT/'sources/native-payload-cache-cleanup-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Receipt-bound payload cache cleanup:',len(rows),'host/ARM cases passed.')
