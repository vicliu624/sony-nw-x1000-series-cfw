"""Native pending-token removal and command3 completion gate; no real cleanup."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for pcs_pending in (False,True):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536);root=area;tracker=area+0x1000;done=area+0xff00;finalizations=[];pcs=[];trace=[]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(root+4,3);put(root+0x2c,tracker)
 def hook(cpu,pc,size,context):
  if pc==done:cpu.emu_stop();return
  if pc==0x10ee4:finalizations.append(get(root+4))
  elif pc==0x1fd30:
   pcs.append(1);put(cpu.reg_read(UC_ARM_REG_R2),0x333 if pcs_pending else 0)
  elif pc not in (0xff5c,0x116d4,0x33b83c):return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(entry,a,b):
  u.reg_write(UC_ARM_REG_R0,a);u.reg_write(UC_ARM_REG_R1,b);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(entry,done+4,count=20000);assert u.reg_read(UC_ARM_REG_PC)==done
 for token in (0x111,0x222):call(0x48a14,tracker,token)
 assert get(tracker)==2
 for token,remaining in ((0x999,2),(0x111,1),(0x999,1),(0x222,1 if pcs_pending else 0)):
  call(0x11250,root,token);assert get(tracker)==remaining
  trace.append(dict(token=hex(token),pending=get(tracker),finalizations=len(finalizations)))
 assert len(finalizations)==(0 if pcs_pending else 1)
 if pcs_pending:
  assert get(tracker+4)==0x333 and get(root+8)==1;call(0x11250,root,0x333);assert finalizations==[3]
 # A completion replay on the now-empty tracker can reach completion again.
 # The body is intercepted: this test must never actually free native objects.
 call(0x11250,root,0x333 if pcs_pending else 0x222);assert finalizations==[3,3]
 rows.append(dict(pcs_pending=pcs_pending,trace=trace,completion_replay_reenters_finalizer=True,pcs_calls=len(pcs)))
out=ROOT/'work/player-pending-finalization'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,native_tracker_and_completion_instructions=True,finalizer_body_intercepted=True,device_accessed=False,cases=rows,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,__import__('pathlib').Path(__file__))},limits=['Command3 context and pending tokens are fixtures; no SDK token namespace or extra native tracker capacity is qualified.','PCS output and native finalizer effects modeled; native add/remove/query and completion gate execute.','Duplicate completion can reenter completion with the supplied retained context; full original post-finalize lifetime is not modeled.','No installed hook, real worker drain, power/USB or physical qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
