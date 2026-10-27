"""Receipt-bound partial bundle cleanup and restart after an actual process exit."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'));work=ROOT/'work/partial-cleanup-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
mf2,ix2,_,_=metadata['fixture']('0.1.1');header=array('MF',metadata['manifest'])+array('IX',metadata['index'])+array('MF2',mf2)+array('IX2',ix2);(work/'partial_fixture.h').write_text(header)
sources=['runtime/store/'+p+'.c' for p in ('partial_cleanup','download_record','download_intent','package_assemble','download_plan','download_file','download_stream','https_url','bundle_posix','inventory','package','cleanup_plan')]+['runtime/native/sha256.c','tools/test_partial_cleanup.c','tools/partial_cleanup_faults.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)];wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close'
subprocess.run(['gcc',*common,*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True);runtime=metadata['work']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,wrap,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def call(command,mode,parent,expected=0):
 run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_PARTIAL_MODE=mode,HB_PARTIAL_PARENT=str(parent)));assert run.returncode==expected,(mode,run.returncode,run.stderr)
def tree(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in base.rglob('*')}
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('review','empty','absent','short-controls','partial','bad-content','missing-controls','complete','unknown','unknown-dir','oversize','link','hardlink','root-link','bad-record','missing-record','identity','cancel','replace-record','replace-tree','sync-1','sync-2','sync-3','sync-4','sync-5','process-exit','process-exit-unknown','mutate-record','read-close'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();(base/'unrelated').write_bytes(b'KEEP');bundle=parent/'.bundle-demo';receipt=parent/'.download-demo.intent'
   call(command,'save',parent)
   files=dict(metadata['files'],**{'files.sha256':metadata['index']})
   if mode!='absent':
    bundle.mkdir()
    if mode!='empty':
     for name,data in files.items():
      if mode=='short-controls':
       if name not in ('app.ini','files.sha256'):continue
       data=data[:5]
      elif mode=='missing-controls':
       if name!='assets/icon.bin':continue
       data=data[:2]
      elif mode not in ('complete',):
       if name=='app':data=data[:20]
       elif name=='assets/icon.bin':data=data[:2]
      p=bundle/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   if mode=='bad-content':(bundle/'app').write_bytes(b'X'*len(files['app']))
   elif mode=='unknown':(bundle/'unknown').write_bytes(b'KEEP')
   elif mode=='unknown-dir':(bundle/'unknown').mkdir()
   elif mode=='oversize':(bundle/'app').write_bytes(b'X'*(len(files['app'])+1))
   elif mode=='link':(bundle/'app').unlink();(bundle/'app').symlink_to(base/'unrelated')
   elif mode=='hardlink':os.link(bundle/'app',base/'other')
   elif mode=='root-link':bundle.rename(base/'saved');bundle.symlink_to(base/'saved',target_is_directory=True)
   elif mode=='bad-record':data=bytearray(receipt.read_bytes());data[-1]^=1;receipt.write_bytes(data)
   elif mode=='missing-record':receipt.unlink()
   before=tree(base)
   invalid=mode in ('unknown','unknown-dir','oversize','link','hardlink','root-link')
   actual='invalid' if invalid else mode if mode in ('review','bad-record','missing-record','identity','cancel','replace-record','replace-tree','mutate-record','read-close') or mode.startswith('sync-') else 'discard'
   if mode in ('process-exit','process-exit-unknown'):
    call(command,'die',parent,77);assert receipt.exists() and bundle.exists()
    if mode=='process-exit-unknown':
     (bundle/'unknown').write_bytes(b'KEEP');preserved=tree(base);call(command,'invalid',parent);assert tree(base)==preserved
    else:call(command,'discard',parent)
   else:call(command,actual,parent)
   if invalid or mode in ('review','bad-record','missing-record','identity','cancel'):assert tree(base)==before,(platform,mode)
   elif mode=='process-exit-unknown':assert (bundle/'unknown').read_bytes()==b'KEEP' and receipt.exists()
   elif mode=='mutate-record':assert receipt.read_bytes().startswith(b'X') and tree(bundle)=={str(Path(k).relative_to(Path('packages/.bundle-demo'))):v for k,v in before.items() if k.startswith('packages/.bundle-demo/')}
   elif mode=='replace-record':assert receipt.read_bytes()==b'KEEP' and bundle.exists() and Path(str(receipt)+'.saved').exists()
   elif mode=='replace-tree':assert (bundle/'keep').read_bytes()==b'KEEP' and Path(str(bundle)+'.saved').exists() and receipt.exists()
   else:assert not list(parent.iterdir()),(platform,mode)
   assert (base/'unrelated').read_bytes()==b'KEEP';rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['tools/download_file_faults.c']},'limits':['Quiescent host temporary filesystem, not Sony FAT/USB/power-loss qualification.','Record is persisted before host fixture creates provisional payload; this unit does not invoke the app controller.','Process exit occurs at the first cleanup fsync; not exhaustive kill-point coverage.','No raw partitions, LIVE installation changes or execution of synthetic ELF.','Invalid/missing receipt and unknown tree entries preserved; no partial download continuation.','Separate .fetch cache cleanup is not implemented by this bundle-only API; caller must handle it before receipt deletion.']}
(ROOT/'sources/native-partial-cleanup-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Receipt-bound partial cleanup:',len(rows),'host/ARM cases passed.')
