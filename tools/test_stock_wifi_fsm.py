"""Original Wi-Fi factory/event dispatcher and table routing, offline ARM."""
import hashlib,io,json,struct,time,sys
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def half(a):return struct.unpack('<H',u.mem_read(a,2))[0]
def byte(a):return u.mem_read(a,1)[0]
def put(a,n):u.mem_write(a,struct.pack('<I',n))
secondary='--secondary' in sys.argv
factory,object_literal,global_literal,classes_literal,groups,dispatch=(0x62ef0,0x62f30,0x62f38,0x62f34,7,0x62f5c) if secondary else (0x61d48,0x61d88,0x61d90,0x61d8c,3,0x61db4)
callbacks=[];action_targets=set()
for group in range(1,groups+1):
 descriptor=word(word(classes_literal)+(group-1)*4);actions=word(descriptor+12)
 for i in range(half(descriptor+4)):
  target=word(actions+i*4)
  if target:action_targets.add(target)
def hook(uc,pc,size,unused):
 if pc in action_targets:
  callbacks.append(dict(address=hex(pc),arguments=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)],return_site=hex(uc.reg_read(UC_ARM_REG_LR))))
  answer=0 # Table routing is real; callback body/resource action is modeled.
 elif pc==0x17c42c:answer=1
 elif pc==0x33b918:answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def syscall(*args):raise AssertionError('Unexpected real syscall')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,syscall)
def call(entry,*args):
 for reg,n in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(*args,0,0,0,0)):u.reg_write(reg,n)
 u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(entry,0x50000000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 return u.reg_read(UC_ARM_REG_R0)
call(factory)
obj=word(word(global_literal));assert obj==word(object_literal) and obj
classes=word(obj+4);assert byte(obj+2)==groups
rows=[];targets=set()
for group in range(1,groups+1):
 descriptor=word(classes+(group-1)*4);states=byte(descriptor)
 assert 1<=states<=16
 count=half(descriptor+6);events=word(descriptor+16);actions=word(descriptor+12);mapping=word(descriptor+8)
 for state in range(1,states+1):
  for i in range(count):
   event=word(events+i*8);index=word(events+i*8+4)
   assert index<half(descriptor+2)
   action_index=half(mapping+(index*states+state-1)*2) if byte(descriptor+28) else byte(mapping+index*states+state-1)
   target=word(actions+action_index*4)
   u.mem_write(obj,bytes([group,state]));callbacks.clear()
   message=0x60001000
   for at,n in ((4,event),(8,0x12345678),(12,0x87654321)):put(message+at,n)
   call(dispatch,message)
   if target:
    assert len(callbacks)==1 and int(callbacks[0]['address'],16)==target
    assert callbacks[0]['arguments']==[obj,event,0x12345678,0x87654321]
    targets.add(target)
   else:assert not callbacks
   assert bytes(u.mem_read(obj,2))==bytes([group,state])
   rows.append(dict(group=group,state=state,event=hex(event),callback=hex(target)))
if not secondary:assert {0x61e10,0x6205c,0x62acc}<=targets
report=dict(passed=True,device_accessed=False,firmware_created=False,arm_cases=len(rows),
 native_factory_executed=True,native_dispatcher_executed=True,synchronous_callback_arguments_verified=True,
 factory_object=hex(obj),secondary=secondary,groups=groups,routes=rows,stock_sha256=hashlib.sha256(raw).hexdigest(),
 source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
 limits=['Callback bodies return modeled zero; RF/media/event resources are not executed.',
 'Synchronous routing preserves the incoming caller, but the upstream caller thread identity is not established.',
 'No radio ownership, cross-process interception, persistence, physical test or firmware package.'])
out=ROOT/('work/stock-wifi-secondary-fsm' if secondary else 'work/stock-wifi-fsm')/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,arm_cases=len(rows),device_accessed=False,report=(out/'report.json').relative_to(ROOT).as_posix(),factory_object=hex(obj)),indent=2))
