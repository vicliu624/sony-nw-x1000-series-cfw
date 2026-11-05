"""Replay original Wi-Fi worker/direct-event routing; queue boundary modeled."""
import hashlib,io,json,struct,time
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
obj=0x60001000;message=0x60002000;fsm=0x60003000
def put(a,n):u.mem_write(a,struct.pack('<I',n))
trace=[];flags=[];hold=0;busy=0
def hook(uc,pc,size,unused):
 a,b,c,d=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==0x61d38:answer=fsm
 elif pc in (0x3b38c,0x3b3bc,0x3b3ec):flags.append([hex(pc),a]);answer=0
 elif pc==0xe5f4:answer=17
 elif pc==0xf674:assert a==17;put(b,hold);answer=0
 elif pc==0x3b3a4:answer=busy
 elif pc==0x61db4:assert a==message;trace.append('direct_fsm');answer=0
 elif pc==0x62f5c:assert a==message;trace.append('direct_other');answer=0
 elif pc==0x336abc:
  assert (a,b,c,d)==(91,message,16,0);trace.append('worker_queue');answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def syscall(*args):raise AssertionError('Unexpected actual syscall')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,syscall)
rows=[]
for event in [*range(0x4c0001,0x4c0012),0x4cc001,0x4c8008,0x4cc004,0x4c800c,0x4cd001,0x4c800f]:
 for group in (1,3):
  for hold in (0,1):
   for busy in (0,1):
    trace.clear();flags.clear();u.mem_write(fsm,bytes([group]));put(obj+16,91)
    for at,n in ((0,0),(4,event),(8,0x1234),(12,0x5678)):put(message+at,n)
    for reg,n in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,message),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,n)
    u.emu_start(0x3b994,0x50000000,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
    expected_flags=[]
    if event&0xffff<0x8000:
     if event==0x4c0001:
      expected_flags.append(['0x3b38c',1])
      if group==3:expected_flags.append(['0x3b3bc',1])
     if event==0x4c0005 and hold:expected=[]
     else:
      if event==0x4c0005:expected_flags.append(['0x3b38c',1])
      if event==0x4c000d and busy:
       expected_flags.extend([['0x3b3bc',0],['0x3b3ec',1]]);expected=[]
      else:expected=['direct_fsm' if event in (0x4c000d,0x4c0010,0x4c0011) else 'worker_queue']
    else:expected=['worker_queue' if event in (0x4cc001,0x4c8008,0x4cc004,0x4c800c,0x4cd001) else 'direct_other']
    assert trace==expected and flags==expected_flags,(hex(event),group,hold,busy,trace,flags)
    rows.append(dict(event=hex(event),group=group,hold=hold,busy=busy,route=trace,flags=flags))
report=dict(passed=True,device_accessed=False,firmware_created=False,arm_cases=len(rows),cases=rows,
 stock_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
 limits=['Original routing instructions execute; queue, flags, lock state and downstream dispatch are fixture boundaries.',
 'Worker creation is established separately by static pthread_create wrapper evidence, not by this replay.',
 'No installed interception, actual pthread scheduling, radio or hardware qualification.'])
out=ROOT/'work/stock-wifi-event-router'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,arm_cases=len(rows),device_accessed=False,report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
