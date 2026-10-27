"""Execute NetFront argv parsing and startup event construction; no browser/IPC.

Stop at the original startup boundary after parsing, then invoke its original
startup callback with synthetic context. Platform initialization is intercepted.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/qqmusic-wifi-research/netfront').read_bytes()
digest=hashlib.sha256(raw).hexdigest()
assert digest=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
rows=[]
for args,expected in [(['netfront'],0),(['netfront','--restart'],1)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x20000);end=0x2000100;argv=0x2001000;events=[];phase='parse';decisions=[];restore_result=1
 u.mem_write(0x2006000,struct.pack('<I',0x2006100))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def cstr(a):return bytes(u.mem_read(a,256)).split(b'\0')[0]
 for i,arg in enumerate(args):
  a=0x2002000+i*256;u.mem_write(a,arg.encode()+b'\0');u.mem_write(argv+i*4,struct.pack('<I',a))
 def hook(uc,pc,size,unused):
  r0,r1,r2,r3=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  result=0
  if pc==end or (phase=='parse' and pc==0xad64):uc.emu_stop();return
  elif pc==0xa8ec:
   a,b=bytes(uc.mem_read(r0,r2)),bytes(uc.mem_read(r1,r2));result=0 if a==b else 1
  elif pc==0xadc8:result=1  # platform startup eligibility modeled
  elif pc==0x8fc50:events.append({'code':hex(r3),'payload':get(uc.reg_read(UC_ARM_REG_SP))})
  elif pc==0xc034:result=0x2006000
  elif pc==0x148b8:decisions.append('attempt_restore');result=restore_result
  elif pc==0x14984:decisions.append('update_startup_state')
  elif pc==0xe388:decisions.append('ordinary_startup')
  elif pc in (0x30721c,0xad80,0x2fd688,0x3347e0,0x2fc4d8,0xba28,0xbc34):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def reject(*args):raise AssertionError('Unexpected system instruction')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject)
 def call(pc,r0,r1,r2=0):
  for r,v in ((UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_R2,r2),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):u.reg_write(r,v)
  u.emu_start(pc,end,count=20000)
 call(0xadf0,len(args),argv)
 assert u.reg_read(UC_ARM_REG_PC)==0xad64 and get(0x7de9ec)==expected
 phase='callback';call(0xab18,0,0x2004000,0x2005000)
 assert u.reg_read(UC_ARM_REG_PC)==end and events==[{'code':'0x8009','payload':expected}]
 downstream=[]
 for restored in ([1,0] if expected else [0]):
  restore_result=restored;decisions.clear();message=0x2007000
  u.mem_write(message+12,struct.pack('<I',0x8009));u.mem_write(message+28,struct.pack('<I',expected))
  call(0x14a04,0x2005000,message)
  assert u.reg_read(UC_ARM_REG_PC)==end
  wanted=(['attempt_restore','update_startup_state'] if restored else ['attempt_restore','update_startup_state','ordinary_startup']) if expected else ['update_startup_state','ordinary_startup']
  assert decisions==wanted
  downstream.append({'modeled_restore_result':restored,'original_branch_calls':list(decisions)})
 rows.append({'argv':args,'parsed_restart_flag':expected,'startup_event':events[0],'startup_dispatch':downstream})
report={'passed':True,'NetFront_sha256':digest,'cases':rows,'physical_device_or_ipc':False,
 'limits':['Platform initialization and eligibility modeled; main execution stops after argv parsing.',
           'Original startup callback invoked with synthetic context; event dispatch captured.',
           'Event consumer 0x14a04 executes; restore/update/default handlers intercepted to prove branch ordering only.',
           'Actual restored page/request, storage destination and network reacquisition not proven.']}
(ROOT/'sources/stock-browser-restart.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
