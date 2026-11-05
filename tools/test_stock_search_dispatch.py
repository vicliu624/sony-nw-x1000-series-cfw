"""Verify original Search FSM routing for every registered state/event pair."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
 if s['p_type']!='PT_LOAD':continue
 a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
area=0x71000000;u.mem_map(area,65536);done=area+0xff00;descriptor=0x4122a8
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
states=u.mem_read(descriptor,1)[0];events=struct.unpack('<H',u.mem_read(descriptor+2,2))[0];handlers=struct.unpack('<H',u.mem_read(descriptor+4,2))[0]
assert (states,events,handlers)==(40,33,84)
table=get(descriptor+12);targets={get(table+i*4) for i in range(handlers)};observed=[]
def hook(cpu,pc,size,data):
 if pc==done:cpu.emu_stop();return
 if pc in targets:
  observed.append((pc,tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))))
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);routes=[]
for event_index in range(events):
 event,index=struct.unpack('<II',u.mem_read(get(descriptor+16)+event_index*8,8));assert index==event_index
 for state in range(1,states+1):
  u.mem_write(area,b'\0'*32);u.mem_write(area,bytes((1,state)));put(area+4,0x41220c);u.mem_write(area+8,b'\xff\xff');u.mem_write(area+13,b'\x15')
  action=u.mem_read(get(descriptor+8)+index*states+state-1,1)[0];expected=get(table+action*4);observed.clear()
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(area,event,0x1234,0x5678)):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x17c608,done+4,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
  assert observed==[(expected,(area,event,0x1234,0x5678))]
  assert bytes(u.mem_read(area,2))==bytes((1,state))
  routes.append(dict(event=hex(event),state=state,action=action,handler=hex(expected)))
completion=[r for r in routes if r['event']=='0x530004' and r['action']!=0]
assert next(r for r in completion if r['state']==26)['handler']=='0x99f80'
assert not any(r['handler']=='0x960dc' for r in completion)
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_search_dispatch.py').read_bytes()).hexdigest(),pairs_verified=len(routes),completion_routes=completion,routes=routes,device_accessed=False,limits=['Original FSM event lookup and state/action routing execute.','Every selected application handler is intercepted and returns no transition; application effects and menu click provenance are not qualified.'])
p=ROOT/'work/player-stock-search-dispatch';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='routes'},indent=2))
