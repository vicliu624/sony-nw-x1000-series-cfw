"""Original scan-control handlers are not an arbitrary-track selection API."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';cases=[]
for handler,operation,value,notify,result in ((0x69064,3,100,7,9),(0x690b0,4,-100,8,9),(0x681f0,3,10,7,4),(0x6821c,4,-10,8,5)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in ELFFile(io.BytesIO(raw)).iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;audio=0x6922d8;controller=area+0x1000;calls=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(audio,controller)
 def hook(uc,pc,size,ctx):
  r0,r1,r2,r3=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0xb6888:finish(area+0x2000);return
  if pc==0xb6b48:assert (r0,r1)==(area+0x2000,1);finish();return
  if pc==0x3c194:finish(area+0x3000);return
  if pc==0x3c38c:assert (r0,r1)==(area+0x3000,1);finish();return
  if pc==0x3cd34:finish();return
  if pc==0x116d4:finish();return
  if pc==0x33b83c:finish();return
  if pc==0x27d6a0:
   assert (r0,r1,r2,r3)==(controller,operation,audio+0x38,audio+0x10)
   assert struct.unpack('<iI',uc.mem_read(r2,8))==(value,1);calls.append('change-state');put(r3,77);finish();return
  if pc==0x1542c:finish(area+0x4000);return
  if pc==0x1764c:assert (r0,r1)==(area+0x4000,notify);calls.append('notify');finish();return
  if pc in (0x28d704,0x2995d0,0x295ce8,0x2808d4,0x2817e4):raise AssertionError('Unexpected ID or sequence creation')
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,area);u.reg_write(UC_ARM_REG_R1,0x440002 if operation==3 else 0x440006);u.reg_write(UC_ARM_REG_R2,0xdead0001);u.reg_write(UC_ARM_REG_R3,0xbeef0001);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(handler,done,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==result and calls==['change-state','notify']
 cases.append(dict(handler=hex(handler),operation=operation,signed_payload=value,payload_second_word=1,native_item_id_consumed=False))
w=ROOT/'work/stock-audio-control-roles';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_handlers_and_wrappers_execute=True,cases=cases,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_audio_control_roles.py').read_bytes()).hexdigest(),limits=['Controller admission, UI/configuration helpers and logging are modeled.','State-request parameters are observed, not qualified time/rate units. No track selection or hardware behavior is implemented.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
