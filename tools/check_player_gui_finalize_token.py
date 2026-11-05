"""Native GUI command3 and nested cleanup order; most leaf effects modeled."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for active,deep in ((0,False),(1,False),(0,True)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);context=area;result=area+0x7000;done=area+0xff00;calls=[];nested=[]
 u.mem_write(result,struct.pack('<I',0xffffffff))
 helpers={0x11fcc,0x11fc8,0x119a0,0xb4b9c,0x11ec4}
 teardown=[0x23e28,0x23e50,0x2a34c,0x2a3a0,0x48b98,0x48e80,
  0x2955c,0x29584,0x3700c,0x37074,0x2a120,0x2a13c,0x28924,0x289fc,
  0x28df8,0x28e18,0x2696c,0x269bc,0x26f70,0x26fc0,0x273ec,0x27434,
  0x2763c,0x2768c,0x27a04,0x27a68,0x25c10,0x25c60,0x2a984,0x2acfc,
  0x14d70,0xb4948,0x54fcc]
 state=struct.unpack_from('<I',raw,0x27a0c-0x8000)[0]
 for offset in (0,4,0x2b98,0x2b9c):u.mem_write(state+offset,struct.pack('<I',0x12345678))
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  if deep and pc==0x11ec4:calls.append(hex(pc));return
  if deep and pc in teardown:
   nested.append(pc)
   # Execute the getter and state-reset body rather than modeling their writes.
   if pc in (0x27a04,0x27a68):return
   value=0
  elif pc==0x12128:value=active
  elif pc in helpers:calls.append(hex(pc));value=0
  elif pc in (0x116d4,0x33b83c):value=0
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,3),(UC_ARM_REG_R2,result),(UC_ARM_REG_SP,area+0xf000),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
 u.emu_start(0x143c0,done+4,count=20000);assert u.reg_read(UC_ARM_REG_PC)==done
 token=struct.unpack('<I',u.mem_read(result,4))[0];assert token==0
 assert calls==(['0x11fcc'] if active else ['0x11fc8','0x119a0','0xb4b9c','0x11ec4'])
 if deep:
  assert nested==teardown
  assert all(struct.unpack('<I',u.mem_read(state+offset,4))[0]==0 for offset in (0,4,0x2b98,0x2b9c))
 rows.append(dict(active_fixture=active,pending_token=token,cleanup_helpers=calls,
  deep_cleanup=deep,nested_cleanup_order=[hex(a) for a in nested],original_state_reset_executed=deep))
out=ROOT/'work/player-gui-finalize-token'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,native_gui_branch_and_output=True,cleanup_effects_modeled=True,device_accessed=False,cases=rows,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,__import__('pathlib').Path(__file__))},limits=['Activity selection and most cleanup leaves are modeled; the deep case executes 11ec4 and original getter27a04/reset27a68, including four state writes.','Reset field semantics and SDK resource dependency are not established by this replay; no actual hardware teardown.','Zero output does not prove all native work synchronous, only no pending token returned by the tested branch.','Do not assume token203 is an existing registered command3 request or reuse206/207 from different commands.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
