"""Inject host filesystem errors/process exits into the C adapter, work fixtures only."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-fs-tests').resolve();work.mkdir(exist_ok=True)
p=subprocess.run(['python3',str(ROOT/'tools/test_store_fs.py')],cwd=ROOT,capture_output=True,text=True,timeout=30)
assert p.returncode==0,p.stderr
library=work/'faults.so'
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','tools/store_fs_faults.c','-ldl','-o',str(library)],cwd=ROOT,check=True)
def make(folder,revision):
 folder.mkdir(exist_ok=True);b=bytearray(96);b[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',b,16,2,40);b[-1]=revision;b=bytes(b)
 fields={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(b).hexdigest()}
 (folder/'app.ini').write_text('\n'.join(k+'='+v for k,v in fields.items())+'\n');(folder/'app').write_bytes(b)
def valid(folder):
 try:
  fields=dict(line.split('=',1) for line in (folder/'app.ini').read_text().splitlines())
  data=(folder/'app').read_bytes()
  return len(data)==int(fields['bytes']) and hashlib.sha256(data).hexdigest()==fields['sha256'] and fields['id']=='demo'
 except (OSError,ValueError,KeyError):return False
faults=[('write',1,'before'),('write',1,'after'),('write',2,'before'),('rename',1,'before'),('rename',1,'after'),('rename',1,'exit'),('rename',2,'before'),('rename',2,'after'),('rename',2,'exit'),('fsync',1,'before'),('fsync',5,'before'),('fsync',6,'before'),('unlink',1,'before'),('unlink',1,'after'),('unlink',1,'exit'),('unlink',2,'before'),('unlink',2,'after')]
original_cases=len(faults)
faults.extend([('write',3,'before'),('write',3,'after'),('write',3,'exit'),('fsync',7,'before'),('fsync',8,'before'),('unlink',3,'before'),('unlink',3,'after'),('unlink',3,'exit'),('rmdir',1,'before'),('rmdir',1,'after'),('rmdir',1,'exit')])
rows=[]
for index,(operation,nth,mode) in enumerate(faults):
 with tempfile.TemporaryDirectory(prefix='fault-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  apps=base/'apps';apps.mkdir();source=base/'package';make(source,2);make(apps/'demo',1)
  sentinel=base/'save.dat';sentinel.write_bytes(b'USER DATA MUST SURVIVE')
  args=[str(work/'driver'),str(apps),str(source),'demo','normal','apply']
  env=dict(os.environ,LD_PRELOAD=str(library),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION=operation,HB_TEST_NTH=str(nth),HB_TEST_MODE=mode)
  p=subprocess.run(args,capture_output=True,text=True,env=env,timeout=10)
  if mode=='exit':assert p.returncode==90,(operation,nth,mode,p.returncode,p.stdout,p.stderr);result='interrupted'
  else:
   assert p.returncode==0,p.stderr;result=int(p.stdout.strip());assert result!=0,(operation,nth,mode,'fault not observed')
  complete_live=valid(apps/'demo');complete_backup=valid(apps/'.backup-demo')
  assert complete_live or complete_backup,(operation,nth,mode,'both complete versions lost')
  args[-1]='recover'
  recovery=subprocess.run(args,capture_output=True,text=True,check=True,timeout=10)
  recovered=int(recovery.stdout.strip());assert recovered in (0,-3),(operation,nth,mode,recovered)
  if index<original_cases:assert recovered==0,('original recovery regression',operation,nth,mode)
  assert valid(apps/'demo'),(operation,nth,mode,'no valid live after recovery attempt')
  if recovered==0:assert not (apps/'.backup-demo').exists() and not (apps/'.install-demo').exists()
  explicit_result=None
  if recovered==-3:
   assert (operation,nth,mode)==('write',3,'before')
   args[-1]='keep-current'
   explicit=subprocess.run(args,capture_output=True,text=True,check=True,timeout=10)
   explicit_result=int(explicit.stdout.strip());assert explicit_result==0
   assert valid(apps/'demo') and (apps/'demo/app').read_bytes()[-1]==2
   assert not (apps/'.backup-demo').exists() and not (apps/'.cleanup-demo').exists()
  assert sentinel.read_bytes()==b'USER DATA MUST SURVIVE'
  rows.append({'operation':operation,'nth':nth,'mode':mode,'install_result':result,'complete_live_at_failure':complete_live,'complete_backup_at_failure':complete_backup,'recovery_result':recovered,'explicit_keep_current_result':explicit_result,'valid_live_after_recovery':True,'unrelated_data_unchanged':True})
refusals=[]
for mutation in ('bad-checksum','wrong-id','changed-live','changed-backup','foreign-backup-entry','changed-live-valid'):
 with tempfile.TemporaryDirectory(prefix='receipt-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  apps=base/'apps';apps.mkdir();source=base/'package';make(source,2);make(apps/'demo',1)
  args=[str(work/'driver'),str(apps),str(source),'demo','normal','apply']
  env=dict(os.environ,LD_PRELOAD=str(library),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION='unlink',HB_TEST_NTH='1',HB_TEST_MODE='exit')
  if mutation=='changed-live-valid':env['HB_TEST_MODE']='before'
  interrupted=subprocess.run(args,capture_output=True,text=True,env=env,timeout=10)
  if mutation=='changed-live-valid':assert interrupted.returncode==0 and int(interrupted.stdout.strip())==1
  else:assert interrupted.returncode==90
  receipt=apps/'.cleanup-demo';data=bytearray(receipt.read_bytes());assert len(data)==201
  if mutation=='bad-checksum':data[-1]^=1;receipt.write_bytes(data)
  elif mutation=='wrong-id':
   data[8]=ord('x');data[169:]=hashlib.sha256(data[:169]).digest();receipt.write_bytes(data)
  elif mutation=='changed-live':(apps/'demo/app').write_bytes(b'changed live content')
  elif mutation=='changed-backup':(apps/'.backup-demo/app').write_bytes(b'changed backup content')
  elif mutation=='changed-live-valid':make(apps/'demo',3);assert valid(apps/'demo') and valid(apps/'.backup-demo')
  else:(apps/'.backup-demo/foreign.dat').write_bytes(b'must not be deleted')
  def tree():
   return {str(path.relative_to(apps)):hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'directory' for path in apps.rglob('*')}
  before=tree();args[-1]='recover'
  result=subprocess.run(args,capture_output=True,text=True,check=True,timeout=10)
  assert int(result.stdout.strip())==-3 and tree()==before,mutation
  args[-1]='keep-current'
  explicit=subprocess.run(args,capture_output=True,text=True,check=True,timeout=10)
  assert int(explicit.stdout.strip())==-3 and tree()==before,mutation
  refusals.append({'case':mutation,'recovery_result':-3,'explicit_keep_current_result':-3,'entire_managed_tree_content_unchanged':True})
report={'all_passed':True,'physical_device_access':False,'cases':rows,'receipt_refusal_cases':refusals,'original_regression_cases':original_cases,'manual_review_cases':sum(r['recovery_result']==-3 for r in rows),'explicit_choice_recovered_cases':sum(r['explicit_keep_current_result']==0 for r in rows),'adapter_sha256':hashlib.sha256((ROOT/'runtime/store/fs_posix.c').read_bytes()).hexdigest(),'limits':['LD_PRELOAD error injection and _exit after real host operations, not hardware I/O failure or power loss.','Faults restricted to this run project work fixture path. No Sony files, devices, mount or firmware touched.','Normal recovery retains incomplete receipts; explicit keep-current checks both complete copies. No device recovery UI exists yet.','No target FAT durability, flash capacity or USB lifecycle qualification.']}
(ROOT/'sources/native-store-filesystem-faults.json').write_text(json.dumps(report,indent=2)+'\n');print('Filesystem fault tests:',len(rows),'passed;',report['manual_review_cases'],'require retained-state review.')



