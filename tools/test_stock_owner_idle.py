"""Original GUI idle policy, timeout getter/setter and select timeval conversion."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for s in elf.iter_segments():
 if s['p_type']!='PT_LOAD':continue
 a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
area=0x71000000;u.mem_map(area,0x40000);policy=area;timing=area+0x2c000;input_state=area+0x2d000;request=area+0x2e000;done=area+0x3ff00;selected=[]
put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
loop_mode=False;anchors=[];loop_trace=[]
put(0x4f7820,timing);put(input_state+0x78,0xffffffff)
def hook(cpu,pc,size,data):
 if pc==done:cpu.emu_stop();return
 if loop_mode and pc==0xa6968:
  anchors.append(len(selected));loop_trace.append('anchor')
  if len(anchors)==3:cpu.emu_stop();return
  value=0
 elif loop_mode and pc in (0xffa4,0xe18d8):value=area+0x30000 if pc==0xffa4 else input_state
 elif loop_mode and pc in (0x109ec,0x121c0,0x106c8,0x105f4,0x10620,0x10640,0x1063c,0x121ec,0x12128,0x51570,0x51828):value=0
 elif loop_mode and pc==0xe1b90:
  put(cpu.reg_read(UC_ARM_REG_R1),0);put(cpu.reg_read(UC_ARM_REG_R2),0);value=0
 elif pc==symbols['memcpy']:
  a,b,n=(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2));assert n==128;cpu.mem_write(a,bytes(cpu.mem_read(b,n)));value=a
 elif pc==symbols['select']:
  assert tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))==(0,input_state+0x7c,0,0)
  pointer=get(cpu.reg_read(UC_ARM_REG_SP));selected.append(struct.unpack('<2i',cpu.mem_read(pointer,8)));value=0
  if loop_mode:loop_trace.append('select')
 else:return
 cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,*args):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,area+0x3f000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done+4,count=20000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
put(request,1);assert call(0xeae0c,policy,request)==0 and get(policy+0x29b98)==1 and get(policy+4)&8
assert call(0xe44dc)==200000
put(request,0);assert call(0xeae0c,policy,request)==0 and not get(policy+0x29b98) and not get(policy+4)&8 and call(0xe44dc)==0
cases=[]
for period in (0,200000,1000001,60000000):
 call(0xe44a4,period);assert call(0xe44dc)==period;selected.clear();call(0xe1aa0,input_state)
 assert selected==[(period//1000000,period%1000000)];cases.append(dict(configured_us=period,select_timeval=selected[0]))
assert call(0xe44a4,60000001)==0xffffffff and call(0xe44dc)==60000000
call(0xe44a4,200000);put(area+0x30010,policy);put(policy+0x5704,0);put(policy+0x56f8,0xffffffff)
selected.clear();loop_mode=True
u.reg_write(UC_ARM_REG_SP,area+0x3f000);u.reg_write(UC_ARM_REG_LR,done)
u.emu_start(0xff04,done+4,count=200000)
assert len(anchors)==3 and anchors==[1,2,3] and selected==[(0,200000)]*3
assert loop_trace==['select','anchor']*3
report=dict(passed=True,target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_owner_idle.py').read_bytes()).hexdigest(),idle_policy_us=200000,cases=cases,device_accessed=False,original_loop_anchor_after_select=anchors,original_loop_trace=loop_trace,limits=['Original idle policy, timeout setter/getter, input poll and timeval conversion execute; memcpy and select syscall boundaries are modeled.','The loop profile executes ff04,10644,134ec,51ae4,b4c54,e1aa0 with inactive GUI fixtures; other loop stages, input decoding and select completion are modeled. No SDK continuation or real wall-clock delay executes.','This confirms a traced 200ms idle policy, not total UI tick latency, power/sleep behavior or physical endpoint responsiveness.'])
p=ROOT/'work/player-stock-owner-idle';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
