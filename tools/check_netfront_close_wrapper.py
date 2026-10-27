"""Stock NetFront display-close wrapper, software guard and both mapped/unmapped context cleanup."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/netfront';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for state,owned,extra in ((0,False,False),(1,False,False),(1,True,False),(1,False,True),(1,True,True),(2,True,True)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095;u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);u.mem_map(0x61000000,0x500000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 guard=0x7de698;display=0x918de4;context=0x91013c;table=0x60003000;sentinel=0x6001f000
 put(guard,state);put(display,17);put(display+4,0x61000000)
 put(context+0x3e0,0x62000000 if extra else 0);put(context+0x3e4,8192 if extra else 0);put(context+0x88,18 if extra else 0);put(context+0x384,table if owned else 0);put(context+0x90,0x300 if owned else 0)
 allocations=[0x60008000+i*0x100 for i in (0,2,7)] if owned else []
 for i in range(8):put(table+4+i*4,(0x60008000+i*0x100) if owned and i in (0,2,7) else 0);put(table+0x24+i*4,0x100)
 events=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if pc==sentinel:uc.emu_stop();return
  if pc==symbols['munmap']:
   assert a[:2] in ([0x61000000,0x500000],[0x62000000,8192]);events.append('unmap-extra' if a[0]==0x62000000 else 'munmap');result=0
  elif pc==symbols['close']:assert a[0] in (17,18);events.append('close-extra' if a[0]==18 else 'close');result=0
  elif pc==symbols['free']:assert a[0] in allocations;events.append('free:'+hex(a[0]));result=0
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def run():
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,sentinel);u.emu_start(0x37a2c8,0,count=3000);assert u.reg_read(UC_ARM_REG_PC)==sentinel;return u.reg_read(UC_ARM_REG_R0)
 result=run();expected=['munmap','close']+(['unmap-extra','close-extra'] if extra else [])+['free:'+hex(p) for p in allocations] if state==1 else []
 assert events==expected and result==(guard if state==1 else 1),(state,owned,events,expected,result,word(guard))
 assert word(guard)==(0 if state==1 else state)
 if state==1:
  assert word(context+0x90)==0 and word(context+0x3e0)==0
  before=events.copy();assert run()==1 and events==before
 rows.append({'state_fixture':state,'owned_buffers_fixture':len(allocations),'result':result,'state_after':word(guard),'operations':events.copy(),'extra_mapping_fixture':extra})
report={'passed':True,'entry':'0x37a2c8','cases':rows,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),path]},'hardware_tested':False,'limits':['Display/guard/context fields supplied; real code executes guard, getters, cleanup iteration and setter.','Only munmap/close/free are replaced, not actual kernel cleanup.','Both context mapping branches exercised with supplied fields; outer browser/APF caller remains unverified.','No complete browser lifecycle, display drain or physical handoff qualification.']}
(ROOT/'sources/native-netfront-close-wrapper.json').write_text(json.dumps(report,indent=2)+'\n');print('NetFront close wrapper: state1-only cleanup, owned-buffer frees and repeat-call guard passed in six bounded cases.')


