"""Whole provisional cleanup ordering: cache -> bundle -> receipt, with restarts."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'));work=ROOT/'work/download-recovery-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
(work/'recovery_fixture.h').write_text(array('MF',metadata['manifest'])+array('IX',metadata['index']))
sources=['runtime/store/'+p+'.c' for p in ('download_recovery','payload_cache_cleanup','partial_cleanup','download_record','download_intent','package_assemble','download_plan','download_file','download_stream','https_url','bundle_posix','inventory','package','cleanup_plan')]+['runtime/native/sha256.c','tools/test_download_recovery.c','tools/download_recovery_faults.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S'];common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)];wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close,--wrap=unlink'
subprocess.run(['gcc',*common,*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True);runtime=metadata['work']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,wrap,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def call(command,mode,parent,cache,expected=0):
 run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_RECOVERY_MODE=mode,HB_RECOVERY_PARENT=str(parent),HB_RECOVERY_CACHE=str(cache)));assert run.returncode==expected,(mode,run.returncode,run.stderr)
def tree(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in base.rglob('*')}
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('review','partial','empty','absent','unknown-bundle','oversize-cache','unknown-after','new-cache-after','cancel','sync-1','sync-2','sync-3','sync-4','sync-5','sync-6','die-cache','die-bundle','wrong-plan-object','replace-tree','sync-final-new-cache'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';cache=base/'cache';parent.mkdir();cache.mkdir();call(command,'save',parent,cache)
   (base/'unrelated').write_bytes(b'KEEP');(cache/'.fetch-foreign').write_bytes(b'FOREIGN');receipt=parent/'.download-demo.intent';bundle=parent/'.bundle-demo'
   targets=[cache/('.fetch-'+key) for key in metadata['keys']]
   if mode!='absent':
    bundle.mkdir()
    if mode!='empty':
     for name,data in dict(metadata['files'],**{'files.sha256':metadata['index']}).items():
      p=bundle/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data[:20] if name=='app' else data[:2] if name=='assets/icon.bin' else data)
    for i,path in enumerate(metadata['paths']):
     if mode=='new-cache-after' and i==2:continue
     targets[i].write_bytes(metadata['files'][path][:20] if i==0 else metadata['files'][path][:2])
   if mode=='unknown-bundle':(bundle/'unknown').write_bytes(b'KEEP')
   elif mode=='oversize-cache':targets[1].write_bytes(b'X'*7)
   before=tree(base);actual='invalid' if mode in ('unknown-bundle','oversize-cache') else mode if mode in ('review','unknown-after','new-cache-after','cancel','wrong-plan-object','replace-tree') or mode.startswith('sync-') else 'discard'
   if mode in ('die-cache','die-bundle'):call(command,mode,parent,cache,77);assert receipt.exists();call(command,'discard',parent,cache)
   else:call(command,actual,parent,cache)
   assert (base/'unrelated').read_bytes()==b'KEEP' and (cache/'.fetch-foreign').read_bytes()==b'FOREIGN'
   if mode in ('review','unknown-bundle','oversize-cache','cancel','wrong-plan-object'):assert tree(base)==before,(platform,mode)
   elif mode=='replace-tree':assert bundle.exists() and Path(str(bundle)+'.saved').exists() and targets[0].exists() and receipt.exists()
   elif mode=='sync-final-new-cache':assert targets[0].read_bytes()==b'KEEP' and not bundle.exists()
   elif mode=='unknown-after':assert (bundle/'unknown').read_bytes()==b'KEEP' and targets[0].exists() and receipt.exists()
   elif mode=='new-cache-after':assert targets[2].read_bytes()==b'KEEP' and targets[0].exists() and bundle.exists() and receipt.exists()
   else:assert not list(parent.iterdir()) and not any(p.exists() for p in targets),(platform,mode)
   rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['tools/payload_cache_faults.c','tools/download_file_faults.c']},'limits':['Provisional payload cache/bundle/receipt only, not metadata-fetch cache or app UI integration.','Quiescent temporary filesystem, not concurrent writers, Sony FAT/USB or power-loss qualification.','Real process exits at one cache unlink and one bundle fsync; not exhaustive interruption points.','This API requires a verified final record; temporary publication recovery is handled by the package job separately.']}
(ROOT/'sources/native-download-recovery-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Ordered download recovery cleanup:',len(rows),'host/ARM cases passed.')
