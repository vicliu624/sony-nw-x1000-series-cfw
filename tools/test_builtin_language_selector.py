"""Replay stock language confirmation; UI/store services mocked, no device writes."""
import hashlib,io,json
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
data=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(data).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in ELFFile(io.BytesIO(data)).iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000)
selected=market=0;writes=[];rows=[]
def hook(uc,pc,size,unused):
 if pc==0xf7c8:uc.mem_write(uc.reg_read(UC_ARM_REG_R0),market.to_bytes(4,'little'));answer=0
 elif pc==0x2a984:answer=0x60001000
 elif pc==0x2b728:uc.mem_write(uc.reg_read(UC_ARM_REG_R2),(1).to_bytes(4,'little'));answer=0
 elif pc==0x74634:answer=selected
 elif pc==0x3ce08:answer=0x60002000
 elif pc==0x3dedc:writes.append(uc.reg_read(UC_ARM_REG_R1));answer=0
 elif pc in (0x74608,0x74668,0xa57f0):answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
for market in (0,10):
 for selected,expected,name in ((0xf80101,1,'English'),(0xf80107,7,'Japanese'),(0xf8010a,9,'Simplified Chinese'),(0xf80109,10,'Traditional Chinese')):
  for confirm in (True,False):
   writes.clear();u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_R2,0xff0000 if confirm else 0)
   u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0x89a38,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and writes==([expected] if confirm else [])
   rows.append(dict(market=market,language=name,menu_item=hex(selected),confirm=confirm,requested_settings=list(writes)))
report=dict(passed=True,stock_confirmation_instructions_executed=True,store_and_ui_boundaries_modeled=True,
            device_accessed=False,rows=rows,source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest())
out=ROOT/'work/builtin-language-settings';out.mkdir(exist_ok=True);(out/'selector-replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(rows),simplified_menu='0xf8010a',traditional_menu='0xf80109',device_accessed=False)))
