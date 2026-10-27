"""Persisted pending-plan codec and provisional resource cleanup host tests."""
from pathlib import Path
import hashlib,json,os,shutil,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-pending-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/pending_plan.c','runtime/store/cleanup_posix.c','runtime/store/cleanup_plan.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_pending_cleanup_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','tools/store_fs_faults.c','-ldl','-o',str(work/'faults.so')],cwd=ROOT,check=True)
def index(files):return b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
def make(folder,revision,resources=True):
 folder.mkdir();program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program[-1]=revision;program=bytes(program)
 fields={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
 files={'app':program,'app.ini':('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()}
 if resources:files.update({'assets/theme.dat':b'theme','fonts/ui/a.bin':b'font','empty.dat':b''})
 for name,data in files.items():
  out=folder/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 if resources:(folder/'files.sha256').write_bytes(index(files))
 return files
def tree(folder):return {str(p.relative_to(folder)):'link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in folder.rglob('*')}
scenarios=['update-complete','first-install','legacy-incoming','partial-files','empty-stage','stage-absent','extra-file','extra-directory','oversize-file','file-link','directory-link','stage-link','valid-live-changed','missing-live','unexpected-backup','bad-checksum','bad-id','bad-old-identity','bad-profile','bad-length','cancel']
faults=[('unlink',n,mode) for n in (1,3,6) for mode in ('before','after','exit')]+[('rmdir',1,mode) for mode in ('before','after','exit')]+[('fsync',1,mode) for mode in ('before','after','exit')]
rows=[]
for scenario in scenarios+faults:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  apps=base/'apps';apps.mkdir();(apps/'.store-lock').write_bytes(b'');live=apps/'demo';incoming=base/'incoming'
  no_old=scenario in ('first-install','unexpected-backup')
  old_files=None if no_old else make(live,1)
  new_files=make(incoming,2,scenario!='legacy-incoming')
  save=base/'save.dat';save.write_bytes(b'USER SAVE');receipt=apps/'.pending-demo'
  def run(mode,env=None,exit_code=0):
   p=subprocess.run([str(work/'driver'),mode,str(apps),str(incoming),str(receipt)],capture_output=True,text=True,env=env,timeout=10)
   assert p.returncode==exit_code,(scenario,p.returncode,p.stdout,p.stderr)
   return None if exit_code else int(p.stdout.strip())
  assert run('plan')==0
  raw=receipt.read_bytes();assert raw[:8]==b'HBSTG001' and raw[8]==int(not no_old)
  assert struct.unpack_from('<I',raw,41)[0]+77==len(raw) and hashlib.sha256(raw[:-32]).digest()==raw[-32:]
  stage=apps/'.install-demo';shutil.copytree(incoming,stage)
  refusal=False
  if scenario=='partial-files':
   for name in ('app','app.ini','assets/theme.dat','files.sha256'):(stage/name).write_bytes((stage/name).read_bytes()[:2])
  elif scenario=='empty-stage':shutil.rmtree(stage);stage.mkdir()
  elif scenario=='stage-absent':shutil.rmtree(stage)
  elif scenario=='extra-file':(stage/'foreign').write_bytes(b'KEEP');refusal=True
  elif scenario=='extra-directory':(stage/'foreign').mkdir();refusal=True
  elif scenario=='oversize-file':(stage/'app').write_bytes(bytes(97));refusal=True
  elif scenario=='file-link':(stage/'assets/theme.dat').unlink();(stage/'assets/theme.dat').symlink_to(save);refusal=True
  elif scenario=='directory-link':
   (stage/'assets/theme.dat').unlink();(stage/'assets').rmdir();(stage/'assets').symlink_to(base,target_is_directory=True);refusal=True
  elif scenario=='stage-link':shutil.rmtree(stage);stage.symlink_to(base,target_is_directory=True);refusal=True
  elif scenario=='valid-live-changed':
   (live/'assets/theme.dat').write_bytes(b'other theme');old_files['assets/theme.dat']=b'other theme';(live/'files.sha256').write_bytes(index(old_files));refusal=True
  elif scenario=='missing-live':live.rename(apps/'.backup-demo');refusal=True
  elif scenario=='unexpected-backup':make(apps/'.backup-demo',1);refusal=True
  elif scenario in ('bad-checksum','bad-id','bad-old-identity','bad-profile','bad-length'):
   data=bytearray(raw)
   if scenario=='bad-checksum':data[-1]^=1
   elif scenario=='bad-id':
    length=struct.unpack_from('<I',data,41)[0];data[53]=ord('x');data[45+length-32:45+length]=hashlib.sha256(data[45:45+length-32]).digest()
   elif scenario=='bad-old-identity':data[9]^=1
   elif scenario=='bad-profile':data[8]=2
   else:struct.pack_into('<I',data,41,0xffffffff)
   if scenario!='bad-checksum':data[-32:]=hashlib.sha256(data[:-32]).digest()
   receipt.write_bytes(data);refusal=True
  elif scenario=='cancel':refusal=True
  receipt_before=receipt.read_bytes();live_before=tree(live) if live.exists() else None;source_before=tree(incoming)
  if isinstance(scenario,tuple):
   operation,nth,mode=scenario
   env=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION=operation,HB_TEST_NTH=str(nth),HB_TEST_MODE=mode)
   result=run('clean',env,90 if mode=='exit' else 0)
   if mode!='exit':assert result!=0,('missing injected failure',scenario)
   assert run('check')==0 and run('clean')==0 and not stage.exists()
  elif refusal:
   before=tree(apps);assert run('cancel' if scenario=='cancel' else 'clean')!=0 and tree(apps)==before
  else:
   before=tree(apps);assert run('check')==0 and tree(apps)==before
   assert run('clean')==0 and not stage.exists();assert run('clean')==0
  assert (tree(live) if live.exists() else None)==live_before and tree(incoming)==source_before and receipt.read_bytes()==receipt_before and save.read_bytes()==b'USER SAVE'
  rows.append({'case':str(scenario),'refused_without_mutation':refusal,'live_source_receipt_save_unchanged':True,'stage_removed':not stage.exists()})
for source in sources[:2]:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',source,'-o',str(work/(Path(source).stem+'.arm.o'))],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources[:2]},'limits':['Pending receipt is generated/synced before fixture stage creation; no real installer integration yet.','Provisional declared files may be incomplete and are disposable only under trusted persisted intent ownership.','Caller holds lock and keeps trees quiescent; not a sandbox or publisher authentication.','Host errors/process exits are not target FAT/power-loss qualification.','No live activation, backup deletion, network download, device program or linked ARM app.']}
(ROOT/'sources/native-store-pending-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Pending ownership/cleanup:',len(rows),'cases passed; ARM objects compiled.')
