"""Run C installer against ordinary temporary directories inside project work/."""
from pathlib import Path
import fcntl,hashlib,json,shutil,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-fs-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/fs_posix.c','runtime/store/transaction.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_store_fs_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',area/'manifest.json']+[area/x['path'] for x in json.loads((area/'manifest.json').read_text())['files']]
def snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=snapshot();cases=[]
def make(folder,revision):
 folder.mkdir(exist_ok=True)
 b=bytearray(96);b[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',b,16,2,40);b[-1]=revision
 (folder/'app').write_bytes(b)
 fields={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(b).hexdigest()}
 (folder/'app.ini').write_text('\n'.join(k+'='+v for k,v in fields.items())+'\n')
 return bytes(b)
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
 base=Path(temp).resolve();assert base.parent==work
 apps=base/'apps';source=base/'package';outside=base/'data';apps.mkdir();outside.mkdir()
 (outside/'save.dat').write_bytes(b'PRESERVE USER SAVE');(apps/'unrelated.txt').write_bytes(b'PRESERVE OTHER DATA')
 old=make(source,1)
 def run(name,expected=0,mode='apply',space='normal',root=None):
  p=subprocess.run([str(work/'driver'),str(root or apps),str(source),'demo',space,mode],capture_output=True,text=True,check=True,timeout=10)
  actual=int(p.stdout.strip());assert actual==expected,(name,actual,expected)
  assert (outside/'save.dat').read_bytes()==b'PRESERVE USER SAVE' and (apps/'unrelated.txt').read_bytes()==b'PRESERVE OTHER DATA'
  cases.append({'case':name,'result':actual,'unrelated_data_unchanged':True})
 run('first-install');assert (apps/'demo/app').read_bytes()==old
 new=make(source,2);run('update');assert (apps/'demo/app').read_bytes()==new
 assert not (apps/'.backup-demo').exists() and not (apps/'.install-demo').exists()
 (source/'app').write_bytes(b'corrupt');run('bad-source-hash',-5);assert (apps/'demo/app').read_bytes()==new
 make(source,3);run('space-reserve-unavailable',-4,space='full');assert (apps/'demo/app').read_bytes()==new
 run('cancel-before-write',-2,mode='cancel');assert (apps/'demo/app').read_bytes()==new
 (source/'asset.dat').write_bytes(b'not silently skipped');run('extra-resource-rejected',-5);(source/'asset.dat').unlink()
 (source/'app').unlink();(source/'app').symlink_to(apps/'demo/app');run('source-symlink-rejected',-5);(source/'app').unlink();make(source,3)
 (apps/'demo').rename(apps/'.backup-demo');run('restore-backup',mode='recover');assert (apps/'demo/app').read_bytes()==new
 shutil.copytree(apps/'demo',apps/'.backup-demo');run('finish-committed-cleanup',mode='recover');assert not (apps/'.backup-demo').exists()
 stage=apps/'.install-demo';stage.mkdir();(stage/'app.ini').write_bytes(b'partial');run('discard-partial-stage',mode='recover');assert not stage.exists()
 stage.symlink_to(outside,target_is_directory=True);run('stage-symlink-not-traversed',-3,mode='recover');assert stage.is_symlink();stage.unlink()
 alias=base/'alias';alias.symlink_to(apps,target_is_directory=True);run('root-symlink-rejected',-100,root=alias);alias.unlink()
 with (apps/'.store-lock').open('r+') as locked:
  fcntl.flock(locked,fcntl.LOCK_EX|fcntl.LOCK_NB);run('concurrent-install-rejected',-1)
 assert (apps/'demo/app').read_bytes()==new
assert before==snapshot()
report={'all_passed':True,'physical_device_access':False,'cases':cases,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources[:4]},'candidate_version':version,'candidate_unchanged':True,'limits':['Real host files/rename/fsync/flock in project work fixtures, not target FAT, flash or physical USB.','Profile accepts exactly app.ini and app; resources/archives and publisher authentication remain unimplemented.','Not linked into ARM candidate; POSIX/libc/flock/fsync behavior on Sony requires independent qualification.','No real I/O error, storage-full or power-cut injection; low-space case uses an intentionally unavailable reserve.','Filesystem root confinement is an adapter contract, not a sandbox against other processes.']}
(ROOT/'sources/native-store-filesystem-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('C filesystem adapter:',len(cases),'cases passed; candidate unchanged.')
