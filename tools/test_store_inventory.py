"""C resource inventory parser/binding/hash tests; no installation or device access."""
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=(ROOT/'work/store-inventory-tests').resolve();work.mkdir(exist_ok=True)
sources=['runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/test_store_inventory_driver.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'driver')],cwd=ROOT,check=True)
program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
fields={'api':'1','id':'demo','name':'Demo','version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
manifest=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
base={'app':program,'app.ini':manifest,'assets/theme.dat':b'theme data','empty.dat':b''}
def line(path,data=b'',size=None):return hashlib.sha256(data).hexdigest().encode()+b' '+str(len(data) if size is None else size).encode()+b' '+path.encode()+b'\n'
def inventory(files):return b'HBFILES1\n'+b''.join(line(p,d) for p,d in sorted(files.items()))
valid=inventory(base);cases=[('valid',valid,0,None),('CRLF',valid.replace(b'\n',b'\r\n'),0,None),('no-final-newline',valid[:-1],-1,None),('bad-header',valid.replace(b'HBFILES1',b'HBFILES2'),-1,None),('traversal',valid+line('../outside'),-1,None),('absolute-path',valid+line('/tmp/outside'),-1,None),('backslash',valid+line('assets\\other'),-1,None),('drive-path',valid+line('c:other'),-1,None),('empty-component',valid+line('z//file'),-1,None),('dot-component',valid+line('z/./file'),-1,None),('trailing-dot',valid+line('z/file.'),-1,None),('reserved-name',valid+line('z/CON.txt'),-1,None),('reserved-device',valid+line('z/com1.bin'),-1,None),('case-duplicate',b'HBFILES1\n'+line('APP',program)+valid.split(b'\n',1)[1],-1,None),('file-directory-conflict',valid.replace(line('assets/theme.dat',base['assets/theme.dat']),line('assets')+line('assets/theme.dat',base['assets/theme.dat'])),-1,None),('directory-case-conflict',valid.replace(line('assets/theme.dat',base['assets/theme.dat']),line('Assets/one')+line('assets/theme.dat',base['assets/theme.dat'])),-1,None),('self-inventory',valid+line('files.sha256'),-1,None),('case-self-inventory',b'HBFILES1\n'+line('FILES.SHA256')+valid.split(b'\n',1)[1],-1,None),('unsorted',b'HBFILES1\n'+b''.join(reversed(valid.splitlines(keepends=True)[1:])),-1,None),('missing-app',inventory({k:v for k,v in base.items() if k!='app'}),-1,None),('bad-size',valid.replace(b' 96 app\n',b' 99999999999999999999 app\n'),-1,None),('leading-zero-size',valid.replace(b' 96 app\n',b' 096 app\n'),-1,None),('bad-hash',valid.replace(valid[9:10],b'G',1),-1,None),('manifest-binding',valid.replace(hashlib.sha256(manifest).hexdigest().encode(),b'0'*64),-5,None),('app-binding',valid.replace(hashlib.sha256(program).hexdigest().encode(),b'0'*64),-5,None),('changed-resource',valid,-5,('assets/theme.dat',b'THEME DATA')),('short-resource',valid,-3,('assets/theme.dat',b'x')),('long-resource',valid,-3,('assets/theme.dat',b'theme dataX')),('nonempty-empty-file',valid,-3,('empty.dat',b'x'))]
allowed=dict(base);allowed['z/com10.bin']=b'not a Windows device'
path160='a'*60+'/'+'b'*60+'/'+'c'*38
longpath=dict(base);longpath[path160]=b'long path'
cases.extend([('reserved-prefix-allowed',inventory(allowed),0,('z/com10.bin',allowed['z/com10.bin'])),('path160',inventory(longpath),0,(path160,b'long path')),('path161',valid+line(path160+'c'),-1,None),('file-too-large',valid+line('z/large',size=134217729),-1,None),('total-too-large',valid+line('z/large1',size=134217728)+line('z/large2',size=134217728),-1,None),('inventory-text-too-large',valid+b'X'*(32769-len(valid)-1)+b'\n',-1,None)])
rows=[]
for name,text,expected,mutation in cases:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  folder=Path(temp).resolve();assert folder.parent==work
  for path,data in base.items():
   out=folder/path;out.parent.mkdir(exist_ok=True,parents=True);out.write_bytes(data)
  (folder/'files.sha256').write_bytes(text)
  if mutation:
   changed=folder/mutation[0];changed.parent.mkdir(exist_ok=True,parents=True);changed.write_bytes(mutation[1])
  p=subprocess.run([str(work/'driver'),str(folder)],capture_output=True,text=True,check=True,timeout=5)
  result=int(p.stdout.strip());assert result==expected,(name,result,expected)
  rows.append({'case':name,'result':result})
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',sources[0],'-o',str(work/'inventory.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'inventory_source_sha256':hashlib.sha256((ROOT/sources[0]).read_bytes()).hexdigest(),'limits':['Host C parser/hash/binding execution plus ARM object compilation, not a device app.','Inventory does not authenticate a publisher or reject undeclared on-disk files by itself; filesystem traversal/integration remains pending.','Resource-capable copying/transaction recovery is not integrated; existing POSIX adapter remains two-file-only.','Synthetic ELF header is a fixture, never executed.']}
(ROOT/'sources/native-store-inventory-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('C inventory:',len(rows),'cases passed; ARM object compiled.')

