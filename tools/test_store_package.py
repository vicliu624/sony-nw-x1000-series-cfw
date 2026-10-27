"""Test C manifest/program validation using ordinary host fixtures; compile ARM objects."""
from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-package-tests';work.mkdir(exist_ok=True)
program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
def manifest(payload=program,**changes):
 fields={'api':'1','id':'demo','name':'Demo','version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':str(len(payload)),'sha256':hashlib.sha256(payload).hexdigest()};fields.update(changes)
 return ('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
def padded(size):
 raw=manifest();return raw.replace(b'bytes=96',b'bytes='+b'0'*(size-len(raw))+b'96')
wrong=bytearray(program);wrong[18]=3;wrong=bytes(wrong)
corrupt=bytearray(program);corrupt[-1]=1
cases=[('valid',manifest(),program,0),('CRLF',manifest().replace(b'\n',b'\r\n'),program,0),('bare-CR',manifest().replace(b'\n',b'\r'),program,-1),('no-final-LF',manifest().rstrip(b'\n'),program,0),('name48',manifest(name='a'*48),program,0),('name49',manifest(name='a'*49),program,-1),('UTF8-name48',manifest(name='中'*16),program,0),('UTF8-name51',manifest(name='中'*17),program,-1),('version32',manifest(version='0.1.0-'+'a'*26),program,0),('version33',manifest(version='0.1.0-'+'a'*27),program,-1),('manifest1024',padded(1024),program,0),('manifest1025',padded(1025),program,-1),('embedded-NUL',manifest().replace(b'Demo',b'De\0mo'),program,-1),('wrong-target',manifest(target='sony-a918'),program,-1),('wrong-id',manifest(id='other'),program,-1),('duplicate',manifest()+b'api=1\n',program,-1),('unknown-field',manifest()+b'other=1\n',program,-1),('bad-hash-format',manifest(sha256='G'*64),program,-1),('program-too-small',manifest(bytes='83'),program,-1),('size-overflow',manifest(bytes='999999999999999999999'),program,-1),('truncated-program',manifest(),program[:-1],-3),('extended-program',manifest(),program+b'X',-3),('corrupted-program',manifest(),bytes(corrupt),-5),('wrong-ELF-machine',manifest(wrong),wrong,-4)]
sources=['runtime/store/package.c','runtime/native/sha256.c','tools/test_store_package_driver.c']
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'validator')],cwd=ROOT,check=True)
rows=[]
for name,data,payload,expected in cases:
 (work/'app.ini').write_bytes(data);(work/'app').write_bytes(payload)
 p=subprocess.run([str(work/'validator'),str(work/'app.ini'),str(work/'app'),'demo'],capture_output=True,text=True,check=True,timeout=5)
 actual=int(p.stdout.strip());assert actual==expected,(name,actual,expected)
 rows.append({'case':name,'result':actual})
for source in sources[:2]:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',source,'-o',str(work/(Path(source).stem+'.arm.o'))],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'cases':rows,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources[:2]},'limits':['C functions execute on host with partial ordinary-file reads; ARM object compile only.','Checks app.ini and main app executable; asset inventory/archive integrity/authorship and filesystem confinement remain separate.','ELF class/endian/machine/type checks do not qualify Sony ABI or executable behavior.','No store UI, filesystem transaction adapter, device execution or integration-candidate changes.']}
(ROOT/'sources/native-store-package-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('C package validation:',len(rows),'cases passed; ARM objects compiled.')
