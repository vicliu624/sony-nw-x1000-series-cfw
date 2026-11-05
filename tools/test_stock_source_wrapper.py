"""Original single-item wrapper -> native admission -> temporary cleanup."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};cases=[]
for factory_error,allocation_failure in ((0,False),(0,True),(0x2202,False),(0x2202,True)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);audio=area;controller=area+0x1000;service=area+0x2000;descriptor=area+0x3000;item=area+0x4000;sequence=area+0x5000;impl=area+0x5100;table=area+0x5200;message=area+0x6000;destroy=area+0xe000;done=area+0xff00
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(audio,controller);put(audio+4,item);put(audio+8,descriptor);put(audio+16,6);put(descriptor,0);put(descriptor+4,item)
 counter=get(0x4aac4);put(counter,1);put(controller,service);put(controller+4,7);put(service+4,1);put(service+8,2);put(service+0x10,4);put(service+0x2c,service+0x28)
 put(sequence,1);put(sequence+4,impl);put(sequence+8,table);put(table,destroy);locks=set();freed=[];destroyed=[];pool_freed=[];factory=[];admissions=[];notifications=[];clones=[]
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
  if pc==0x283a38:
   assert args[:3]==(0x1122,0,item);factory.append(pc);put(args[3],0 if factory_error else sequence);value=factory_error
  elif pc==0xb6b40:value=0x1122
  elif pc==0x3c194:value=0x1234
  elif pc==0x27d360:value=1
  elif pc==0x27c378:
   assert args[:3]==(service,7,1);admissions.append(pc)
   if allocation_failure:value=0x302
   else:put(args[3],message)
  elif pc==symbols['MomaObjectId_clone']:assert args[0]==item;clones.append(item);value=item
  elif pc==0xa57f0:notifications.append(args)
  elif pc==symbols['free']:assert args[0]==descriptor;freed.append(descriptor)
  elif pc==destroy:assert args[0]==impl;destroyed.append(impl)
  elif pc==0x286058:assert args[1]==sequence;pool_freed.append(sequence)
  elif pc==0x335788:assert args[0] not in locks;locks.add(args[0])
  elif pc==0x3357e4:assert args[0] in locks;locks.remove(args[0])
  elif pc in (0xb6888,0x116d4,0x33b83c,0xac8e4,0x3c1a0,0x3c2d4,0x285d24,0x3365d8,0x3354f4):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,audio);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0xacc9c,done+4,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==1
 assert get(audio+8)==0 and get(counter)==0 and freed==[descriptor] and not locks
 assert len(factory)==len(admissions)==1 and clones==[item] and notifications[0][:3]==(0x53000c,0,item)
 assert get(audio+16)==6 # new source admission ticket is local, not this preparation ticket
 if allocation_failure:assert get(service+0x28)==0
 else:assert get(service+0x28)==message and get(message+0x24)==(0 if factory_error else sequence)
 expected_refs=1 if factory_error or not allocation_failure else 0
 assert get(sequence)==expected_refs
 assert len(destroyed)==len(pool_freed)==int(not factory_error and allocation_failure)
 cases.append(dict(factory_error=factory_error,allocation_failure=allocation_failure,wrapper_result=1,descriptor_freed=True,sequence_created=not factory_error,sequence_refs=get(sequence) if not factory_error else None,message_enqueued=not allocation_failure,preparation_ticket_unchanged=True))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_wrapper.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original wrapper, descriptor kind selection/free, controller admission/enqueue and sequence reference release execute.','Source factory, allocator/pools, ID clone/event consumers, metadata UI, mutex/ticket primitives and sequence destructor body are modeled.','Factory failure can still enqueue a null source; wrapper return1 is not installation success. No full GUI completion or audio output qualification.'])
p=ROOT/'work/player-stock-source-wrapper';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
