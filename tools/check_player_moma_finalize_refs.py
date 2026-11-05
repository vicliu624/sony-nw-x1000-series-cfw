"""Original Moma library finalize reference counters; release/panic effects modeled."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
def image_words(address,count):
 segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count*4<=s['p_vaddr']+s['p_filesz'])
 offset=int(segment['p_offset']+address-segment['p_vaddr'])
 return struct.unpack_from('<'+'I'*count,raw,offset)
for name,entry,literal,module in (('MomaLib_finalize',0x2958a8,0x295908,11),('MomaLcPluginLib_finalize',0x28babc,0x28bb1c,8)):
 counter=struct.unpack_from('<I',raw,literal-0x8000)[0]
 for initial in (0,1,2):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for s in elf.iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  area=0x71000000;u.mem_map(area,65536);done=area+0xff00;releases=[];panics=[]
  u.mem_write(counter,struct.pack('<I',initial))
  def hook(cpu,pc,size,context):
   if pc==done:cpu.emu_stop();return
   if pc==0x339af0:panics.append(pc);cpu.emu_stop();return
   if pc==0x33d9bc:releases.append(cpu.reg_read(UC_ARM_REG_R1));assert releases[-1]==module
   elif pc!=0x33d8c0:return
   cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(entry,done+4,count=10000);after=struct.unpack('<I',u.mem_read(counter,4))[0]
  assert after==max(initial-1,0) and bool(panics)==(initial==0) and releases==([module] if initial==1 else [])
  rows.append(dict(function=name,counter=hex(counter),initial=initial,after=after,table_release_counts=releases,panic_selected=bool(panics)))
pool_rows=[]
assert image_words(0x60f7cc,1)==(0x275dcc,)
for initial in (0,1):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;pool_releases=[]
 u.mem_write(0x822490,struct.pack('<I',initial))
 def pool_hook(cpu,pc,size,context):
  if pc==done:cpu.emu_stop();return
  if pc!=0x285f94:return
  pool_releases.append(cpu.reg_read(UC_ARM_REG_R0))
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,pool_hook);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(0x275dcc,done+4,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and pool_releases==[0x822494]
 assert struct.unpack('<I',u.mem_read(0x822490,4))[0]==0
 pool_rows.append(dict(initial_flag=initial,final_flag=0,pool_release_arguments=[hex(a) for a in pool_releases]))
dispatch_rows=[]
for name,entry,literal,table_literal,count in (
 ('MomaManager_finalize',0x288100,0x288160,0x288164,8),
 ('secondary-input-release',0xb6b18,0x275c80,0x275c84,4),
 ('MomaLib_finalize',0x2958a8,0x295908,0x29590c,11),
 ('MomaLcPluginLib_finalize',0x28babc,0x28bb1c,0x28bb20,8)):
 counter=image_words(literal,1)[0];table=image_words(table_literal,1)[0]
 expected=[image_words(table+index*12+8,1)[0] for index in reversed(range(count))]
 if name=='secondary-input-release':
  nested=[image_words(0x60f71c+index*12+8,1)[0] for index in reversed(range(15))]
  position=expected.index(0x275cbc)+1
  expected[position:position]=nested
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;observed=[];pool_dispatch=[]
 u.mem_write(counter,struct.pack('<I',1))
 u.mem_write(0x822490,struct.pack('<I',1))
 def dispatch_hook(cpu,pc,size,context):
  if pc==done:cpu.emu_stop();return
  if name=='secondary-input-release' and pc==0x285f94:
   pool_dispatch.append(cpu.reg_read(UC_ARM_REG_R0));cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
  if pc not in expected:return
  observed.append(pc)
  if name=='secondary-input-release' and pc in (0x275cbc,0x275dcc):return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,dispatch_hook);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(entry,done+4,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and observed==expected
 if name=='secondary-input-release':
  assert pool_dispatch==[0x822494] and struct.unpack('<I',u.mem_read(0x822490,4))[0]==0
 dispatch_rows.append(dict(function=name,table=hex(table),count=count,reverse_callbacks=[hex(a) for a in observed],nested_pool_release_arguments=[hex(a) for a in pool_dispatch]))
out=ROOT/'work/player-moma-finalize-refs'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,original_finalize_instructions=True,module_release_and_panic_intercepted=True,device_accessed=False,cases=rows,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,__import__('pathlib').Path(__file__))},limits=['Library initialization reference counters are not proven to count live Moma clients or SDK jobs.','Module release implementation, underlying manager lifetime and concurrent readers are not executed.','No library initialization/finalization call is added to the SDK; holding an extra init reference is not established as a drain substitute.'])
report['ctrlinfo_pool_finalizer_cases']=pool_rows
report['ctrlinfo_pool_finalizer_literal_reference']='0x60f7cc'
report['original_table_dispatch_cases']=dispatch_rows
report['limits'].append('Native reverse dispatch executes. Secondary input release also executes its thunk, nested table wrapper and pool finalizer; other leaf callbacks and pool release effects are intercepted.')
report['limits'].append('Root completion is tested separately; native live refcounts, concurrent users and physical teardown are not qualified.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
