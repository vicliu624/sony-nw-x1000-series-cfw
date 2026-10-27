"""C resource cleanup receipt codec/identity tests; no installer activation."""
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-cleanup-plan-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/cleanup_plan.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_cleanup_plan_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
def index(files):return b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'.encode() for name,data in sorted(files.items()))
def make(folder,revision,resources):
 folder.mkdir();b=bytearray(96);b[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',b,16,2,40);b[-1]=revision;b=bytes(b)
 fields={'api':'1','id':'demo','name':'Demo','version':f'0.1.{revision}','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(b).hexdigest()}
 files={'app':b,'app.ini':('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()}
 if resources:files['assets/theme.dat']=b'theme';files['empty.dat']=b''
 if resources==128:files.update({f'resources/r{i:03d}.dat':b'' for i in range(128-len(files))})
 for name,data in files.items():
  path=folder/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(data)
 if resources:(folder/'files.sha256').write_bytes(index(files))
 return files
def identity(folder):
 exists=(folder/'files.sha256').exists();raw=(folder/'files.sha256').read_bytes() if exists else b''
 return hashlib.sha256(b'HBPKG001'+hashlib.sha256((folder/'app.ini').read_bytes()).digest()+hashlib.sha256((folder/'app').read_bytes()).digest()+bytes([int(exists)])+struct.pack('<I',len(raw))+(hashlib.sha256(raw).digest() if exists else bytes(32))).digest()
rows=[]
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
 base=Path(temp).resolve();assert base.parent==work
 new=base/'new';newfiles=make(new,2,True);receipt=base/'receipt.bin'
 def run(mode,old,expected,name):
  result=subprocess.run([str(work/'driver'),mode,str(old),str(new),str(receipt)],capture_output=True,text=True,check=True,timeout=10)
  actual=int(result.stdout.strip());assert actual==expected,(name,actual,expected)
  rows.append({'case':name,'result':actual})
 for resource_kind in (0,True,128):
  old=base/('old-'+str(resource_kind));files=make(old,1,resource_kind)
  run('encode',old,0,'roundtrip-'+str(resource_kind));data=receipt.read_bytes()
  assert data[:8]==b'HBCLN002' and data[8:41]==b'demo'+bytes(29) and data[41:73]==identity(new)
  assert hashlib.sha256(data[:-32]).digest()==data[-32:]
  has=bool(resource_kind);raw=(old/'files.sha256').read_bytes() if has else b''
  assert data[73]==int(has) and struct.unpack_from('<I',data,74)[0]==len(raw)
  assert data[78:110]==(hashlib.sha256(raw).digest() if has else bytes(32))
  count=struct.unpack_from('<H',data,110)[0];cursor=112;decoded={}
  for _ in range(count):
   length=data[cursor];cursor+=1;path=data[cursor:cursor+length].decode();cursor+=length
   size=struct.unpack_from('<I',data,cursor)[0];cursor+=4;digest=data[cursor:cursor+32];cursor+=32
   decoded[path]=(size,digest)
  assert cursor==len(data)-32 and decoded=={p:(len(d),hashlib.sha256(d).digest()) for p,d in files.items()}
  run('match',old,0,'match-'+str(resource_kind))
 old=base/'old-True';run('encode',old,0,'fresh-resource-receipt');good=receipt.read_bytes()
 def changed(name,mutate,expected,checksum=True):
  data=bytearray(good);mutate(data)
  if checksum:data[-32:]=hashlib.sha256(data[:-32]).digest()
  receipt.write_bytes(data);run('decode',old,expected,name)
 changed('bad-checksum',lambda d:d.__setitem__(-1,d[-1]^1),-5,False)
 changed('bad-magic',lambda d:d.__setitem__(0,ord('X')),-5)
 changed('wrong-id',lambda d:d.__setitem__(8,ord('x')),-5)
 changed('invalid-profile',lambda d:d.__setitem__(73,2),-1)
 changed('legacy-resource-mismatch',lambda d:(d.__setitem__(73,0),d.__setitem__(slice(74,110),bytes(36))),-1)
 changed('index-size-overflow',lambda d:struct.pack_into('<I',d,74,32769),-1)
 changed('file-count-overflow',lambda d:struct.pack_into('<H',d,110,129),-1)
 changed('traversal-path',lambda d:d.__setitem__(slice(113,116),b'../'),-1)
 changed('NUL-path',lambda d:d.__setitem__(114,0),-1)
 changed('noncanonical-app-name',lambda d:d.__setitem__(slice(113,116),b'APP'),-1)
 changed('program-size-too-small',lambda d:struct.pack_into('<I',d,116,0),-1)
 changed('program-size-overflow',lambda d:struct.pack_into('<I',d,116,134217729),-1)
 receipt.write_bytes(good+b'X');run('decode',old,-5,'trailing-byte')
 receipt.write_bytes(good[:-1]);run('decode',old,-5,'truncated')
 receipt.write_bytes(good[:64]);run('decode',old,-1,'short-header')
 receipt.write_bytes(bytes(25361));run('decode',old,-1,'oversize-record')
 run('small',old,-3,'insufficient-output-capacity')
 receipt.write_bytes(good)
 (new/'assets/theme.dat').write_bytes(b'new theme');newfiles['assets/theme.dat']=b'new theme';(new/'files.sha256').write_bytes(index(newfiles))
 run('match',old,-5,'changed-valid-resource-bundle')
 (new/'assets/theme.dat').write_bytes(b'theme');newfiles['assets/theme.dat']=b'theme';(new/'files.sha256').write_bytes(index(newfiles).replace(b'\n',b'\r\n'))
 run('match',old,-5,'changed-index-representation')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'cleanup-plan.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['C codec/identity and host read-only bundle checks only; resource commit/recovery is not wired into existing installer.','HBCLN002 checksum is not a signature; verified bundles and trusted transaction ownership remain caller preconditions.','No target FAT, power-loss, process/USB lifecycle or linked ARM application validation.','Active two-file adapter still uses HBCLN001; no deployed metadata migrated.']}
(ROOT/'sources/native-store-cleanup-plan-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Resource cleanup plan:',len(rows),'checks passed; ARM object compiled.')
