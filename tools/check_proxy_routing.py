"""Replay original sysmgrd command selection with simulated libc copy helpers only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes();assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
e=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value']for s in e.get_section_by_name('.dynsym').iter_symbols()}
def cstring(u,p):
 out=bytearray()
 for i in range(1024):
  c=u.mem_read(p+i,1)[0]
  if not c:return out.decode()
  out.append(c)
 raise ValueError('unterminated')
rows=[]
for id in [1,2,0x20001,0x20002,0x30001]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x1000);u.mem_map(0x60000000,0x20000)
 entry=bytearray(0x510);struct.pack_into('<I',entry,0,id);entry[4:4+len(b'/contents/HOMEBREW/launcher/app\0')]=b'/contents/HOMEBREW/launcher/app\0';u.mem_write(0x60010000,bytes(entry))
 u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,0x60010000);u.reg_write(UC_ARM_REG_R2,0);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 def hook(uc,pc,size,data):
  if pc==syms['memcpy']:
   dst,src,n=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]];uc.mem_write(dst,bytes(uc.mem_read(src,n)));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  elif pc==0x1b3c8:
   dst,n,src=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]];s=cstring(uc,src).encode()+b'\0';assert len(s)<=n;uc.mem_write(dst,s);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x10f64,0x50000000,count=10000)
 ptr=u.reg_read(UC_ARM_REG_R0);argv=[]
 for i in range(4):
  p=struct.unpack('<I',u.mem_read(ptr+i*4,4))[0]
  if not p:break
  argv.append(cstring(u,p))
 expect_proxy=id>>16==3;assert (argv[0]=='appproxy')==expect_proxy
 rows.append({'application_id':hex(id),'argv':argv,'uses_proxy':expect_proxy})
result={'scope':'original makeExecCommand instructions; copy helpers mocked; no exec or hardware','rows':rows,'conclusion':'Only ID class 0x0003xxxx selects appproxy. Class 0 and 0x0002xxxx run configured executable directly.'}
(ROOT/'sources/native-proxy-routing.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
