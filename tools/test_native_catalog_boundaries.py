"""Compare host catalog limits with actual ARM manifest parser on ordinary fixtures."""
from pathlib import Path
import hashlib,io,json,struct,sys,tempfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'runtime'))
from catalog import read_app
binary=(ROOT/'work/x1000-homebrew-frontend').read_bytes();elf=ELFFile(io.BytesIO(binary))
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
manifest_build=json.loads((ROOT/'work/native-frontend-build.json').read_text());assert hashlib.sha256(binary).hexdigest()==manifest_build['sha256']
candidate=ROOT/'work'/('integration-'+manifest_build['version'])/'external/HOMEBREW/launcher/app'
assert candidate.read_bytes()==binary
program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
def make(name='Demo',version='0.1.0',size=None):
 fields={'api':'1','id':'demo','name':name,'version':version,'target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
 raw=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
 if size:raw=raw.replace(b'bytes=96',b'bytes='+b'0'*(size-len(raw))+b'96');assert len(raw)==size
 return raw
cases=[('name48',make('a'*48),True),('name49',make('a'*49),False),('utf8-name48',make('中'*16),True),('utf8-name51',make('中'*17),False),('version32',make(version='0.1.0-'+'a'*26),True),('version33',make(version='0.1.0-'+'a'*27),False),('manifest1024',make(size=1024),True),('manifest1025',make(size=1025),False)]
cases.extend([('windows-CRLF',make().replace(b'\n',b'\r\n'),True),('bare-CR',make().replace(b'\n',b'\r'),False)])
rows=[];work=ROOT/'work/catalog-boundaries';work.mkdir(exist_ok=True)
for name,data,expected in cases:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);stop=0x60000100;fds={};nextfd=[10]
 files={'/fixture/apps/demo/app.ini':data,'/fixture/apps/demo/app':program}
 def text(p):return bytes(u.mem_read(p,256)).split(b'\0')[0].decode()
 def intr(uc,number,unused):
  pc=uc.reg_read(UC_ARM_REG_PC);nr=(struct.unpack('<I',uc.mem_read(pc-4,4))[0]&0xffffff)-0x900000
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if nr==85:result=-22
  elif nr==5:
   path=text(a[0]);assert path in files;result=nextfd[0];nextfd[0]+=1;fds[result]=[path,0]
  elif nr==3:
   fd=fds[a[0]];chunk=files[fd[0]][fd[1]:fd[1]+min(a[2],37)];fd[1]+=len(chunk);uc.mem_write(a[1],chunk);result=len(chunk)
  elif nr==19:assert a[2]==2;result=len(files[fds[a[0]][0]])
  elif nr==6:del fds[a[0]]
  else:raise AssertionError(nr)
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff)
 u.hook_add(UC_HOOK_INTR,intr);u.mem_write(0x60001000,b'/fixture/apps\0');u.mem_write(0x60001100,b'demo\0')
 for reg,value in ((UC_ARM_REG_R0,0x60001000),(UC_ARM_REG_R1,0x60001100),(UC_ARM_REG_R2,0x60002000),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(symbols['manifest'],stop,count=200000);assert u.reg_read(UC_ARM_REG_PC)==stop and not fds
 arm_ok=u.reg_read(UC_ARM_REG_R0)==0
 with tempfile.TemporaryDirectory(dir=work) as folder:
  app=Path(folder)/'demo';app.mkdir();(app/'app.ini').write_bytes(data);(app/'app').write_bytes(program)
  try:read_app(app);host_ok=True
  except ValueError:host_ok=False
 assert arm_ok==host_ok==expected,(name,arm_ok,host_ok)
 rows.append({'case':name,'manifest_bytes':len(data),'ARM_accepts':arm_ok,'host_accepts':host_ok})
report={'all_passed':True,'physical_device_access':False,'frontend_sha256':hashlib.sha256(binary).hexdigest(),'host_catalog_sha256':hashlib.sha256((ROOT/'runtime/catalog.py').read_bytes()).hexdigest(),'cases':rows,'limits':['Actual compiled ARM manifest function with virtual ordinary-file syscalls; host reference uses temporary local files.','Agreement covers tested byte limits only, not complete parser equivalence or valid executable ABI.','Synthetic96-byte ELF header is a parser fixture and is never executed.']}
(ROOT/'sources/native-catalog-boundary-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

