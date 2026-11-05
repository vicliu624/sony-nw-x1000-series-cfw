"""Original single-item factory and temporary query-descriptor ownership."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';cases=[]
for scenario in ('success','query-allocation','group-create','prepare-empty','prepare-busy'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);context=area;query=area+0x1000;group=area+0x2000;impl=area+0x3000;table=area+0x3100;item=area+0x4000;out=area+0x5000;destroy=area+0xe000;after_retain=area+0xe004;after_query_release=area+0xe008;done=area+0xff00
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 put(context,0x1122);put(out,0x5a5a5a5a);put(0x83ba7c,1);put(0x8386b4,2);query_pool=get(0x27f750);id_refs=[1];freed=[];locks=set();continuations={};created=[False]
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
  if pc==0x286028:assert args[0]==query_pool;value=0 if scenario=='query-allocation' else query
  elif pc==0x2995d0:assert args[0]==item;id_refs[0]+=1;value=item
  elif pc==0x2995e8:assert args[0]==item;id_refs[0]-=1
  elif pc==0x282b08:
   assert args[:2]==(0x1122,query) and get(query)==1 and get(query+4)==2 and get(query+8)==item
   if scenario=='group-create':value=0x302
   else:
    continuations['ctor']=(cpu.reg_read(UC_ARM_REG_LR),args[2]);cpu.reg_write(UC_ARM_REG_R0,query);cpu.reg_write(UC_ARM_REG_LR,after_retain);cpu.reg_write(UC_ARM_REG_PC,0x27f804);return
  elif pc==after_retain:
   lr,dest=continuations.pop('ctor');assert get(query)==2
   put(group,1);put(group+4,impl);put(group+8,table);put(table,destroy);put(dest,group);created[0]=True
   cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,lr);return
  elif pc==0x282c50:
   assert args[:2]==(group,0x123) and get(query)==2
   value=0x2612 if scenario=='prepare-empty' else 0x106 if scenario=='prepare-busy' else 0
  elif pc==destroy:
   assert args[0]==impl and get(group)==0 and get(query)==1
   continuations['dtor']=cpu.reg_read(UC_ARM_REG_LR);cpu.reg_write(UC_ARM_REG_R0,query);cpu.reg_write(UC_ARM_REG_LR,after_query_release);cpu.reg_write(UC_ARM_REG_PC,0x27f758);return
  elif pc==after_query_release:cpu.reg_write(UC_ARM_REG_PC,continuations.pop('dtor'));return
  elif pc==0x286058:
   assert args[:2] in ((query_pool,query),(0x8386b8,group));freed.append(args[:2])
  elif pc==0x335788:assert args[0] not in locks;locks.add(args[0])
  elif pc==0x3357e4:assert args[0] in locks;locks.remove(args[0])
  elif pc in (0x285d24,0x33d8c0,0x33b83c):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(pc,*args):
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done+4,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 result=call(0x283a38,context,0x123,item,out)
 expected=0 if scenario=='success' else 0x302 if scenario in ('query-allocation','group-create') else 0x2612 if scenario=='prepare-empty' else 0x106
 assert result==expected and get(out)==(group if not result else 0)
 if not result:assert get(group)==1 and get(query)==1 and id_refs[0]==2;call(0x27e774,group)
 assert id_refs[0]==1 and not locks and not continuations
 assert freed.count((query_pool,query))==int(scenario!='query-allocation') and freed.count((0x8386b8,group))==int(created[0])
 cases.append(dict(scenario=scenario,result=result,error_output_cleared=bool(result),caller_id_reference_preserved=True,all_temporary_and_returned_references_released=True))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_factory.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original factory, temporary descriptor create/retain/release and generic group release execute.','Group construction/preparation/destructor body, pool allocation, ID methods, mutexes and logging are modeled.','No real Moma database, full one-track constructor or complete GUI/playback transaction is qualified.'])
p=ROOT/'work/player-stock-source-factory';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
