"""Original source action table, dispatcher and sequence ownership offline."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for state in (1,2,4,8,16,32,64,128):
 for source_present in (False,True):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for s in ELFFile(io.BytesIO(raw)).iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  area=0x71000000;u.mem_map(area,65536);player=area;fsm=player+8;payload=area+0x4000;old_sequence=area+0x5000;sequence=area+0x5100;track=area+0x5200;rule_node=area+0x7000;state_nodes=area+0x7100;done=area+0xff00
  get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
  put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
  states=[struct.unpack('<4I',u.mem_read(0x49a128+i*16,16)) for i in range(8)]
  rules=[(0x499458+i*20,struct.unpack('<5I',u.mem_read(0x499458+i*20,20))) for i in range(160)]
  candidates=[(a,row) for a,row in rules if row[:2]==(state,1)];assert len(candidates)==1
  address,rule=candidates[0];assert rule[3]==(0x2795f4 if state in (1,2) else 0x279554) and rule[4]==0
  put(rule_node+16,address)
  for i,row in enumerate(states):put(state_nodes+i*32+16,0x49a128+i*16)
  put(player,player);put(fsm,player);put(fsm+0x3c90,state);put(player+0x3ca8,old_sequence);put(player+0x3ca4,area+0x6000);put(old_sequence,2);put(sequence,2);put(payload,1);put(payload+24,sequence if source_present else 0)
  entries={row[2] for row in states if row[2]};observed=[]
  helpers={0x2766fc,0x2766cc,0x286458,0x286528,0x2864e8,0x286508,0x27e350,0x278a9c,0x286484,0x286490,0x276c3c,0x286468,0x335788,0x3357e4}
  def hook(cpu,pc,size,data):
   if pc==done:cpu.emu_stop();return
   args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
   if pc==0x286ab4:
    assert args[0]==fsm;index=next(i for i,row in enumerate(states) if row[0]==args[1]);value=state_nodes+index*32
   elif pc==0x286760:value=args[0]
   elif pc==0x33bad4:assert args[0]==fsm+0x440;value=rule_node
   elif pc==0x27e7d4:assert args[0]==sequence;value=track
   elif pc in (0x27e3e4,0x278a88):value=0
   elif pc in entries:observed.append(pc)
   elif pc in helpers:pass
   else:return
   cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook);sp=area+0xf000
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(fsm,0,1,payload)):u.reg_write(r,v)
  put(sp,1);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x286af4,done+4,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==done
  if state in (1,2):
   expected=0;final=2 if source_present else 1
   assert get(player+0x3ca8)==(sequence if source_present else 0) and get(old_sequence)==1 and get(sequence)==(3 if source_present else 2)
  else:
   expected=0x2603;final=state
   assert get(player+0x3ca8)==old_sequence and get(old_sequence)==2 and get(sequence)==2
  assert u.reg_read(UC_ARM_REG_R0)==expected and get(fsm+0x3c90)==final and len(observed)==1
  cases.append(dict(initial_state=state,source_present=source_present,result=expected,final_state=final,source_action=hex(rule[3])))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_install.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original source rule records, FSM dispatcher, action and retain/release instructions execute.','Tree lookup resolves pinned original records; sequence track lookup, data/config helpers, state entry and mutex boundaries are modeled.','No decoding, audio output, asynchronous GUI stop/install completion or hardware qualification is claimed.'])
p=ROOT/'work/player-stock-source-install';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),idle_installs_or_clears=True,active_states_reject_without_replacing_source=True,device_accessed=False),indent=2))
