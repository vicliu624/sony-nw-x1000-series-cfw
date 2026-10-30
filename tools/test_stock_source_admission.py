"""Original set-source request retains sequence and owns copied configuration."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';cases=[]
for mode in ('copied','no-config','null-sequence','allocation-failure','inactive'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for seg in ELFFile(io.BytesIO(raw)).iter_segments():
  if seg['p_type']!='PT_LOAD':continue
  a=int(seg['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(seg['p_memsz'])+4095)&~4095);u.mem_write(a,seg.data())
 area=0x71000000;u.mem_map(area,65536)
 controller,service,sequence,config,message,ticket,extra1,extra2,done=(area+x for x in (0,0x1000,0x2000,0x3000,0x4000,0x5000,0x6000,0x7000,0xff00))
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(controller,service);put(controller+4,7);put(sequence,1);put(0x8386b4,3);put(service+4,1);put(service+8,2);put(service+0x10,4);put(service+0x2c,service+0x28)
 words=[11,22,33,44,55,extra1,extra2];u.mem_write(config,struct.pack('<7I',*words));u.mem_write(extra1,bytes(range(16)));u.mem_write(extra2,bytes(range(28)));put(ticket,0x5a5a5a5a);locks=set();signals=[];allocations=[]
 def hook(uc,pc,size,ctx):
  r0,r1,r2,r3=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0x27d360:finish(mode!='inactive');return
  if pc in (0x285d24,0x33b83c):finish();return
  if pc==0x27c378:
   assert (r0,r1,r2)==(service,7,1);allocations.append(message)
   if mode=='allocation-failure':finish(0x302);return
   put(r3,message);finish();return
  if pc==0x335788:assert r0 not in locks;locks.add(r0);finish();return
  if pc==0x3357e4:assert r0 in locks;locks.remove(r0);finish();return
  if pc==0x3365d8:assert r0==service+0x14;finish();return
  if pc==0x3354f4:assert r0==2;signals.append(r0);finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(pc,*args):
  sp=area+0xf000;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  for i,v in enumerate(args[4:]):put(sp+i*4,v)
  u.emu_start(pc,done,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
 result=call(0x27d54c,controller,0 if mode=='null-sequence' else sequence,0 if mode=='no-config' else config,ticket)
 expected=0x302 if mode=='allocation-failure' else 0x2605 if mode=='inactive' else 0;assert result==expected and not locks,(mode,result)
 if result:assert get(ticket)==0xffffffff and get(sequence)==1 and not signals and get(service+0x28)==0
 else:
  assert get(ticket)==5 and get(message+4)==5 and get(service+0x28)==message and signals==[2]
  assert get(message+0x24)==(0 if mode=='null-sequence' else sequence)
  assert get(sequence)==(1 if mode=='null-sequence' else 2)
  if mode=='no-config':assert get(message+0x28)==0
  else:
   assert get(message+0x28)==message+0x2c and struct.unpack('<5I',u.mem_read(message+0x2c,20))==tuple(words[:5])
   assert get(message+0x40)==message+0x48 and get(message+0x44)==message+0x58
   u.mem_write(config,bytes(28));u.mem_write(extra1,bytes(16));u.mem_write(extra2,bytes(28))
   assert bytes(u.mem_read(message+0x48,16))==bytes(range(16)) and bytes(u.mem_read(message+0x58,28))==bytes(range(28))
  if mode!='null-sequence':call(0x27e774,sequence);assert get(sequence)==1
 cases.append(dict(mode=mode,result=result,admission_ticket=get(ticket),caller_release_preserves_message_reference=not result and mode!='null-sequence'))
w=ROOT/'work/stock-source-admission';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_controller_and_enqueue_and_retain_execute=True,cases=cases,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_admission.py').read_bytes()).hexdigest(),limits=['Controller initialization, allocation, mutex/ticket/event primitives and logging modeled.','No original request consumer/destructor, source factory, GUI integration or playback completion qualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
