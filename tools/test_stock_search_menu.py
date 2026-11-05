"""Original menu index5 producers: native search kind/index and empty refusal."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for entry,scope in ((0x87598,0),(0x83ad4,1)):
 for index,present in [(i,True) for i in range(6)]+[(5,False)]:
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for s in ELFFile(io.BytesIO(raw)).iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  area=0x71000000;u.mem_map(area,65536);done=area+0xff00;messages=[];checks=[]
  def hook(cpu,pc,size,data):
   if pc==done:cpu.emu_stop();return
   args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
   if pc==0x434b8:value=area
   elif pc==0x46188:
    assert args[:2]==(area,scope);checks.append(True);return
   elif pc==0x41518:
    assert args[0]==0x10000000;value=area+0x100
   elif pc==0x4215c:
    assert args==(area+0x100,0,0x66e158+0x4e8,0)
    stack=cpu.reg_read(UC_ARM_REG_SP)
    extra=struct.unpack('<4I',cpu.mem_read(stack,16));assert extra[:3]==(0,0,0)
    cpu.mem_write(extra[3],struct.pack('<I',12 if present else 0))
   elif pc==0x42088:assert scope==1 and args[:3]==(area+0x100,0,0x10000000)
   elif pc==0x420e4:assert scope==1 and args[0]==area+0x100
   elif pc==0xa57f0:messages.append(args)
   elif pc==0x74608:value=area+0x100
   elif pc in (0x74668,0x46b2c):pass
   else:return
   cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(0,0,index,0)):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(entry,done+4,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==done
  expected=(0,3,2,1,4,5)[index];requests=[m for m in messages if m[0]==0x530002]
  if present:assert requests==[(0x530002,0,0,expected)] and u.reg_read(UC_ARM_REG_R0)==0x4901
  else:assert not requests and (0x2010e,0,0x7e,0) in messages and u.reg_read(UC_ARM_REG_R0)==2
  assert len(checks)==int(index==5)
  cases.append(dict(entry=hex(entry),menu_index=index,present=present,search_kind=0 if requests else None,query_index=expected if requests else None))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_search_menu.py').read_bytes()).hexdigest(),cases=cases,index5_availability_predicate='0x66e640 (FORMAT3)',device_accessed=False,limits=['Original menu branch, availability predicate selection and message arguments execute; count-query result, context guards, UI navigation and event sender are modeled.','This verifies both original index5 producers, not physical touch dispatch, active SWD identity or real playlist contents.'])
p=ROOT/'work/player-stock-search-menu';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),index5_search_kind=0,index5_query_index=5,empty_lists_refused=True,device_accessed=False),indent=2))
