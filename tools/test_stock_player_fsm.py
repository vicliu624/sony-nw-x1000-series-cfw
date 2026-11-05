"""Original internal player FSM: deferred commands and invalid target masks."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};cases=[]
for action_result,next_mask,expected,final_state in ((0,2,0,2),(0x106,2,0x106,1),(0x2202,2,0x2202,2),(0,3,0x2683,1),(0,0,0x2683,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;action=area+0xe000;enter=area+0xe004;current_node=area+0x5000;next_node=current_node+0x40;rule_node=current_node+0x80;current_config=current_node+0xc0;next_config=current_node+0x100;rule=current_node+0x140;owner=area+0x6000;payload=owner+0x100;observed=[]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(area,owner);put(area+0x3c90,1);put(current_node+16,current_config);put(next_node+16,next_config);put(rule_node+16,rule);put(rule+8,3);put(rule+12,action);put(rule+16,0);put(next_config+8,enter)
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
  if pc==0x286ab4:
   assert args[0]==area and args[1] in (1,2);value=current_node if args[1]==1 else next_node
  elif pc==0x286760:value=args[0]
  elif pc==0x33bad4:assert args[0]==area+0x440;value=rule_node
  elif pc==action:
   assert args[:3]==(owner,0,payload);put(args[3],next_mask);observed.append('action');value=action_result
  elif pc==enter:assert args[:2]==(owner,payload);observed.append('enter')
  elif pc in (0x285d24,0x33b83c,symbols['PltMark_basename']):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);sp=area+0xf000
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(area,0,1,payload)):u.reg_write(r,v)
 put(sp,1);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x286af4,done+4,count=20000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==expected
 assert get(area+0x3c90)==final_state and observed==(['action','enter'] if final_state==2 else ['action'])
 cases.append(dict(action_result=action_result,next_mask=next_mask,result=expected,final_state=final_state))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_player_fsm.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original FSM dispatch, target-mask validation and bit-count helper execute.','State/rule tree lookup, action/entry handlers and logging are modeled; these are synthetic rules, not the recovered player rule table.','No full source installation, fatal session consumer path or hardware qualification is claimed.'])
p=ROOT/'work/player-stock-fsm';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
