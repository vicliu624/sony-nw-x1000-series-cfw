"""Experimental C source helper against original GUI handoff instructions."""
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
w=ROOT/'work/stock-source-submit';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/'+n+'.c' for n in ('stock_source','stock_gui','stock_image','local_identity')]+['runtime/native/sha256.c','tools/fixtures/stock_source_host.c'];artifact=w/'submit.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';image=ELFFile(io.BytesIO(raw));native={s.name:s['st_value'] for s in image.get_section_by_name('.dynsym').iter_symbols()};helper=artifact.read_bytes();symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(helper)).get_section_by_name('.symtab').iter_symbols()};cases=[]
for mode in (1,2):
 for scenario in ('accepted','rejected','same-ticket','filtered','filtered-after-move','id-allocation','source-off','bad-id','busy','wrong-thread','changed-descriptor-code','transition'):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for binary in (raw,helper):
   for segment in ELFFile(io.BytesIO(binary)).iter_segments():
    if segment['p_type']!='PT_LOAD':continue
    a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
  area=0x71000000;u.mem_map(area,65536);context=area;identity=area+0x100;output=area+0x300;actor=area+0x1000;controller=area+0x2000;item=area+0x3000;heap=area+0x4000;done=area+0xff00;audio=0x6922d8;allocations=[];disposed=[];callbacks=set();requests=[];post_dispatch=[0]
  def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
  put(0x6831dc,actor);put(actor+4,0x3f11d8);u.mem_write(actor,bytes((mode,5 if mode==1 else 2)));u.mem_write(actor+8,b'\xff\xff');u.mem_write(actor+13,b'\2')
  put(audio,controller);put(controller,area+0x6000);put(controller+4,7);put(audio+0x10,6)
  text=b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=123';u.mem_write(identity,text+bytes(65-len(text)));u.mem_write(output,b'\x5a'*12)
  for descriptor,count in ((0x3f1604,10),(0x3f11e0,7)):
   for offset in (20,24):
    table=get(descriptor+offset)
    if table:callbacks.update(get(table+4*i) for i in range(count) if get(table+4*i))
  def hook(uc,pc,size,data):
   r0,r1,r2,r3=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
   def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
   if post_dispatch[0] and pc==post_dispatch[0]:uc.reg_write(UC_ARM_REG_R0,1)
   if pc in callbacks:finish();return
   if pc==0x17c40 and get(r1+4)==0x44001d and scenario=='filtered':finish(1);return
   if pc==0x17c40 and get(r1+4)==0x44001d and scenario=='filtered-after-move':post_dispatch[0]=uc.reg_read(UC_ARM_REG_LR)
   if pc==0x28d704:
    assert (r0,r1)==(1,0) and struct.unpack('<2I',uc.mem_read(r2,8))==(0x123,0);allocations.append(item);finish(0 if scenario=='id-allocation' else item);return
   if pc==native['malloc']:assert r0==64;finish(heap);return
   if pc==0xac8e4:finish();return
   if pc in (0x116d4,0x33b83c):finish();return
   if pc==0x27d6a0:
    assert (r0,r1,r2,r3)==(controller,0,audio+0x38,audio+0x10);requests.append(pc);put(r3,0xffffffff if scenario=='rejected' else 6 if scenario=='same-ticket' else 7);finish(0x302 if scenario=='rejected' else 0);return
   if pc==0x2995e8:assert r0==item;disposed.append(item);finish();return
   if pc==0x27d54c:raise AssertionError('Source construction must await original stop completion')
  u.hook_add(UC_HOOK_CODE,hook)
  def call(name,*args):
   for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
   u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(symbols[name],done,count=30000000);assert u.reg_read(UC_ARM_REG_PC)==done;value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
  assert call('xw_stock_gui_bind',context)==0
  if scenario=='source-off':put(symbols['xw_test_source_ready'],0)
  if scenario=='bad-id':u.mem_write(identity,b'bad'+bytes(62))
  if scenario=='busy':put(context+4,1)
  if scenario=='wrong-thread':put(symbols['xw_test_thread'],18)
  if scenario=='changed-descriptor-code':u.mem_write(0x4ab70,bytes([u.mem_read(0x4ab70,1)[0]^1]))
  if scenario=='transition':u.mem_write(actor+1,b'\3')
  rc=call('xw_stock_source_submit',context,identity,output)
  expected=1 if scenario=='accepted' else -9 if scenario in ('rejected','same-ticket','filtered-after-move') else -4 if scenario in ('filtered','busy','wrong-thread','transition') else -1 if scenario=='bad-id' else -3 if scenario=='changed-descriptor-code' else -2
  assert rc==expected,(mode,scenario,rc)
  attempted,moved,ticket=struct.unpack('<3I',u.mem_read(output,12));handoff=scenario in ('accepted','rejected','same-ticket','filtered-after-move')
  assert moved==int(handoff) and attempted==int(handoff or scenario=='filtered')
  assert disposed==([item] if scenario=='filtered' else [])
  if handoff:assert get(audio+4)==item and get(audio+8)==heap and bytes(u.mem_read(actor,2))==bytes((1,7)) and len(requests)==1
  if scenario not in ('accepted','rejected','same-ticket','filtered','filtered-after-move','id-allocation'):assert not allocations and not requests
  cases.append(dict(mode=mode,case=scenario,result=rc,moved=bool(moved),disposed=len(disposed),ticket=ticket))
report=dict(passed=True,device_accessed=False,experimental_not_advertised=True,original_gui_and_descriptor_handoff=True,cases=cases,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/stock_source.h','tools/test_stock_source_submit.py']},limits=['Image/thread identity, source readiness, native ID/heap allocation, GUI callbacks and controller acceptance are modeled.','Original GUI filter/FSM, descriptor install and stop wrapper execute. Completion, recovery, consumer teardown and OOM remain unqualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
