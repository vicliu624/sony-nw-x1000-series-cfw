"""Original CtrlInfo observer -> GUI stable playing/paused transitions."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for primary,substate,event in ((0,0,0x440104),(1,0,0x440105),(2,0,0x44001e),(1,1,None),(2,1,None)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);info=area;actor=area+0x1000;done=area+0xff00
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 put(info+4,primary);put(info+8,substate);put(0x4ee674,0);put(0x6922d8+0x34,0);messages=[];callbacks=set()
 for descriptor,count in ((0x3f1604,10),(0x3f11e0,7)):
  for offset in (20,24):
   table=get(descriptor+offset)
   if table:callbacks.update(get(table+i*4) for i in range(count) if get(table+i*4))
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  value=0
  if pc==0xa57f0:messages.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
  elif pc in callbacks or pc in (0x116d4,0x33b83c,0xacaac,0x496b8,0x497b4,0x17c42c,0x33b918):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(pc,*args):
  sp=area+0xf000
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  for i,v in enumerate(args[4:]):put(sp+i*4,v)
  u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done+4,count=30000);assert u.reg_read(UC_ARM_REG_PC)==done
 call(0xad39c,0,0,0,2,info)
 assert messages==([] if event is None else [(event,0,0,0)]),(primary,substate,messages)
 final=None
 if primary in (1,2) and substate==0:
  mode,initial,final=(1,8,5) if primary==1 else (2,1,2)
  u.mem_write(actor,bytes((mode,initial)));put(actor+4,0x3f11d8);u.mem_write(actor+8,b'\xff\xff');u.mem_write(actor+13,b'\2')
  call(0x17c608,actor,event,0,0);assert bytes(u.mem_read(actor,2))==bytes((mode,final))
 cases.append(dict(primary=primary,substate=substate,event=hex(event) if event else None,stable_gui_state=final))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_state_notifications.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original observer, CtrlInfo accessors, event selection, GUI dispatch and selected GUI handlers execute.','Metadata refresh, UI effects, state entry/exit and logging are modeled.','This proves stable notification mapping, not physical playback, user input or service installation.'])
p=ROOT/'work/player-stock-state-notifications';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
