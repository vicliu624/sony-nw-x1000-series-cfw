"""Replay original WLAN list selection; UI/state services modeled, no writes."""
import hashlib,io,json,struct,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for classification in (1,2):
 for index,wanted in enumerate((0x9a01,0x5901,6,0x9c01,4,0x9b01)):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000);events=[];power=[]
  def hook(uc,pc,size,unused):
   if pc==0x7461c:answer=0x5a
   elif pc==0xe5f4:answer=0
   elif pc==0xf6c0:answer=classification
   elif pc==0x3ba48:answer=1
   elif pc==0x37f5c:
    assert uc.reg_read(UC_ARM_REG_R0)==6 and uc.reg_read(UC_ARM_REG_R1)==0x600
    uc.mem_write(uc.reg_read(UC_ARM_REG_R2),bytes(4));answer=0
   elif pc==0xda18:answer=4
   elif pc in (0xda9c,0xd4fc):power.append(hex(pc));answer=0
   elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]);answer=0
   else:return
   uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,index),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
  u.emu_start(0x7c8cc,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==wanted
  assert not power
  rows.append(dict(classification=classification,index=index,native_transition=hex(wanted),posted_events=events,direct_power_calls=power))
report=dict(passed=True,device_accessed=False,original_list_lookup_and_callback_executed=True,
            settings_list='0x5a',native_enabled_item='0xf60005',native_enabled_page='0x9a',
            wording_group='sid-100-00',cases=rows,
            source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
            limits=['Original enable confirmation, NVP persistence and actual power transitions are not executed.',
                    'This locates the stock UI entry; no three-mode selector or firmware is created.'])
out=ROOT/'work/wireless-settings-entry'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
