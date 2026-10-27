"""Original H264 component SendCommand -> message queue; no DSP/thread execution."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/omf_mc_h264d.so').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='8dcb6f2c5cd5a107e3f84daa1f8a72ef420abf59c67bc7281b9ab10d2536a8b2'
elf=ELFFile(io.BytesIO(raw));rows=[]
for target in (1,2,3,4,5):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 put(0x60001004,1);put(0x60001008,0x60002000);put(0x6000200c,1)
 put(0x600023cc,0x60005000);put(0x600023dc,0x60004000)
 messages=[];services=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
  if pc==0x16f4: # Pinned ELF PLT entry, redirect to its actual handle validator.
   uc.reg_write(UC_ARM_REG_PC,0x2074);return
  if pc==0x1634:
   assert a==[0x60005000,1];name='lock';result=0
  elif pc==0x1784:
   assert a[0]==0x60005000;name='unlock';result=0
  elif pc==0x161c:
   assert a[0]==12;name='allocate';result=0x60003000
  elif pc==0x170c:
   assert a==[0x60004000,0x60003000]
   words=list(struct.unpack('<3I',uc.mem_read(a[1],12)))
   assert words==[target-1,target,0];messages.append(words);name='post';result=0
  else:return
  services.append(name);uc.reg_write(UC_ARM_REG_R0,result)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM_REG_R0,0x60001000),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,target),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x6001f000)):u.reg_write(reg,value)
 u.emu_start(0x2254,0x6001f000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
 assert u.reg_read(UC_ARM_REG_R0)==(0 if target<=4 else 0x80001005)
 assert services==(['lock','allocate','post','unlock'] if target<=4 else ['lock','allocate','unlock'])
 rows.append({'target_state_fixture':target,'command':0,'native_messages':messages,'virtual_services':services,'return':hex(u.reg_read(UC_ARM_REG_R0))})
report={'component_sha256':digest,'entry':'OmfMcSendCommand0x2254','cases':rows,
 'finding':'State command0 targets1..4 enqueue message ids0..3 and return after queue acceptance; target5 does not enqueue.',
 'limits':['Handle/private state and service endpoints supplied; native handle validation and message construction execute. Allocator/mutex/queue are virtual.',
           'No message receiver, DSP, real state transition or completion callback executed. Return0 means queued under this fixture, not transition complete.']}
(ROOT/'sources/native-h264-command-queue.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five original H264 SendCommand cases passed: targets1..4 queue mapped messages; no completion claim')
