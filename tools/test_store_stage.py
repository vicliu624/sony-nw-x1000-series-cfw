"""C bundle staging tests on project work fixtures; no activation/device writes."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-stage-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/stage_posix.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_store_stage_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared','tools/store_fs_faults.c','-ldl','-o',str(work/'faults.so')],cwd=ROOT,check=True)
program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
fields={'api':'1','id':'demo','name':'Demo','version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
manifest=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
names=['legacy','resources','nested16','long-path','bad-resource','undeclared-file','source-link','cancel','space','existing-stage','stage-link','parent-alias','overlap','write-index-error','write-program-error','process-interrupted']
rows=[]
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',area/'manifest.json']+[area/f['path'] for f in json.loads((area/'manifest.json').read_text())['files']]
def candidate():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=candidate()
for name in names:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  source=base/'package';parent=base/'apps';source.mkdir();parent.mkdir()
  live=parent/'demo';live.mkdir();(live/'app').write_bytes(b'CURRENT VERSION MUST SURVIVE')
  save=base/'save.dat';save.write_bytes(b'SAVE MUST SURVIVE')
  if name=='overlap':source=parent/'package';source.mkdir()
  files={'app':program,'app.ini':manifest}
  if name!='legacy':files.update({'assets/theme.dat':b'theme bytes','fonts/ui/font.bin':b'font bytes','empty.dat':b''})
  if name=='nested16':files['/'.join(['d']*16)+'/deep.dat']=b'deep'
  if name=='long-path':files['a'*60+'/'+'b'*60+'/'+'c'*38]=b'long'
  for path,data in files.items():
   out=source/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
  if name!='legacy':
   index=b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
   (source/'files.sha256').write_bytes(index);files['files.sha256']=index
  expected=0;stage=parent/'.install-demo';mode='normal';environment=None;actual_parent=parent
  if name=='bad-resource':(source/'assets/theme.dat').write_bytes(b'changed');expected=-27
  elif name=='undeclared-file':(source/'extra').write_bytes(b'extra');expected=-27
  elif name=='source-link':
   (source/'assets/theme.dat').unlink();(source/'assets/theme.dat').symlink_to(save);expected=-27
  elif name=='cancel':mode='cancel';expected=-23
  elif name=='space':mode='full';expected=-22
  elif name=='existing-stage':stage.mkdir();(stage/'keep').write_bytes(b'KEEP STAGE');expected=-26
  elif name=='stage-link':stage.symlink_to(live,target_is_directory=True);expected=-26
  elif name=='parent-alias':actual_parent=base/'alias';actual_parent.symlink_to(parent,target_is_directory=True);expected=-20
  elif name=='overlap':expected=-20
  elif name in ('write-index-error','write-program-error','process-interrupted'):
   environment=dict(os.environ,LD_PRELOAD=str(work/'faults.so'),HB_TEST_ROOT=str(parent),HB_TEST_OPERATION='write',HB_TEST_NTH='1' if name=='write-index-error' else '2' if name=='write-program-error' else '3',HB_TEST_MODE='exit' if name=='process-interrupted' else 'before')
   expected='interrupted' if name=='process-interrupted' else -21
  def snapshot(folder):
   return {str(p.relative_to(folder)):'link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in folder.rglob('*')}
  source_before=snapshot(source)
  p=subprocess.run([str(work/'driver'),str(source),str(actual_parent),mode],capture_output=True,text=True,env=environment,timeout=15)
  if expected=='interrupted':assert p.returncode==90,(name,p.returncode,p.stdout,p.stderr);result='interrupted'
  else:assert p.returncode==0,p.stderr;result=int(p.stdout.strip());assert result==expected,(name,result,expected)
  assert snapshot(source)==source_before
  assert (live/'app').read_bytes()==b'CURRENT VERSION MUST SURVIVE' and save.read_bytes()==b'SAVE MUST SURVIVE'
  assert not (parent/'.backup-demo').exists()
  if result==0:
   assert {str(f.relative_to(stage)):f.read_bytes() for f in stage.rglob('*') if f.is_file()}==files
  if name=='existing-stage':assert (stage/'keep').read_bytes()==b'KEEP STAGE'
  rows.append({'case':name,'result':result,'source_unchanged':True,'live_and_save_unchanged':True,'activated':False,'stage_exists_after':stage.exists()})
assert before==candidate()
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'stage.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'candidate_version':version,'candidate_unchanged':True,'source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['Real host staging copy/fsync and injected failures/process exit, not target FAT or physical power loss.','Failures can leave inactive partial stage. Resource commit/cleanup/recovery is not integrated.','Source/parent must be quiescent; no sandbox against malicious concurrent changes.','No archive extraction, publisher authentication, app execution or store UI.','ARM object compile only; target libc/ABI and durability remain unqualified.']}
(ROOT/'sources/native-store-stage-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('C bundle staging:',len(rows),'cases passed; ARM object compiled; candidate unchanged.')

