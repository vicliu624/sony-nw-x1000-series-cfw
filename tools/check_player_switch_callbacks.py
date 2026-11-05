"""Pinned SpiderApp notification callbacks: original instructions, modeled queue."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
for notice,literal,entry,event in ((4,0xfdd0,0xea18,0x420015),(6,0xfdd8,0xeb9c,0x420024)):
 assert struct.unpack_from('<I',raw,literal-0x8000)[0]==entry
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;queued=[]
 def hook(cpu,pc,size,context):
  if pc==done:cpu.emu_stop();return
  if pc==0xa57f0:
   args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
   args.append(struct.unpack('<I',cpu.mem_read(cpu.reg_read(UC_ARM_REG_SP),4))[0]);queued.append(args)
  elif pc not in (0xe5ac,0x33b918):return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(entry,done+4,count=10000);assert u.reg_read(UC_ARM_REG_PC)==done
 assert queued==[[event,0,0,0,0]],queued
 rows.append(dict(notice=notice,registered_callback=hex(entry),registration_literal=hex(literal),queued=queued))
out=ROOT/'work/player-switch-callbacks'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,original_callback_instructions=True,queue_boundary_modeled=True,device_accessed=False,cases=rows,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,ROOT/'runtime/native/home_feedback.S',__import__('pathlib').Path(__file__))},limits=['Registration literal targets and callback instructions verified; original queue enqueue/log/getter effects modeled.','This does not execute root cleanup, manager process termination/restart or the complete GUI loop.','Different notifications are not proof of OS suspension, continued audio or owner-service availability.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
