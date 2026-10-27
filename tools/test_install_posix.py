"""Unified resource installer normal/fault/recovery tests on host work fixtures."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-install-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/install_posix.c','runtime/store/transaction.c','runtime/store/stage_posix.c','runtime/store/cleanup_posix.c','runtime/store/pending_plan.c','runtime/store/cleanup_plan.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_install_posix_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','tools/store_fs_faults.c','-ldl','-o',str(work/'faults.so')],cwd=ROOT,check=True)
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',area/'manifest.json']+[area/f['path'] for f in json.loads((area/'manifest.json').read_text())['files']]
def candidate():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before_candidate=candidate()
def index(files):return b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
def make(folder,revision,resources=True):
 folder.mkdir(exist_ok=True);program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program[-1]=revision;program=bytes(program)
 fields={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
 files={'app':program,'app.ini':('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()}
 if resources:files.update({'assets/theme.dat':b'theme '+str(revision).encode(),'fonts/ui/a.bin':b'font','empty.dat':b''})
 for name,data in files.items():
  p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 if resources:(folder/'files.sha256').write_bytes(index(files))
 return files
def tree(folder):return {str(p.relative_to(folder)):'link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in folder.rglob('*')}
def valid(folder):
 try:
  fields=dict(line.split('=',1) for line in (folder/'app.ini').read_text().splitlines());data=(folder/'app').read_bytes()
  if len(data)!=int(fields['bytes']) or hashlib.sha256(data).hexdigest()!=fields['sha256']:return False
  entries=(folder/'files.sha256').read_text().splitlines() if (folder/'files.sha256').exists() else []
  if entries:
   assert entries[0]=='HBFILES1'
   for row in entries[1:]:
    digest,size,path=row.split(' ');content=(folder/path).read_bytes()
    if len(content)!=int(size) or hashlib.sha256(content).hexdigest()!=digest:return False
  return True
 except (OSError,ValueError,KeyError,AssertionError):return False
normal=['first-resource','first-legacy','update-resource','legacy-to-resource','resource-to-legacy','bad-source','extra-source','cancel','space','source-link','root-alias','unknown-stage','unknown-backup','legacy-receipt','lock-busy','idle-empty-first','idle-empty-update','idle-current-invalid','idle-pending-link','idle-pending-big','idle-stage-present','idle-backup-present','idle-valid-record-conflict','commit-repair-conflict','commit-repair-partial-backup']
faults=[('write',n,mode) for n in (1,2,4,7) for mode in ('before','after','exit')]+[('rename',n,mode) for n in (1,2) for mode in ('before','after','exit')]+[('unlink',n,mode) for n in (1,3,6,7,8) for mode in ('before','after','exit')]+[('rmdir',1,mode) for mode in ('before','after','exit')]+[('fsync',n,mode) for n in (1,5,10) for mode in ('before','after','exit')]
rows=[]
for scenario in normal+faults:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  apps=base/'apps';apps.mkdir();(apps/'.store-lock').write_bytes(b'');source=base/'package';live=apps/'demo'
  first=scenario in ('first-resource','first-legacy','idle-empty-first')
  if not first:make(live,1,scenario!='legacy-to-resource')
  make(source,2,scenario not in ('first-legacy','resource-to-legacy'))
  (base/'save.dat').write_bytes(b'USER SAVE');(apps/'unrelated.txt').write_bytes(b'OTHER APP DATA')
  actual_root=apps;mode='apply';space='normal';expected=0
  if scenario=='bad-source':(source/'assets/theme.dat').write_bytes(b'bad');expected=-5
  elif scenario=='extra-source':(source/'extra.dat').write_bytes(b'extra');expected=-5
  elif scenario=='cancel':mode='cancel';expected=-2
  elif scenario=='space':space='full';expected=-4
  elif scenario=='source-link':(source/'assets/theme.dat').unlink();(source/'assets/theme.dat').symlink_to(base/'save.dat');expected=-5
  elif scenario=='root-alias':actual_root=base/'alias';actual_root.symlink_to(apps,target_is_directory=True);expected=-5
  elif scenario=='unknown-stage':(apps/'.install-demo').mkdir();(apps/'.install-demo/keep').write_bytes(b'KEEP');expected=-3
  elif scenario=='unknown-backup':make(apps/'.backup-demo',9);expected=-3
  elif scenario=='legacy-receipt':(apps/'.cleanup-demo').write_bytes(b'v1 metadata must not be guessed');expected=-3
  if str(scenario).startswith('idle-'):
   mode='cancel-idle';expected=0 if scenario in ('idle-empty-first','idle-empty-update') else -3
   (apps/'.pending-demo').write_bytes(b'')
   if scenario=='idle-current-invalid':(live/'app').write_bytes(b'broken')
   elif scenario=='idle-pending-link':
    (apps/'.pending-demo').unlink();(apps/'.pending-demo').symlink_to(base/'save.dat')
   elif scenario=='idle-pending-big':(apps/'.pending-demo').write_bytes(bytes(25438))
   elif scenario=='idle-stage-present':(apps/'.install-demo').mkdir();(apps/'.install-demo/keep').write_bytes(b'KEEP')
   elif scenario=='idle-backup-present':make(apps/'.backup-demo',9)
   elif scenario=='idle-valid-record-conflict':(apps/'.pending-demo').unlink()
  def run(action='apply',environment=None,exit_code=0):
   p=subprocess.run([str(work/'driver'),str(actual_root),str(source),'demo',action,space],capture_output=True,text=True,env=environment,timeout=15)
   assert p.returncode==exit_code,(scenario,p.returncode,p.stdout,p.stderr)
   return None if exit_code else int(p.stdout.strip())
  if scenario=='idle-valid-record-conflict':
   injected=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION='write',HB_TEST_NTH='1',HB_TEST_MODE='exit')
   run('apply',injected,90);make(live,3)
  elif scenario in ('commit-repair-conflict','commit-repair-partial-backup'):
   injected=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION='write',HB_TEST_NTH='7',HB_TEST_MODE='before')
   assert run('apply',injected)==1
   if scenario=='commit-repair-conflict':make(apps/'.backup-demo',9)
   else:(apps/'.backup-demo/app.ini').unlink()
   mode='recover';expected=-3
  old=tree(live) if live.exists() else None;source_before=tree(source);root_before=tree(apps)
  recovery=None;explicit=None
  if isinstance(scenario,tuple):
   operation,nth,fault_mode=scenario
   env=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION=operation,HB_TEST_NTH=str(nth),HB_TEST_MODE=fault_mode)
   result=run('apply',env,90 if fault_mode=='exit' else 0)
   if fault_mode!='exit':assert result!=0,('fault not observed',scenario)
   assert valid(live) or valid(apps/'.backup-demo'),('complete copies lost',scenario)
   recovery=run('recover');assert recovery in (0,-3),(scenario,recovery)
   if scenario==('write',7,'before'):assert recovery==0
   if recovery==-3:
    assert scenario==('write',1,'before')
    live_before_clear=tree(live);explicit=run('cancel-idle');assert explicit==0 and tree(live)==live_before_clear
    assert run('recover')==0
    assert all(not (apps/name).exists() for name in ('.install-demo','.backup-demo','.pending-demo','.committed-demo'))
   assert valid(live) or valid(apps/'.backup-demo'),('complete copies lost after recovery',scenario)
   if recovery==0:
    assert valid(live)
    assert all(not (apps/name).exists() for name in ('.install-demo','.backup-demo','.pending-demo','.committed-demo'))
  else:
   if scenario=='lock-busy':
    with (apps/'.store-lock').open('r+') as lock:
     fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);result=run();expected=-1
   else:result=run(mode)
   assert result==expected,(scenario,result,expected)
   if str(scenario).startswith('idle-'):
    assert (tree(live) if live.exists() else None)==old
    if result==0:assert not (apps/'.pending-demo').exists() and run('recover')==0
    else:assert tree(apps)==root_before
   elif result==0:
    assert valid(live) and tree(live)==tree(source)
    assert all(not (apps/name).exists() for name in ('.install-demo','.backup-demo','.pending-demo','.committed-demo'))
    assert run('recover')==0
   else:assert (tree(live) if live.exists() else None)==old
   if scenario in ('commit-repair-conflict','commit-repair-partial-backup'):assert tree(apps)==root_before
   if scenario=='unknown-stage':assert (apps/'.install-demo/keep').read_bytes()==b'KEEP'
   if scenario=='legacy-receipt':assert (apps/'.cleanup-demo').read_bytes()==b'v1 metadata must not be guessed'
  assert tree(source)==source_before and (base/'save.dat').read_bytes()==b'USER SAVE' and (apps/'unrelated.txt').read_bytes()==b'OTHER APP DATA'
  rows.append({'case':str(scenario),'result':result,'recovery_result':recovery,'explicit_idle_cancel_result':explicit,'source_save_unrelated_unchanged':True})
  if len(rows)==len(normal):print('Normal package scenarios passed; checking injected faults.',flush=True)
assert candidate()==before_candidate
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'install.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'manual_recovery_cases':sum(r['recovery_result']==-3 for r in rows),'explicit_idle_cancel_successes':sum(r['explicit_idle_cancel_result']==0 for r in rows),'candidate_version':version,'candidate_unchanged':True,'source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['Unified host local-package transaction only; no device app/store UI/network/archive implementation.','Malformed partially created metadata can require retained-state review; no automatic guessing.','Faults are host injected errors/process exits, not target FAT/physical power loss.','Source and managed tree must be quiescent; not an OS sandbox or publisher authentication.','ARM object compilation only; target libc/ABI, USB handoff, capacity and durability unqualified.']}
(ROOT/'sources/native-store-install-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Unified resource installation:',len(rows),'cases passed;',report['manual_recovery_cases'],'retained-state recoveries; ARM object compiled; candidate unchanged.')



