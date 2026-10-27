"""Original QFB busy wait over virtual scheduler/user copy; no hardware."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
a=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(a));assert elf.get_section_by_name('.kernel').data()==raw
rows=[]
for name in ('query-only','timeout','signal','callback-page0','callback-page1'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x30000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 count=0 if name=='query-only' else 1
 payload=0x60003000;u.mem_write(payload,struct.pack('<3I',count,0,0))
 for p,v in ((0xc02c28d8,1),(0xc02c28dc,1),(0x60016008,0xffffffff),(0x6001600c,0x60005000),(0x60005004,0x60006000),(0x60006000,2 if name=='signal' else 0)):
  put(p,v)
 callbacks=[];wait_services=[];sleeps=[]
 def hook(uc,pc,size,data):
  if pc==0xc0219e84:uc.emu_stop();return
  if pc in (0xc00f5ce4,0xc00f58b0):
   dst,src,n=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
   assert n==12
   uc.mem_write(dst,bytes(uc.mem_read(src,n)))
  elif pc in (0xc005d7cc,0xc005d8f4,0xc004ffa8,0xc0042f90):wait_services.append(hex(pc))
  else:return
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_R2,0x80044e00);u.reg_write(UC_ARM_REG_R3,payload)
 u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 pc=0xc0101f80
 for attempt in range(5):
  u.emu_start(pc,0x50000000,count=20000)
  if u.reg_read(UC_ARM_REG_PC)==0x50000000:break
  assert u.reg_read(UC_ARM_REG_PC)==0xc0219e84
  sleeps.append(u.reg_read(UC_ARM_REG_R0));saved=u.context_save();return_pc=u.reg_read(UC_ARM_REG_LR)
  if name.startswith('callback') and not callbacks:
   page=int(name[-1]);put(0xc02c28e4,page)
   u.reg_write(UC_ARM_REG_R0,page);u.reg_write(UC_ARM_REG_R1,0)
   u.reg_write(UC_ARM_REG_SP,0x60028000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc0101680,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000;callbacks.append(page)
  u.context_restore(saved);u.reg_write(UC_ARM_REG_R0,0);pc=return_pc
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 result=u.reg_read(UC_ARM_REG_R0);record=list(struct.unpack('<3I',u.mem_read(payload,12)))
 expected=([1,1,0] if name=='callback-page0' else [1,0,1] if name=='callback-page1' else [count,1,1])
 assert record==expected,(name,record)
 assert result==(0 if name=='query-only' or callbacks else 1),(name,result)
 assert bool(sleeps)==(name not in ('query-only','signal'))
 rows.append({'case':name,'native_return':result,'record':record,'virtual_schedule_inputs':sleeps,'injected_callback_pages':callbacks,'virtual_wait_services':wait_services})
report={'kernel_sha256':digest,'entry':'0xc0101f80 ioctl80044e00','cases':rows,'limits':['Busy states, thread/task/signal flags, user buffers and scheduler/waitqueue services are virtual.','Callback cases inject original qfb_callback during a simulated schedule point; target-page global is supplied. Actual IRQ/driver/concurrency not exercised.','Count1 and query-only samples, not full wait-count100 latency or complete signal delivery/USB lifecycle qualification.']}
(ROOT/'sources/native-kernel-display-wait.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five native busy-wait/query/signal/callback cases verified; busy record can accompany ioctl return0')
