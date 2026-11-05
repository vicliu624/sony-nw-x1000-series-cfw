"""Execute original asynchronous list-request packing and parent retention."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(raw)).get_section_by_name('.dynsym').iter_symbols()}
cases=[]
for child,parent in ((0,0),(0,0x123400),(1,0),(1,0x123400)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;sp=area+0xf000;packed=[];clones=[];sent=[]
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  value=0
  if pc==0x1f064:value=area+0x100
  elif pc==symbols['MomaObjectId_clone']:clones.append(args[0])
  elif pc==0xb8404:assert args[0]==area+0x200;value=0
  elif pc==0x433ec:
   stack=cpu.reg_read(UC_ARM_REG_SP);pointer=word(stack);length=word(stack+4)
   assert args==[4,7,0,0] and length==36
   packed.append(struct.unpack('<9I',cpu.mem_read(pointer,length)));value=area+0x300
  elif pc==0x1ee58:sent.append(args);assert args==[area+0x100,7,4,area+0x300]
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(7,0x111,0x222,area+0x200)):u.reg_write(r,v)
 for i,v in enumerate((0x333,child,parent,1)):u.mem_write(sp+i*4,struct.pack('<I',v))
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x1f91c,done+4,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and len(sent)==1
 assert clones==([parent] if child and parent else [])
 assert packed==[(0x111,0,0,0x222,area+0x200,0x333,child,parent,1)]
 cases.append(dict(child_flag=child,parent_present=bool(parent),parent_retained=bool(clones),payload_bytes=36))
report=dict(target_sha256=digest,cases=cases,device_accessed=False,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_list_request.py').read_bytes()).hexdigest(),limits=['Original request-packing instructions execute; clone, aggregation classification, allocator and queue sender are modeled.','This verifies retention and request layout, not async consumer completion or visible playlist routing.'])
p=ROOT/'work/player-stock-list-request';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
