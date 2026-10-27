"""Execute stock SID formatting and SWD loader through its file-open boundary."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
rows=[]
for sid,expected in [(34700,'347-00'),(99999,'999-99')]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x780000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x20000);sp=0x50018000;context=0x50002000
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def string(a):
  b=bytearray()
  for n in range(400):
   c=bytes(u.mem_read(a+n,1))
   if c==b'\0':return b.decode()
   b.extend(c)
  raise AssertionError('unterminated')
 global_pointer=word(0xec448);u.mem_write(global_pointer,struct.pack('<I',context));opened=[]
 def hook(uc,pc,size,_):
  if pc==0xd9a0:
   fmt=string(uc.reg_read(UC_ARM_REG_R2));assert fmt=='/usr/local/share/gemini/res/swd/ucs2-dev-sid-%03d-%02d.swd'
   a=uc.reg_read(UC_ARM_REG_R3);b=word(uc.reg_read(UC_ARM_REG_SP));text=(fmt%(a,b)).encode();assert (a,b)==divmod(sid,100)
   uc.mem_write(uc.reg_read(UC_ARM_REG_R0),text+b'\0');uc.reg_write(UC_ARM_REG_R0,len(text))
  elif pc==0xd574:
   uc.mem_write(uc.reg_read(UC_ARM_REG_R0),bytes([uc.reg_read(UC_ARM_REG_R1)&255])*uc.reg_read(UC_ARM_REG_R2))
  elif pc==0xe09c:
   path=string(uc.reg_read(UC_ARM_REG_R0));assert path.endswith(expected+'.swd') and uc.reg_read(UC_ARM_REG_R1)==0
   opened.append(path);uc.emu_stop();return
  else:return
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,sid);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
 u.emu_start(0x10a544,0x50019000,count=1000);assert len(opened)==1
 rows.append({'sid':sid,'read_only_open_attempt':opened[0]})
report={'passed':True,'scope':'Actual stock numeric SID arithmetic and loader prefix through open; parsing/mapping not executed','cases':rows,'formatting_and_memset_mocked':True,'resource_context_fixture':True,'registry_required_before_open':False,'swd_parser_verified':False,'actual_text_lookup_verified':False,'stock_sha256':hashlib.sha256(raw).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out=ROOT/'work/home-feedback-resource-review-1/loader-open-report.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
