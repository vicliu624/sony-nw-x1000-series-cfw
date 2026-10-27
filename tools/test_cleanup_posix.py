"""Resource backup subset-check/deletion/restart tests on host work fixtures."""
from pathlib import Path
import hashlib,json,os,shutil,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-cleanup-posix-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/cleanup_posix.c','runtime/store/cleanup_plan.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_cleanup_posix_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','tools/store_fs_faults.c','-ldl','-o',str(work/'faults.so')],cwd=ROOT,check=True)
def index(files):return b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
def make(folder,revision,resources=True):
 folder.mkdir();b=bytearray(96);b[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',b,16,2,40);b[-1]=revision;b=bytes(b)
 f={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(b).hexdigest()}
 files={'app':b,'app.ini':('\n'.join(k+'='+v for k,v in f.items())+'\n').encode()}
 if resources:files.update({'assets/theme.dat':b'theme '+str(revision).encode(),'fonts/ui/a.bin':b'font','empty.dat':b''})
 for name,data in files.items():
  p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 if resources:(folder/'files.sha256').write_bytes(index(files))
 return files
def tree(folder):return {str(p.relative_to(folder)):'link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in folder.rglob('*')}
scenarios=['complete','missing-manifest','only-index','empty-backup','backup-absent','legacy-old','legacy-new','changed-old','foreign-file','foreign-directory','file-link','directory-link','backup-link','valid-live-changed','bad-receipt','cancel']
faults=[('unlink',n,mode) for n in (1,3,6) for mode in ('before','after','exit')]+[('rmdir',1,mode) for mode in ('before','after','exit')]+[('fsync',1,mode) for mode in ('before','after','exit')]
rows=[]
for scenario in scenarios+faults:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  apps=base/'apps';apps.mkdir();(apps/'.store-lock').write_bytes(b'');backup=apps/'.backup-demo';live=apps/'demo'
  oldfiles=make(backup,1,scenario!='legacy-old');newfiles=make(live,2,scenario!='legacy-new')
  (base/'save.dat').write_bytes(b'PRESERVE SAVE');receipt=apps/'.cleanup-demo-v2'
  def run(mode,env=None,exit_code=0):
   p=subprocess.run([str(work/'driver'),mode,str(apps),str(receipt)],capture_output=True,text=True,env=env,timeout=10)
   assert p.returncode==exit_code,(scenario,p.returncode,p.stdout,p.stderr)
   return None if exit_code else int(p.stdout.strip())
  assert run('plan')==0;receipt_before=receipt.read_bytes();live_before=tree(live)
  refusal=False
  if scenario=='missing-manifest':(backup/'app.ini').unlink()
  elif scenario in ('only-index','empty-backup'):
   for path in oldfiles:(backup/path).unlink()
   if scenario=='empty-backup':(backup/'files.sha256').unlink()
  elif scenario=='backup-absent':shutil.rmtree(backup)
  elif scenario=='changed-old':(backup/'assets/theme.dat').write_bytes(b'THEME 1');refusal=True
  elif scenario=='foreign-file':(backup/'foreign.dat').write_bytes(b'KEEP');refusal=True
  elif scenario=='foreign-directory':(backup/'foreign').mkdir();refusal=True
  elif scenario=='file-link':(backup/'assets/theme.dat').unlink();(backup/'assets/theme.dat').symlink_to(base/'save.dat');refusal=True
  elif scenario=='directory-link':
   (backup/'assets/theme.dat').unlink();(backup/'assets').rmdir();(backup/'assets').symlink_to(base,target_is_directory=True);refusal=True
  elif scenario=='backup-link':
   shutil.rmtree(backup);backup.symlink_to(base,target_is_directory=True);refusal=True
  elif scenario=='valid-live-changed':
   (live/'assets/theme.dat').write_bytes(b'other valid theme');newfiles['assets/theme.dat']=b'other valid theme';(live/'files.sha256').write_bytes(index(newfiles));live_before=tree(live);refusal=True
  elif scenario=='bad-receipt':
   data=bytearray(receipt.read_bytes());data[-1]^=1;receipt.write_bytes(data);receipt_before=bytes(data);refusal=True
  elif scenario=='cancel':refusal=True
  if isinstance(scenario,tuple):
   operation,nth,mode=scenario
   env=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(apps),HB_TEST_OPERATION=operation,HB_TEST_NTH=str(nth),HB_TEST_MODE=mode)
   result=run('clean',env,90 if mode=='exit' else 0)
   if mode!='exit':assert result!=0,('fault not observed',scenario)
   assert tree(live)==live_before and receipt.read_bytes()==receipt_before
   assert run('check')==0 and run('clean')==0 and not backup.exists()
  elif refusal:
   before=tree(apps);result=run('cancel' if scenario=='cancel' else 'clean');assert result!=0
   assert tree(apps)==before
  else:
   before=tree(apps);assert run('check')==0 and tree(apps)==before
   assert run('clean')==0 and not backup.exists();assert run('clean')==0
  assert tree(live)==live_before and receipt.read_bytes()==receipt_before and (base/'save.dat').read_bytes()==b'PRESERVE SAVE'
  rows.append({'case':str(scenario),'refused_without_mutation':refusal,'backup_removed':not backup.exists(),'live_receipt_save_unchanged':True})
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'cleanup.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['Host resource-backup checking/deletion and injected errors/process exits only. No target FAT/power-loss qualification.','Caller must hold transaction lock, provide verified receipt and keep managed trees quiescent.','Helper retains receipt and never activates/modifies live app. It is not integrated with installer commit/rollback.','No store UI, downloader or device app execution.']}
(ROOT/'sources/native-store-cleanup-posix-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Resource backup cleanup:',len(rows),'cases passed; ARM object compiled.')
