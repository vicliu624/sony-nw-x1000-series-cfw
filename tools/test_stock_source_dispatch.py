"""Original GUI source handoff owns ID before controller acceptance is known."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};cases=[]
for mode,phase in ((1,5),(2,2)):
 for rejected in (False,True):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for segment in elf.iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
  area=0x71000000;u.mem_map(area,65536);actor=area;source=area+0x1000;heap=area+0x2000;item=area+0x3000;controller=area+0x4000;done=area+0xff00;audio=0x6922d8
  def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
  put(actor+4,0x3f11d8);u.mem_write(actor+13,b"\2");put(audio,controller);put(audio+0x10,6);u.mem_write(actor,bytes((mode,phase)));u.mem_write(actor+8,b'\xff\xff');put(source,0);put(source+4,item);callbacks=set();requests=[];allocations=[]
  for descriptor,count in ((0x3f1604,10),(0x3f11e0,7)):
   for offset in (20,24):
    table=get(descriptor+offset)
    if table:callbacks.update(get(table+4*i) for i in range(count) if get(table+4*i))
  def hook(uc,pc,size,ctx):
   r0,r1,r2,r3=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
   def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
   if pc in callbacks:finish();return
   if pc==symbols['malloc']:assert r0==64;allocations.append(heap);finish(heap);return
   if pc==0xac8e4:assert r0==audio;finish();return
   if pc in (0x116d4,0x33b83c):finish();return
   if pc==0x27d6a0:
    assert (r0,r1,r2,r3)==(controller,0,audio+0x38,audio+0x10);assert struct.unpack('<2I',uc.mem_read(r2,8))==(0,1)
    requests.append(pc);put(r3,0xffffffff if rejected else 7);finish(0x302 if rejected else 0);return
   if pc in (0x2995d0,0x2995e8):raise AssertionError('Newly handed ID must not be cloned/disposed by descriptor handoff')
  u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,actor);u.reg_write(UC_ARM_REG_R1,0x44001d);u.reg_write(UC_ARM_REG_R2,source);u.reg_write(UC_ARM_REG_R3,0);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(0x17c608,done,count=1000000);assert u.reg_read(UC_ARM_REG_PC)==done
  assert bytes(u.mem_read(actor,2))==bytes((1,7)) and get(audio+4)==item and get(audio+8)==heap and allocations==[heap] and len(requests)==1
  assert get(audio+0x10)==(0xffffffff if rejected else 7)
  cases.append(dict(initial_mode=mode,initial_phase=phase,rejected_controller=rejected,final_mode=1,final_phase=7,item_owned_by_original_wrapper=True,request_ticket=get(audio+0x10)))
w=ROOT/'work/stock-source-dispatch';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_fsm_handlers_descriptor_and_stop_wrapper=True,cases=cases,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_dispatch.py').read_bytes()).hexdigest(),limits=['UI state entry/exit, heap allocation, metadata update, logging and controller acceptance modeled.','Rejected stop still moves GUI state and owns the item. Recovery/completion not qualified; PLAY_ITEM remains disabled.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
