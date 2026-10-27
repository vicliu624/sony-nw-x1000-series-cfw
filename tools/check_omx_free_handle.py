"""Stock OMX core FreeHandle lifecycle boundary and error propagation, virtual registry/deinit/free."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/libomx_core.so').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
elf=ELFFile(io.BytesIO(raw));rows=[]
for name,initialized,found,deinit_result in (('success',1,True,0),('component-error',1,True,0x80001001),('unknown-handle',1,False,0),('core-uninitialized',0,False,0)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=max((s['p_vaddr']+s['p_memsz']+4095)&~4095 for s in segs)
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 handle=0x60001000;record=0x60003000
 got=0x5aa0+word(0x5b24);put(got+word(0x5b28),0x60002000);put(0x60002000,initialized)
 put(handle+0x4c,0x60007000)
 for off,v in ((4,1),(0x10,handle),(0x40,0x60008000)):put(record+off,v)
 calls=[]
 def hook(uc,pc,size,data):
  a=uc.reg_read(UC_ARM_REG_R0)
  if pc==0x2208:
   assert a==handle;calls.append('lookup');result=record if found else 0
  elif pc==0x60007000:
   assert a==handle;calls.append('component_deinit');result=deinit_result
  elif pc==0x22a4:
   assert a in (handle,0x60008000);assert word(record+4)==0
   calls.append('free_handle' if a==handle else 'free_auxiliary');result=0
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R0,handle);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(0x5a8c,0x6001f000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
 expected_result=0x80001001 if not initialized else 0x80001005 if not found else deinit_result
 assert u.reg_read(UC_ARM_REG_R0)==expected_result
 expected_calls=[] if not initialized else ['lookup'] if not found else ['lookup','component_deinit']+(['free_handle','free_auxiliary'] if not deinit_result else [])
 assert calls==expected_calls
 fields=[word(record+o) for o in (4,0x10,0x40)]
 assert fields==([0,0,0] if initialized and found and not deinit_result else [1,handle,0x60008000])
 rows.append({'case':name,'native_order':calls,'return':hex(expected_result),'record_fields_after':fields})
report={'core_sha256':digest,'entry':'OMX_FreeHandle0x5a8c','cases':rows,
 'finding':'Core calls handle+4c component deinit first. Only success clears registry fields and frees handle/auxiliary; component error propagates without those frees.',
 'limits':['Core initialized pointer/state, registry lookup result and handle callback supplied; component deinit/free are virtual.',
           'No actual registry initialization, library unload or component threads. Upper SpiderApp ignoring this propagated error is separate observed caller behavior.']}
(ROOT/'sources/native-omx-free-handle.json').write_text(json.dumps(report,indent=2)+'\n')
print('Four original OMX FreeHandle cases passed: deinit-before-free and error propagation/record preservation')
