"""Original MetMm list constructors -> pointer-free query snapshot, ARM only."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
w=ROOT/'work/stock-query-snapshot';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/stock_info_host.c'];app=w/'snapshot.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
helper=app.read_bytes();symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(helper)).get_section_by_name('.symtab').iter_symbols()};cases=[];materialization_checks=[]
for scenario in ('search','children','empty','u64','cycle','too-many','string','domain-class','domain-index','parent-class','sort-limit','sort-direction','query-kind','unaligned'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for binary in (raw,helper):
  for segment in ELFFile(io.BytesIO(binary)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536)
 domain,domain_impl,parent,parent_impl,condition,sort,header,entries,tree,query,out,done=(area+x for x in (0x1000,0x1100,0x1200,0x1300,0x2000,0x2100,0x2200,0x2300,0x4000,0x7000,0x9000,0xf000))
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(domain,0x60fc40 if scenario=='domain-class' else 0x60fc48);put(domain+4,domain_impl);put(domain_impl,2 if scenario=='domain-index' else 1)
 put(parent,0 if scenario=='parent-class' else 0x60fc60);put(parent+4,parent_impl);put(parent_impl,1);put(parent_impl+8,0x321)
 put(condition,1);put(condition+4,0 if scenario=='empty' else tree);put(sort,1);put(sort+4,0 if scenario=='empty' else header);put(header,entries);put(header+4,17 if scenario=='sort-limit' else 2)
 for i,v in enumerate((0xfe130002,0,9,2 if scenario=='sort-direction' else 1)):put(entries+i*4,v)
 nodes=[(9,0xffffffff,0,0,0,0,tree+32,tree+64),(1,0,9,0,0,0xaabbccdd,0,0),(1,1,9,0,1,0,0,0)]
 if scenario=='u64':nodes=[(1,6,8,0,0x55667788,0x11223344,0,0)]
 if scenario=='cycle':nodes[0]=nodes[0][:6]+(tree,tree+64)
 if scenario=='string':nodes=[(1,9,11,0,0,0,0,0)]
 if scenario=='too-many':nodes=[(9,0xffffffff,0,0,0,0,tree+(i+1)*32,tree+2048) for i in range(32)]+[(1,1,9,0,0,0,0,0)]
 for i,row in enumerate(nodes):u.mem_write(tree+i*32,struct.pack('<8I',*row))
 put(0x8387fc,0x101000);put(0x83a8a4,0x102000);put(0x83ba7c,0x103000)
 refs=[1];locked=set();freed=[];child=scenario in ('children','parent-class')
 def hook(uc,pc,size,data):
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==done:uc.emu_stop();return
  if pc==0x286028:assert uc.reg_read(UC_ARM_REG_R0)==0x83ba80;finish(query);return
  if pc in (0x299630,0x2995d0):assert uc.reg_read(UC_ARM_REG_R0)==(parent if child else domain);refs[0]+=1;finish(parent if child else domain);return
  if pc in (0x299648,0x2995e8):assert uc.reg_read(UC_ARM_REG_R0)==(parent if child else domain);refs[0]-=1;finish();return
  if pc==0x335788:
   handle=uc.reg_read(UC_ARM_REG_R0);assert handle not in locked;locked.add(handle);finish();return
  if pc==0x3357e4:
   handle=uc.reg_read(UC_ARM_REG_R0);assert handle in locked;locked.remove(handle);finish();return
  if pc==0x286058:assert uc.reg_read(UC_ARM_REG_R0)==0x83ba80;freed.append(uc.reg_read(UC_ARM_REG_R1));finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,*args):
  u.reg_write(UC_ARM_REG_SP,area+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
  u.emu_start(address,done+4,count=2000000);assert u.reg_read(UC_ARM_REG_PC)==done
  v=u.reg_read(UC_ARM_REG_R0);return v if v<0x80000000 else v-0x100000000
 result_slot=area+0x8000
 assert call(0x27f5e4 if child else 0x27f520,parent if child else domain,condition,sort,result_slot)==0
 assert get(result_slot)==query and struct.unpack('<5I',u.mem_read(query,20))==(1,int(child),parent if child else domain,condition,sort)
 assert get(condition)==2 and get(sort)==2 and refs[0]==2 and not locked
 if scenario=='query-kind':put(query+4,2)
 source_before=bytes(u.mem_read(area+0x1000,0x7000));u.mem_write(out,b'\x5a'*1112)
 rc=call(symbols['xw_query_snapshot_copy'],query+int(scenario=='unaligned'),out)
 expected=0 if scenario in ('search','children','empty','u64') else -8 if scenario in ('cycle','unaligned') else -3
 assert rc==expected,(scenario,rc)
 assert bytes(u.mem_read(area+0x1000,0x7000))==source_before and not locked
 if rc:assert bytes(u.mem_read(out,1112))==b'\x5a'*1112
 else:
  head=struct.unpack('<5I',u.mem_read(out,20));assert head[:2]==(int(child),1)
  if child:assert bytes(u.mem_read(out+20,65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=321'
  else:assert bytes(u.mem_read(out+20,65))==bytes(65)
  if scenario=='empty':assert head[2:]==(0,0,0)
  elif scenario=='u64':assert head[2:]==(1,1,2) and struct.unpack('<7I',u.mem_read(out+88,28))==(1,6,8,0x55667788,0x11223344,0,0)
  else:
   assert head[2:]==(1,3,2)
   assert struct.unpack('<7I',u.mem_read(out+88,28))==(9,0xffffffff,0,0,0,2,3)
   assert struct.unpack('<7I',u.mem_read(out+116,28))==(1,0,9,0,0,0,0)
  if scenario!='empty':assert struct.unpack('<4I',u.mem_read(out+984,16))==(0xfe130002,0,9,1)
 if scenario in ('cycle','too-many','string','sort-limit','sort-direction'):
  failed_template=area+0xb000;u.mem_write(failed_template,b'\x5a'*1112)
  assert call(symbols['xw_query_snapshot_filter_copy'],condition,sort,failed_template)==rc
  assert bytes(u.mem_read(failed_template,1112))==b'\x5a'*1112
 if not rc:
  template=area+0xb000;child_snapshot=area+0xc000;identity=area+0xd000
  assert call(symbols['xw_query_snapshot_filter_copy'],condition,sort,template)==0
  assert struct.unpack('<2I',u.mem_read(template,8))==(0,0)
  assert bytes(u.mem_read(template+8,12))==bytes(u.mem_read(out+8,12)) and bytes(u.mem_read(template+88,1024))==bytes(u.mem_read(out+88,1024))
  text=b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=abc'
  u.mem_write(identity,text+bytes(65-len(text)))
  assert call(symbols['xw_query_snapshot_with_parent'],template,identity,child_snapshot)==0
  assert struct.unpack('<2I',u.mem_read(child_snapshot,8))==(1,1) and bytes(u.mem_read(child_snapshot+20,65)).split(b'\0')[0]==text
  assert bytes(u.mem_read(child_snapshot+88,1024))==bytes(u.mem_read(template+88,1024))
  before=bytes(u.mem_read(child_snapshot,1112));u.mem_write(identity,b'bad'+bytes(62))
  assert call(symbols['xw_query_snapshot_with_parent'],template,identity,child_snapshot)!=0 and bytes(u.mem_read(child_snapshot,1112))==before
  native=area+0xa000;u.mem_write(native,b'\x5a'*1164)
  assert call(symbols['xw_query_snapshot_validate'],out)==0
  assert call(symbols['xw_query_snapshot_materialize'],out,native)==0
  def normalized(address,depth=0):
   if not address:return None
   assert depth<33
   row=struct.unpack('<8I',u.mem_read(address,32))
   if row[0] in (9,10):return (row[0],row[1],row[2],normalized(row[6],depth+1),normalized(row[7],depth+1))
   return (row[0],row[1],row[2],row[4],row[5] if row[2] in (7,8) else 0)
  assert normalized(get(native+1160))==normalized(0 if scenario=='empty' else tree)
  assert struct.unpack('<2I',u.mem_read(native+1024,8))==((0,0) if scenario=='empty' else (native+1032,2))
  if scenario!='empty':assert struct.unpack('<4I',u.mem_read(native+1032,16))==(0xfe130002,0,9,1)
  materialization_checks.append(dict(case=scenario,native_tree_and_sort_roundtrip=True))
  if scenario=='search':
   valid=bytes(u.mem_read(out,1112))
   for label,offset,value,error in (('cycle',88+20,1,-8),('orphan',12,4,-8),('bad-edge',88+24,99,-8),('unsupported-kind',116+8,11,-3),('duplicate-edge',88+24,2,-8),('unused-high-word',116+16,1,-8),('sort-direction',984+4,2,-3),('sort-limit',16,17,-3)):
    u.mem_write(out,valid);put(out+offset,value);u.mem_write(native,b'\x5a'*1164)
    assert call(symbols['xw_query_snapshot_validate'],out)==error,label
    assert call(symbols['xw_query_snapshot_materialize'],out,native)==error,label
    assert bytes(u.mem_read(native,1164))==b'\x5a'*1164,label
    materialization_checks.append(dict(case=label,rejected_atomically=True))
   u.mem_write(out,valid);assert call(symbols['xw_query_snapshot_materialize'],out,out)==-1 and bytes(u.mem_read(out,1112))==valid
   materialization_checks.append(dict(case='overlap',rejected_atomically=True))
 if scenario=='query-kind':put(query+4,0)
 call(0x27f758,query);assert freed==[query] and refs[0]==1 and get(condition)==1 and get(sort)==1 and not locked
 cases.append(dict(case=scenario,result=rc,original_constructor=True,source_unchanged=True,original_cleanup_balanced=True))
report=dict(passed=True,original_list_constructors=True,original_condition_sort_reference_cleanup=True,source_handles_not_exported=True,cases=cases,materialization_checks=materialization_checks,device_accessed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/query_snapshot.h','tools/test_stock_query_snapshot.py']},limits=['Pool/mutex/domain-ID clone/release and input objects are modeled; original list construction and condition/sort reference instructions execute.','Caller must already own/retain and serialize with the source query; capture alone does not establish an active Met context.','No owner callback, uncached database execution, queue endpoint or hardware semantics is qualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
