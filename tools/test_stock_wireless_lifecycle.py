"""Replay original wireless module lifecycle callbacks; no hardware or patch."""
import hashlib, io, json, struct
from itertools import product
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for segment in ELFFile(io.BytesIO(raw)).iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
area=0x60000000;u.mem_map(area,0x20000)
context=area+0x1000;primary=area+0x2000;secondary=area+0x2100;module=area+0x3000;output=area+0x4000;done=area+0x1f000
def put(a,v):u.mem_write(a,struct.pack('<I',v))
def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
events=[];cached=0;environment_flag=0
def hook(cpu,pc,size,unused):
 if pc==0x3b134:answer=context
 elif pc==0x61d38:answer=primary
 elif pc==0x62ee0:answer=secondary
 elif pc==0x37f5c:
  assert cpu.reg_read(UC_ARM_REG_R0)==6 and cpu.reg_read(UC_ARM_REG_R1)==0x600
  cpu.mem_write(cpu.reg_read(UC_ARM_REG_R2),bytes([cached]));answer=0
 elif pc==0xe5f4:answer=area+0x5000
 elif pc==0xf674:put(cpu.reg_read(UC_ARM_REG_R1),environment_flag);answer=0
 elif pc==0xa57f0:
  events.append([cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
  assert get(cpu.reg_read(UC_ARM_REG_SP))==0;answer=1
 elif pc in (0xda9c,0xd4fc,0xb3300):raise AssertionError('Unexpected hardware operation')
 else:return
 cpu.reg_write(UC_ARM_REG_R0,answer);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
cases=[]
for command,busy,state,sub,cached,environment_flag in product((3,6,7,21,10,13,18),(0,1),(1,2),(1,6),(0,1),(0,1)):
 put(context+0x20,busy);put(module,primary);u.mem_write(primary,bytes([state]));u.mem_write(secondary,bytes([sub]));put(output,0xa5a5a5a5);events.clear()
 for reg,value in ((UC_ARM_REG_R0,module),(UC_ARM_REG_R1,command),(UC_ARM_REG_R2,output),(UC_ARM_REG_SP,area+0x1e000),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
 u.emu_start(0x3b498,done,count=30000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
 expected=[];token=0;new_busy=busy
 if command==3 and busy:expected=[[0x4c000f,0,0,0]];token=0x503
 elif command==6:new_busy=1
 elif command in (7,21):new_busy=0
 elif command in (10,13,18):
  if not cached and not environment_flag:expected=[[0x420012,0,1,0],[0x4c0005,0,0,0]]
  if command==10:expected.append([0x4c8012,0,0,0])
 assert events==expected and get(output)==token and get(context+0x20)==new_busy,(command,busy,state,sub,cached,environment_flag,events,get(output))
 cases.append(dict(command=command,initial_busy=busy,primary=state,secondary=sub,cached_flag=cached,environment_flag=environment_flag,events=list(events),pending_token=token,final_busy=new_busy))
report=dict(passed=True,device_accessed=False,firmware_created=False,stock_sha256=digest,arm_cases=len(cases),cases=cases,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/test_stock_wireless_lifecycle.py',)},
 limits=['Original module callback, busy getter/setter and cached-Wi-Fi helper execute; environment/configuration/queue are fixtures.',
         'Command6/7 flag changes are not off evidence. No physical radio, native scheduler, SDK composition or suspend/USB qualification.'])
print(json.dumps(report,indent=2))
