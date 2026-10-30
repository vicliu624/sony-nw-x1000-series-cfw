"""Replay original Moma list wrappers; provider rows remain modeled."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R10,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for result in (0,0x2204,0x2214):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);base=a&~4095
  u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536)
 obj,table,out,callback,done=area,area+256,area+512,area+768,area+1024
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(obj,table);put(table,callback+4);put(table+12,callback)
 calls=[]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  if pc in (callback,callback+4):
   assert uc.reg_read(UC_ARM_REG_R0)==obj
   if pc==callback:
    assert uc.reg_read(UC_ARM_REG_R1)==16 and uc.reg_read(UC_ARM_REG_R2)==out
    put(out,0x12345678);calls.append('next')
   else:calls.append('dispose')
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,r0,r1=0,r2=0):
  for reg,value in ((UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_R2,r2),(UC_ARM_REG_SP,area+65520),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
  u.emu_start(address,done+4,count=1000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 assert call(0x298328,obj,16,out)==result
 assert get(out)==(0 if result else 0x12345678)
 call(0x29829c,obj);call(0x29829c,0)
 assert calls==['next','dispose']
 cases.append(dict(native_result=result,error_clears_output=bool(result),dispose_dispatch=True,null_dispose_noop=True))
# Replay Sony's actual enumeration consumer, not only the forwarding wrapper.
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for segment in ELFFile(io.BytesIO(raw)).iter_segments():
 if segment['p_type']!='PT_LOAD':continue
 a=int(segment['p_vaddr']);base=a&~4095
 u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
area=0x71000000;u.mem_map(area,65536)
obj,table,consumer,callback,consume_callback,dispose_callback=area,area+256,area+512,area+768,area+772,area+776
stack=area+32768;row=area+4096
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
put(obj,table);put(table,dispose_callback);put(table+12,callback);put(consumer,consume_callback);put(stack+32,obj)
seen=[];disposed=[];list_disposed=[]
def original_loop(uc,pc,size,data):
 def finish(v):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 if pc==0x27fe38:uc.emu_stop();return
 if pc==callback:
  assert uc.reg_read(UC_ARM_REG_R0)==obj and uc.reg_read(UC_ARM_REG_R1)==0
  dest=uc.reg_read(UC_ARM_REG_R2)
  if len(seen)==3:finish(0x2202)
  else:put(dest,row+len(seen)*64);finish(0)
 elif pc==0x298218:finish(uc.reg_read(UC_ARM_REG_R0)+32)
 elif pc==consume_callback:
  assert uc.reg_read(UC_ARM_REG_R0)==consumer
  index=uc.reg_read(UC_ARM_REG_R1);assert index==len(seen)
  assert uc.reg_read(UC_ARM_REG_R2)==row+index*64+32
  seen.append(index);finish(1)
 elif pc==0x2981f0:disposed.append(uc.reg_read(UC_ARM_REG_R0));finish(0)
 elif pc==dispose_callback:list_disposed.append(uc.reg_read(UC_ARM_REG_R0));finish(0)
u.hook_add(UC_HOOK_CODE,original_loop)
for reg,value in ((UC_ARM_REG_R4,0),(UC_ARM_REG_R6,consumer),(UC_ARM_REG_R7,obj),(UC_ARM_REG_R8,stack+24),(UC_ARM_REG_R10,0),(UC_ARM_REG_SP,stack)):u.reg_write(reg,value)
u.emu_start(0x27fe78,0x27fe3c,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==0x27fe38 and u.reg_read(UC_ARM_REG_R4)==0
assert seen==[0,1,2] and disposed==[row,row+64,row+128] and list_disposed==[obj]
cases.append(dict(original_consumer=True,rows=3,per_row_disposal=True,end_code=0x2202,end_maps_to_success=True,second_argument_context_zero=True))
# Nine-argument client call through the original manager guard and provider slot.
for provider_result in (0,0x106):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in ELFFile(io.BytesIO(raw)).iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095
  u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536)
 client,manager,plugin,callback,done,output=tuple(area+x for x in (0,256,512,768,1024,1280))
 stack=area+32768;context,identity,predicate,first,second,mask,sort=tuple(area+x for x in (1536,1792,2048,2304,2560,2816,3072))
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 put(client,1);put(client+4,manager);put(plugin+0x30,callback)
 for n,v in enumerate((first,second,mask,sort,output)):put(stack+n*4,v)
 steps=[]
 def query_dispatch(uc,pc,size,data):
  def finish(v):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==done:uc.emu_stop();return
  if pc==0x299610:
   assert uc.reg_read(UC_ARM_REG_R0)==identity;finish(19)
  elif pc==0x29661c:
   assert [uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]==[manager,context,19]
   # r3 is the original projection mask, used during provider admission.
   from unicorn.arm_const import UC_ARM_REG_R3
   assert uc.reg_read(UC_ARM_REG_R3)==mask
   guard=get(uc.reg_read(UC_ARM_REG_SP));put(guard,plugin);put(guard+4,0x5151);steps.append('acquire');finish(0)
  elif pc==callback:
   from unicorn.arm_const import UC_ARM_REG_R3
   assert [uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]==[plugin,context,0x5151,identity]
   frame=uc.reg_read(UC_ARM_REG_SP)
   assert [get(frame+n*4) for n in range(6)]==[predicate,first,second,mask,sort,output]
   put(output,0x12345678);steps.append('query');finish(provider_result)
  elif pc==0x29672c:
   assert uc.reg_read(UC_ARM_REG_R0)==manager;steps.append('release');finish(0)
 u.hook_add(UC_HOOK_CODE,query_dispatch)
 from unicorn.arm_const import UC_ARM_REG_R3
 for reg,value in ((UC_ARM_REG_R0,client),(UC_ARM_REG_R1,context),(UC_ARM_REG_R2,identity),(UC_ARM_REG_R3,predicate),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
 u.emu_start(0x295d38,done+4,count=3000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==provider_result
 assert get(output)==(0 if provider_result else 0x12345678) and steps==['acquire','query','release']
 cases.append(dict(client_nine_argument_forwarding=True,provider_result=provider_result,projection_admission=True,guard_release=True))
# Original UI query router: parent routing must replace the domain, not IDs
# passed through the predicate or metadata aggregation key.
for route,target in ((0,0x295de4),(1,0x295e90),(2,0x295d38)):
 for answer in (0,0x106):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095
   u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
  area=0x71000000;u.mem_map(area,65536);done=area+1024;stack=area+32768
  client,context,domain,predicate,key,offset,limit,mask,sort,parent,output=tuple(area+x for x in range(2048,2092,4))
  put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
  get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
  arguments=(key,offset,limit,mask,sort,int(route==1),int(route==2),parent,output)
  for n,value in enumerate(arguments):put(stack+n*4,value)
  seen=[]
  def routed(uc,pc,size,data):
   if pc==done:uc.emu_stop();return
   if pc in (0x295de4,0x295e90,0x295d38):
    assert pc==target
    from unicorn.arm_const import UC_ARM_REG_R3
    assert [uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]==[client,context,parent if route==2 else domain,predicate]
    frame=uc.reg_read(UC_ARM_REG_SP)
    expected=[key,offset,limit,mask,sort,output] if route==1 else [offset,limit,mask,sort,output]
    assert [get(frame+n*4) for n in range(len(expected))]==expected
    seen.append(pc);uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,routed)
  from unicorn.arm_const import UC_ARM_REG_R3
  for reg,value in ((UC_ARM_REG_R0,client),(UC_ARM_REG_R1,context),(UC_ARM_REG_R2,domain),(UC_ARM_REG_R3,predicate),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
  u.emu_start(0xaaef8,done+4,count=3000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==answer and seen==[target]
  cases.append(dict(original_ui_router=True,route=route,parent_replaces_domain=route==2,result=answer))
report=dict(passed=True,device_accessed=False,stock_sha256=hashlib.sha256(raw).hexdigest(),cases=cases,limits=['List provider callback is modeled; provider internals and database pagination remain unqualified; original consumer proves per-row disposal and maps 0x2202 exhaustion to success.'])
folder=ROOT/'work/stock-media-list';folder.mkdir(exist_ok=True)
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
