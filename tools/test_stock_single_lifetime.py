"""Original single-track constructor/prepare/callback/destructor ownership."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';cases=[]
for mode in ('row','empty','cancel'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for seg in ELFFile(io.BytesIO(raw)).iter_segments():
  if seg['p_type']!='PT_LOAD':continue
  a=int(seg['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(seg['p_memsz'])+4095)&~4095);u.mem_write(a,seg.data())
 area=0x71000000;u.mem_map(area,65536)
 impl,obj,client,query,out,source_id,owned_id,attributes,marker,done=(area+x for x in (0,0x5000,0x5200,0x5300,0x5400,0x6000,0x6100,0x6200,0xe000,0xff00))
 u.mem_write(impl,b'\x5a'*0x3000);u.mem_write(attributes,bytes(40));refs={'client':0,'query':0,'id':0};freed=[];return_from_query=[0]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def hook(uc,pc,size,ctx):
  r0,r1,r2,r3=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
  def finish(value=0):uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0x286028:assert r0==0x96bb3c;finish(impl);return
  if pc==0x27fa84:assert r0==client;refs['client']+=1;finish(client);return
  if pc==0x27f804:assert r0==query;refs['query']+=1;finish(query);return
  if pc==0x27e23c:
   assert (r0,r1,r2)==(impl,0x49a9bc,out);put(obj,1);put(obj+4,impl);put(obj+8,r1);put(out,obj);finish();return
  if pc==0x27fcb4:
   sp=uc.reg_read(UC_ARM_REG_SP);assert (r0,r2,r3)==(client,query,0) and get(sp)==1
   record=get(sp+8);assert get(record+4)==0x281430 and get(record+8)==impl+0x24
   if mode!='row':finish(0x106 if mode=='cancel' else 0);return
   return_from_query[0]=uc.reg_read(UC_ARM_REG_LR);uc.reg_write(UC_ARM_REG_R0,record);uc.reg_write(UC_ARM_REG_R1,0);uc.reg_write(UC_ARM_REG_R2,source_id);uc.reg_write(UC_ARM_REG_R3,attributes);uc.reg_write(UC_ARM_REG_LR,marker);uc.reg_write(UC_ARM_REG_PC,0x281430);return
  if pc==marker:uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,return_from_query[0]);return
  if pc==0x2995d0:assert r0==source_id;refs['id']+=1;finish(owned_id);return
  if pc==0x339780:finish();return
  if pc==0x2995e8:assert r0==owned_id;refs['id']-=1;finish();return
  if pc==0x27f758:assert r0==query;refs['query']-=1;finish();return
  if pc==0x27fa18:assert r0==client;refs['client']-=1;finish();return
  if pc==0x286058:assert (r0,r1)==(0x96bb3c,impl);freed.append(impl);finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(pc,*args):
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
 assert call(0x2817e4,client,query,out)==0 and get(out)==obj and get(impl)==0
 assert get(impl+0x24)==0x5a5a5a5a and refs=={'client':1,'query':1,'id':0}
 result=call(0x28194c,obj,0x123);assert result==(0 if mode=='row' else 0x2612 if mode=='empty' else 0x106)
 assert get(impl)==int(mode=='row') and get(impl+0x24)==(owned_id if mode=='row' else 0)
 call(0x2813dc,impl);assert refs=={'client':0,'query':0,'id':0} and freed==[impl]
 cases.append(dict(mode=mode,result=result,constructor_does_not_initialize_id_slot=True,prepared_flag_gates_id_ownership=True,original_id_callback_executed=mode=='row',balanced_cleanup=True))
w=ROOT/'work/stock-single-lifetime';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_constructor_prepare_callback_destructor=True,cases=cases,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_single_lifetime.py').read_bytes()).hexdigest(),limits=['Pools, generic sequence creation, client/query/ID clone/dispose and database delivery are modeled.','Original constructor, preparation, metadata callback and destructor execute; no actual DB, Met worker or hardware qualification.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
