"""Read-only C bundle traversal/verification on host work fixtures."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-bundle-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_store_bundle_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
fields={'api':'1','id':'demo','name':'Demo','version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
manifest=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
def index(files):return b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
names=['legacy','resources','extra-file','extra-directory','missing-resource','changed-resource','resource-symlink','directory-symlink','resource-hardlink','index-symlink','missing-index','wrong-index','manifest-binding','root-alias','cancel','depth16','depth17','file-count128']
rows=[]
for name in names:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp).resolve();assert base.parent==work
  folder=base/'package';folder.mkdir();outside=base/'outside';outside.mkdir();(outside/'sentinel').write_bytes(b'KEEP')
  files={'app':program,'app.ini':manifest}
  if name!='legacy':files.update({'assets/theme.dat':b'color theme','fonts/font.bin':b'font bytes','empty.dat':b''})
  if name in ('depth16','depth17'):files['/'.join(['d']*(16 if name=='depth16' else 17))+'/file.dat']=b'deep'
  if name=='file-count128':files.update({f'resources/r{i:03d}.dat':b'' for i in range(128-len(files))})
  for path,data in files.items():
   target=folder/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  if name!='legacy':(folder/'files.sha256').write_bytes(index(files))
  expected=0
  if name=='extra-file':(folder/'extra.dat').write_bytes(b'extra');expected=-1
  elif name=='extra-directory':(folder/'foreign').mkdir();expected=-1
  elif name=='missing-resource':(folder/'assets/theme.dat').unlink();expected=-1
  elif name=='changed-resource':(folder/'assets/theme.dat').write_bytes(b'COLOR THEME');expected=-5
  elif name=='resource-symlink':
   (folder/'assets/theme.dat').unlink();(folder/'assets/theme.dat').symlink_to(outside/'sentinel');expected=-1
  elif name=='directory-symlink':
   (folder/'assets/theme.dat').unlink();(folder/'assets').rmdir();(folder/'assets').symlink_to(outside,target_is_directory=True);expected=-1
  elif name=='resource-hardlink':
   (folder/'assets/theme.dat').unlink();os.link(outside/'sentinel',folder/'assets/theme.dat');expected=-1
  elif name=='index-symlink':
   (folder/'files.sha256').unlink();(folder/'files.sha256').symlink_to(outside/'sentinel');expected=-2
  elif name=='missing-index':(folder/'files.sha256').unlink();expected=-1
  elif name=='wrong-index':(folder/'files.sha256').write_bytes(b'wrong\n');expected=-1
  elif name=='manifest-binding':
   (folder/'app.ini').write_bytes(manifest.replace(b'name=Demo',b'name=Other'));expected=-5
  elif name=='depth17':expected=-1
  root=folder
  if name=='root-alias':root=base/'alias';root.symlink_to(folder,target_is_directory=True);expected=-2
  if name=='cancel':expected=-2
  def snapshot():
   return {str(p.relative_to(base)):'link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in base.rglob('*')}
  before=snapshot()
  p=subprocess.run([str(work/'driver'),str(root),'cancel' if name=='cancel' else 'check'],capture_output=True,text=True,check=True,timeout=10)
  result,bound,count=map(int,p.stdout.split());assert result==expected,(name,result,expected)
  assert snapshot()==before and (outside/'sentinel').read_bytes()==b'KEEP'
  if not result:assert bound>=sum(map(len,files.values())) and count==len(files)
  rows.append({'case':name,'result':result,'allocation_bound_4096':bound,'listed_files':count,'entire_fixture_unchanged':True})
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'bundle.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'bundle_source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['Read-only real host directories; ARM object compile only, no target ABI qualification.','Allocation estimate uses provided4096-byte unit, excludes transaction receipts/rollback metadata and is not an observed device capacity.','Source tree must remain unchanged during validation; no sandbox against concurrent malicious modifications.','Resource copying, commit receipts and recovery are not integrated; existing installer still rejects resource packages.']}
(ROOT/'sources/native-store-bundle-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Read-only C bundle validation:',len(rows),'cases passed; ARM object compiled.')
