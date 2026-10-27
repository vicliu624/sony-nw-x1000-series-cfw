"""Intent record persistence, ownership and I/O ambiguity; temporary files only."""
from pathlib import Path
import runpy,subprocess,tempfile,json,hashlib,os,errno
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/download-record-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
mf2,ix2,_,_=metadata['fixture']('0.1.1');header=array('MF',metadata['manifest'])+array('IX',metadata['index'])+array('MF2',mf2)+array('IX2',ix2);(work/'record_fixture.h').write_text(header)
sources=[p for p in metadata['sources'] if p!='tools/test_download_plan.c']+['runtime/store/download_intent.c','runtime/store/download_record.c','tools/test_download_record.c','tools/atomic_record_faults.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)];wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close,--wrap=rename'
subprocess.run(['gcc',*common,*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True)
runtime=metadata['work']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,wrap,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def tree(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' if p.is_dir() else 'special' for p in base.rglob('*')}
def call(command,mode,parent):
 run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_RECORD_MODE=mode,HB_RECORD_PARENT=str(parent)));assert run.returncode==0,(mode,run.returncode,run.stderr)
rows=[];skipped=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('save-discard','save-only','short-write','write-error','write-after-error','sync-file','sync-dir','close-file','close-dir','cancel','space','exists','link','parent-alias','replace','mutate','truncate','discard-sync','discard-replace','stage-exists','stage-link','rename-before','rename-after'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();(base/'unrelated').write_bytes(b'KEEP');record=parent/'.download-demo.intent';actual=parent
   if mode=='stage-exists':(parent/'.bundle-demo').mkdir();(parent/'.bundle-demo/keep').write_bytes(b'KEEP')
   elif mode=='stage-link':(parent/'.bundle-demo').symlink_to(base,target_is_directory=True)
   if mode=='exists':record.write_bytes(b'KEEP')
   elif mode=='link':record.symlink_to(base/'unrelated')
   elif mode=='parent-alias':actual=base/'alias';actual.symlink_to(parent,target_is_directory=True)
   call(command,mode,actual)
   assert (base/'unrelated').read_bytes()==b'KEEP'
   if mode=='stage-exists':assert (parent/'.bundle-demo/keep').read_bytes()==b'KEEP' and not record.exists() and {p.name for p in parent.iterdir()}=={'.bundle-demo'}
   elif mode=='stage-link':assert (parent/'.bundle-demo').is_symlink() and not record.exists()
   elif mode in ('exists','discard-replace'):assert record.read_bytes()==b'KEEP'
   elif mode=='link':assert record.is_symlink()
   elif mode=='replace':assert record.read_bytes()==b'KEEP' and Path(str(record)+'.saved').exists()
   elif mode=='mutate':assert record.read_bytes().startswith(b'X')
   elif mode=='truncate':assert record.exists()
   elif mode=='save-only':assert record.read_bytes().startswith(b'HBDL0001')
   else:assert not list(parent.iterdir()),(platform,mode)
   rows.append({'platform':platform,'case':mode,'passed':True})
 for mode in ('load-ready','load-discard','load-close-error','load-cancel','identity','corrupt','short','oversize','zero','hardlink','record-link','fifo','directory','load-parent-alias','forged','load-absent'):
  with tempfile.TemporaryDirectory(prefix='reload-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();record=parent/'.download-demo.intent'
   if mode!='load-absent':call(command,'save-forged' if mode=='forged' else 'save-only',parent)
   if mode=='corrupt':data=bytearray(record.read_bytes());data[20]^=1;record.write_bytes(data)
   elif mode=='short':record.write_bytes(record.read_bytes()[:12])
   elif mode=='oversize':record.write_bytes(b'X'*25405)
   elif mode=='zero':record.write_bytes(b'')
   elif mode=='hardlink':os.link(record,base/'other')
   elif mode=='record-link':record.rename(base/'other');record.symlink_to(base/'other')
   actual_parent=parent
   if mode=='fifo':
    record.unlink()
    try:os.mkfifo(record)
    except OSError as error:
     if error.errno in (errno.EOPNOTSUPP,errno.ENOSYS):skipped.append({'platform':platform,'case':'fifo','reason':'Temporary workspace filesystem cannot create FIFO'});continue
     raise
   elif mode=='directory':record.unlink();record.mkdir()
   elif mode=='load-parent-alias':actual_parent=base/'alias';actual_parent.symlink_to(parent,target_is_directory=True)
   before=tree(base);actual_mode='load-bad' if mode in ('corrupt','short','oversize','zero','hardlink','record-link','fifo','directory','load-parent-alias','forged') else mode
   call(command,actual_mode,actual_parent)
   if mode=='load-discard':assert not list(parent.iterdir())
   else:assert tree(base)==before,(platform,mode)
   rows.append({'platform':platform,'case':mode,'passed':True})
 for mode in ('prefix-zero','prefix-one','prefix-header','prefix-short','prefix-full','prefix-review','prefix-wrong','prefix-oversize','prefix-hardlink','prefix-link','prefix-stage','prefix-final','prefix-absent','prefix-space'):
  with tempfile.TemporaryDirectory(prefix='temp-prefix-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();call(command,'save-only',parent);final=parent/'.download-demo.intent';encoded=final.read_bytes();stage=parent/('.save-demo-'+hashlib.sha256(encoded).hexdigest());final.unlink()
   amount={'prefix-zero':0,'prefix-one':1,'prefix-header':85,'prefix-short':len(encoded)-1}.get(mode,len(encoded));stage.write_bytes(encoded[:amount])
   if mode=='prefix-wrong':stage.write_bytes(b'X')
   elif mode=='prefix-oversize':stage.write_bytes(encoded+b'X')
   elif mode=='prefix-hardlink':os.link(stage,base/'other')
   elif mode=='prefix-link':stage.rename(base/'other');stage.symlink_to(base/'other')
   elif mode=='prefix-stage':(parent/'.bundle-demo').mkdir();(parent/'.bundle-demo/keep').write_bytes(b'KEEP')
   elif mode=='prefix-final':final.write_bytes(b'KEEP')
   elif mode=='prefix-absent':stage.unlink()
   before=tree(base)
   bad=mode in ('prefix-wrong','prefix-oversize','prefix-hardlink','prefix-link','prefix-stage','prefix-final')
   operation='temp-bad' if bad else 'temp-absent' if mode=='prefix-absent' else 'temp-review' if mode=='prefix-review' else 'temp-save-conflict' if mode=='prefix-space' else 'temp-discard'
   call(command,operation,parent)
   if bad or mode in ('prefix-review','prefix-absent','prefix-space'):assert tree(base)==before,(platform,mode)
   else:assert not list(parent.iterdir()),(platform,mode)
   rows.append({'platform':platform,'case':mode,'passed':True})
 for mode in ('die-write','die-sync','die-publish'):
  with tempfile.TemporaryDirectory(prefix='publish-exit-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir()
   run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_RECORD_MODE=mode,HB_RECORD_PARENT=str(parent)));assert run.returncode==77,(platform,mode,run.returncode,run.stderr)
   final=parent/'.download-demo.intent'
   if mode=='die-publish':assert final.exists() and final.read_bytes().startswith(b'HBDL0001');call(command,'load-discard',parent)
   else:
    assert not final.exists();staged=list(parent.glob('.save-demo-*'));assert len(staged)==1
    if mode=='die-write':assert staged[0].read_bytes()==b'H'
    call(command,'temp-discard',parent)
   assert not list(parent.iterdir());rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'skipped_cases':skipped,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['tools/download_file_faults.c']},'limits':['Canonical quiescent temporary filesystem; not Sony FAT, concurrency or power-loss qualification.','Final records use same-directory rename after file fsync; matching content-addressed temp prefixes require explicit cleanup, not READY. Serial/quiescent publisher only.','No partial bundle adoption/deletion or UI/candidate integration yet.','Test wrappers simulate write/fsync/close/rename errors and three process exits, not every kernel or flash failure.','FIFO behavior not tested when the workspace filesystem cannot create it; see skipped_cases.']}
(ROOT/'sources/native-download-record-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Download intent record:',len(rows),'host/ARM cases passed.')
