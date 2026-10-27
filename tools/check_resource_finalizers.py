"""Replay original resource finalizers; virtual libc, no hardware or firmware output."""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw))
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for case in ('fb-success','fb-empty','fb-unmap-failure','fb-close-failure','touch-success','touch-close-failure'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segments)&~4095
 high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 calls=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  result=0
  if pc==symbols['free']:calls.append(['free',a[0]])
  elif pc==symbols['munmap']:
   calls.append(['munmap',a[0],a[1]])
   result=-1 if case=='fb-unmap-failure' else 0
  elif pc==symbols['close']:
   calls.append(['close',a[0]])
   result=-1 if case.endswith('close-failure') else 0
  elif pc==symbols['__errno_location']:result=0x60010000
  elif pc==symbols['fprintf']:calls.append(['error-log'])
  else:return
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 fb=case.startswith('fb-')
 if fb:
  for p,v in [(0x691740,0x60001000),(0x69174c,0x60002000),(0x691748,0x60003000),(0x691744,0x60004000),(0x4ee618,17),(0x6918cc,240),(0x6918d0,432),(0x6918e4,16)]:put(p,v)
  if case=='fb-empty':
   for p in (0x691740,0x69174c,0x691748,0x691744):put(p,0)
   put(0x4ee618,-1)
 else:put(0x60000000,23)
 u.reg_write(UC_ARM_REG_R0,0x60000000);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0xa6364 if fb else 0x14b070,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 result=u.reg_read(UC_ARM_REG_R0)
 if fb:
  assert all(word(p)==0 for p in (0x691740,0x69174c,0x691748))
  if case=='fb-empty':assert calls==[] and result==1
  else:
   assert calls[:4]==[['free',0x60001000],['free',0x60002000],['free',0x60003000],['munmap',0x60004000,207360]]
   if case=='fb-unmap-failure':assert result==0 and word(0x691744)==0x60004000 and word(0x4ee618)==17 and not any(c[0]=='close' for c in calls)
   else:
    assert calls[4]==['close',17] and word(0x691744)==0
    assert result==(0 if case=='fb-close-failure' else 1)
    assert word(0x4ee618)==(17 if case=='fb-close-failure' else 0xffffffff)
 else:assert calls==[['close',23]] and result==0 and word(0x60000000)==0xffffffff
 rows.append({'case':case,'calls':calls,'native_return':result,'fd_after':word(0x4ee618 if fb else 0x60000000)})
report={'input_sha256':digest,'procedures':['0xa6364','0x14b070'],'cases':rows,'limits':['Backing memory, initial buffers/fds, libc success/failures and errno are fixtures; original ARM finalizer bodies execute.','These functions are not yet linked to deactivate/reactivate callers; do not infer application-switch cleanup or actual driver ownership from this test.','No real devices, driver close methods, display restore or firmware images are exercised.']}
(ROOT/'sources/native-resource-finalizers.json').write_text(json.dumps(report,indent=2)+'\n')
print('Six original framebuffer/touch finalizer success/failure cases verified')
