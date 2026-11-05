"""Original control consumer publishes target and native substate separately."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};cases=[]
for request,target,native_state,substate in ((1,0,0x20,1),(2,1,0x80,2)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,131072);player=area;frame=area+0x8000;options=area+0x8100;data=area+0x9000;info=area+0xa000;done=area+0x1ff00
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 put(player+0x3ca4,data);put(player+8+0x3c90,1);put(data+4,info);put(frame,request);put(frame+4,options);put(options,target);put(options+4,1)
 def hook(cpu,pc,size,unused):
  if pc==done:cpu.emu_stop();return
  args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
  if pc==0x286af4:assert args[:3]==(player+8,0,request);put(player+8+0x3c90,native_state)
  elif pc==symbols['memcpy']:cpu.mem_write(args[0],bytes(cpu.mem_read(args[1],args[2])));value=args[0]
  elif pc in (0x27645c,0x276464,0x286458,0x2864c4,0x276c3c,0x286468,0x27b0b8):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R0,player);u.reg_write(UC_ARM_REG_R1,frame);u.reg_write(UC_ARM_REG_SP,area+0x1f000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x27b1b8,done+4,count=30000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
 assert (get(info+4),get(info+8),get(info+12))==(target,substate,0) and get(data+12)&2
 record=0x49a128+(5 if native_state==0x20 else 7)*16
 assert get(record)==native_state
 name=bytes(u.mem_read(get(record+4),16)).split(b'\0',1)[0].decode('ascii')
 assert name==('RUNNING' if native_state==0x20 else 'ERROR')
 cases.append(dict(request=request,target=target,native_state=native_state,native_state_name=name,published_primary=get(info+4),published_substate=get(info+8)))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_control_state.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original command consumer, state normalization, data snapshot and CtrlInfo setters execute.','FSM state outcome, metadata/config operations, mutexes, memcpy and logging are modeled; real command execution remains separately qualified.','RUNNING and ERROR are not stable playback completion; raw publication pairs do not classify PLAYING/PAUSED.'])
p=ROOT/'work/player-stock-control-state';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
