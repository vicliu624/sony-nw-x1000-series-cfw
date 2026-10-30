"""Replay native object-fetch predicate and field0 column selection, PC only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-local-id-query';work.mkdir(exist_ok=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));cases=[]
for object_id in (1,0x12345678,0xffffffff):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 stack,area,done=0x70000000,0x71000000,0x72000000;u.mem_map(stack,65536);u.mem_map(area,65536);u.mem_map(done,4096)
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def string(a):
  value=bytes(u.mem_read(a,100));return value.split(b'\0')[0].decode('ascii')
 captured=[];queries=[];releases=[];formats=[]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0x29e460:
   descriptor=struct.unpack('<8I',uc.mem_read(uc.reg_read(UC_ARM_REG_R0),32));assert descriptor==(1,0,0x77,0,object_id,0,0,0)
   captured.append(descriptor);put(uc.reg_read(UC_ARM_REG_R1),area+0x2000);finish();return
  if pc==0x2a3b40:
   assert uc.reg_read(UC_ARM_REG_R1)==area+0x2000
   put(get(uc.reg_read(UC_ARM_REG_SP)+4),area+0x3000);queries.append(pc);finish();return
  if pc==0x29e4d8:assert uc.reg_read(UC_ARM_REG_R0)==area+0x2000;releases.append(pc);finish();return
  if pc==0xddd8:
   assert get(uc.reg_read(UC_ARM_REG_R0))==0 and uc.reg_read(UC_ARM_REG_R1)==0x6105a4 and uc.reg_read(UC_ARM_REG_R2)==1 and uc.reg_read(UC_ARM_REG_R3)==16
   finish(0x6105a4);return
  if pc==0x3397f4:
   fmt=string(uc.reg_read(UC_ARM_REG_R3));column=string(get(uc.reg_read(UC_ARM_REG_SP)))
   assert fmt=='obj.%s' and column=='object_id';formats.append((fmt,column))
   result=b'obj.object_id';uc.mem_write(uc.reg_read(UC_ARM_REG_R0),result+b'\0');put(uc.reg_read(UC_ARM_REG_R2),len(result));finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,args,extra=None):
  sp=stack+65520;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
  if extra is not None:put(sp,extra)
  u.emu_start(address,done+4,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
 assert call(0x2a417c,(area+0x1000,object_id,area+0x4000,0),area)==0
 assert len(captured)==len(queries)==len(releases)==1 and get(area)==area+0x3000
 put(0xc3c30c,1);put(0xc3c310,1);put(0xc3c314,0x6105a4);put(area+0x5000,area+0x6000)
 assert get(0x6105a4)==0 and get(0x6105a8)==0x77 and string(get(0x6105ac))=='object_id'
 assert call(0x2a6b30,(0,area+0x5000,area+0x7000,128),area+0x8000)==0
 assert formats==[('obj.%s','object_id')] and get(area+0x8000)==13
 cases.append(dict(object_id=object_id,predicate_field=captured[0][1],storage_type=hex(captured[0][2]),column='obj.object_id'))
report=dict(passed=True,device_accessed=False,stock_sha256=digest,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),original_predicate_and_column_instructions=True,cases=cases,
 limits=['Condition allocation/release, query execution, bsearch over the pinned field0 row and formatting are modeled.',
         'This is static-profile identity mapping evidence; no live database schema, ownership or metadata was read.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
