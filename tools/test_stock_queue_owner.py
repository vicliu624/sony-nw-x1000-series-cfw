"""Private Met-owner retained sequence adapter; source ownership is a precondition."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
w=ROOT/'work/stock-queue-owner';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/stock_queue_owner.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','runtime/platform/player/local_identity.c','tools/fixtures/stock_queue_owner_host.c'];app=w/'owner.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
helper=app.read_bytes();symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(helper)).get_section_by_name('.symtab').iter_symbols()};cases=[]
for scenario in ('group-plan','group-missing-query','group-bad-shuffle','single-ready','single-unready','single-bad-id','single-empty-page','query-search','query-children','query-missing','cache-linear','cache-shuffle','cache-miss','cache-cycle','cache-locked','cache-active-reader','cache-bad-id','cache-null-id','cache-bad-mutex','order-linear','order-shuffle','order-bad-map','order-many','order-wide16','order-unknown-type','held','replaced','wrong-thread','missing-session','missing-player','empty','unaligned','changed-code','wrong-image'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for binary in (raw,helper):
  for segment in ELFFile(io.BytesIO(binary)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,262144)
 state,session,player,sequence,replacement,table,impl,done=(area+x for x in (0,0x1000,0x2000,0x7000,0x7100,0x8000,0x8100,0x9000));destroy=done+256
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(session+0x20,0 if scenario=='missing-player' else player);put(player+0x3ca8,0 if scenario=='empty' else sequence)
 for seq in (sequence,replacement):put(seq,1);put(seq+4,impl);put(seq+8,table)
 put(table,destroy);put(0x8386b4,0x71ff0)
 track,track_impl,page_out=area+0xa000,area+0xb000,area+0x100
 if scenario.startswith(('single-','order-','cache-','query-')):
  put(sequence+8,0x49ab0c);put(impl+4,track);put(track+4,track_impl);put(track+8,0 if scenario=='order-unknown-type' else 0x49a910)
  put(track_impl+0x40,65537 if scenario=='order-many' else 65536 if scenario=='order-wide16' else 4);put(track_impl+8,int(scenario in ('order-shuffle','order-bad-map','cache-shuffle')))
  u.mem_write(track_impl+0x11a74,struct.pack('<4H',2,0,4 if scenario=='order-bad-map' else 3,1))
 if scenario.startswith('single-'):
  put(track+8,0x49a9bc);put(track_impl,0 if scenario=='single-unready' else 1);put(track_impl+8,1)
  single_id=area+0x30000;single_id_impl=area+0x30100;put(track_impl+0x24,0xdead0001 if scenario=='single-unready' else single_id)
  put(single_id,0x12345678 if scenario=='single-bad-id' else 0x60fc60);put(single_id+4,single_id_impl);put(single_id_impl,1);put(single_id_impl+4,0);put(single_id_impl+8,0x123)
 cache_out=area+0x300
 if scenario.startswith('cache-'):
  nodes=[area+0x21000+i*0x2000 for i in range(4)];ids=area+0x30000;id_impl=area+0x31000;mutex=area+0x2f000
  put(symbols['xw_test_mutex_address'],mutex);put(track_impl+0xc,mutex);put(track_impl+0x14,int(scenario=='cache-active-reader'))
  for physical,node in enumerate(nodes):
   put(node+8,physical);put(node+12,ids+physical*16);put(ids+physical*16,0x60fc60);put(ids+physical*16+4,id_impl+physical*16)
   put(id_impl+physical*16,1);put(id_impl+physical*16+4,9 if scenario=='cache-bad-id' and physical==1 else 0);put(id_impl+physical*16+8,0x100+physical)
  put(nodes[0],nodes[2]);put(nodes[2]+4,nodes[0]);put(nodes[1],nodes[3]);put(nodes[3]+4,nodes[1])
  put(track_impl+0x44,nodes[0]);put(track_impl+0x48,nodes[2]);put(track_impl+0x4c,nodes[1]);put(track_impl+0x50,nodes[3])
  if scenario=='cache-miss':put(track_impl+0x4c,nodes[3]);put(nodes[3]+4,0)
  if scenario=='cache-cycle':put(nodes[3],nodes[1])
  if scenario=='cache-null-id':put(nodes[1]+12,0)
  if scenario in ('cache-locked','cache-bad-mutex'):put(symbols['xw_test_mutex_result'],16 if scenario=='cache-locked' else 22)
 query_out=area+0x800
 if scenario.startswith(('query-','group-')):
  native_query=area+0x35000;native_domain=area+0x35100;domain_impl=area+0x35140;condition=area+0x35200;predicate=area+0x35300;sort=area+0x35500;header=area+0x35520;entries=area+0x35540;parent=area+0x35700;parent_impl=area+0x35800
  put(track_impl+0x3c,0 if scenario=='query-missing' else native_query);put(native_query,1);put(native_query+4,int(scenario=='query-children'));put(native_query+8,parent if scenario=='query-children' else native_domain);put(native_query+12,condition);put(native_query+16,sort)
  put(native_domain,0x60fc48);put(native_domain+4,domain_impl);put(domain_impl,1)
  put(parent,0x60fc60);put(parent+4,parent_impl);put(parent_impl,1);put(parent_impl+8,0x1234)
  put(condition,1);put(condition+4,predicate);u.mem_write(predicate,struct.pack('<8I',1,0,9,0,0,0,0,0))
  put(sort,1);put(sort+4,header);put(header,entries);put(header+4,1);put(entries,9)
 if scenario.startswith('group-'):
  put(sequence+8,0x49aa68);put(impl+0xc,0 if scenario=='group-missing-query' else native_query);put(impl+0x14,condition);put(impl+0x18,sort);put(impl+0x1c,4);put(impl+0x20,1);put(impl+0x100,2 if scenario=='group-bad-shuffle' else 0)
 if scenario=='changed-code':u.mem_write(0x27e74c,bytes([u.mem_read(0x27e74c,1)[0]^1]))
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 lock=[0];freed=[];destroyed=[]
 def hook(uc,pc,size,data):
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==done:uc.emu_stop();return
  if pc==0x335788:assert uc.reg_read(UC_ARM_REG_R0)==0x71ff0 and not lock[0];lock[0]=1;finish();return
  if pc==0x3357e4:assert uc.reg_read(UC_ARM_REG_R0)==0x71ff0 and lock[0];lock[0]=0;finish();return
  if pc==destroy:assert uc.reg_read(UC_ARM_REG_R0)==impl and lock[0];destroyed.append(pc);finish();return
  if pc==0x286058:assert uc.reg_read(UC_ARM_REG_R0)==0x8386b8 and lock[0];freed.append(uc.reg_read(UC_ARM_REG_R1));finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,*args):
  u.reg_write(UC_ARM_REG_SP,area+262128);u.reg_write(UC_ARM_REG_LR,done)
  from unicorn.arm_const import UC_ARM_REG_R2,UC_ARM_REG_R3
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.emu_start(address,done+4,count=20000000);assert u.reg_read(UC_ARM_REG_PC)==done
  v=u.reg_read(UC_ARM_REG_R0);return v if v<0x80000000 else v-0x100000000
 bind=call(symbols['xw_stock_queue_owner_bind'],state)
 if scenario in ('changed-code','wrong-image'):assert bind==-3;cases.append(dict(case=scenario,result=bind));continue
 assert bind==0
 key=area+0x1400;put(key,0x12345678);put(key+4,7);put(session+0x14,7)
 assert call(symbols['xw_stock_queue_owner_session_matches'],state,session,0x12345678,key)==0
 assert call(symbols['xw_stock_queue_owner_session_matches'],state,session,0x1234567c,key)==-5
 put(key+4,8);assert call(symbols['xw_stock_queue_owner_session_matches'],state,session,0x12345678,key)==-5;put(key+4,7)

 argument=0 if scenario=='missing-session' else session+1 if scenario=='unaligned' else session
 rc=call(symbols['xw_stock_queue_owner_acquire'],state,argument)
 if scenario in ('missing-session','missing-player','empty','unaligned'):
  assert rc==(-1 if scenario=='unaligned' else -2) and get(sequence)==1 and not lock[0]
  assert call(symbols['xw_stock_queue_owner_unbind'],state)==0;cases.append(dict(case=scenario,result=rc));continue
 assert rc==0 and get(sequence)==2 and not lock[0]
 assert call(symbols['xw_stock_queue_owner_acquire'],state,session)==-4 and get(sequence)==2
 assert call(symbols['xw_stock_queue_owner_unbind'],state)==-4
 if scenario.startswith('group-'):
  group_out=area+0x400;u.mem_write(group_out,b'\x5a'*2236);prior=bytes(u.mem_read(group_out,2236));native_before=bytes(u.mem_read(impl,0x104))
  result=call(symbols['xw_stock_queue_owner_group_plan'],state,group_out)
  expected=-2 if scenario=='group-missing-query' else -3 if scenario=='group-bad-shuffle' else 0;assert result==expected,(scenario,result)
  if result:assert bytes(u.mem_read(group_out,2236))==prior
  else:
   assert struct.unpack('<5I',u.mem_read(group_out,20))==(0,1,1,1,1)
   assert struct.unpack('<5I',u.mem_read(group_out+1112,20))==(0,0,1,1,1)
   assert struct.unpack('<3I',u.mem_read(group_out+2224,12))==(4,1,0)
  assert bytes(u.mem_read(impl,0x104))==native_before
 if scenario.startswith('single-'):
  u.mem_write(cache_out,b'\x5a'*1124);prior=bytes(u.mem_read(cache_out,1124));native_before=bytes(u.mem_read(track_impl,0x28))
  offset=1 if scenario=='single-empty-page' else 0
  result=call(symbols['xw_stock_queue_owner_cached_partial'],state,offset,2,cache_out)
  expected=-2 if scenario=='single-unready' else -3 if scenario=='single-bad-id' else 0
  assert result==expected,(scenario,result)
  if result:assert bytes(u.mem_read(cache_out,1124))==prior
  else:
   count=0 if offset else 1;assert struct.unpack('<4I',u.mem_read(cache_out,16))==(1,offset,count,1)
   assert get(cache_out+1120)==count
   if count:assert bytes(u.mem_read(cache_out+80,65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=123'
  assert bytes(u.mem_read(track_impl,0x28))==native_before
 if scenario.startswith('order-'):
  u.mem_write(page_out,b'\x5a'*80);prior=bytes(u.mem_read(page_out,80));native_before=bytes(u.mem_read(track_impl,0x11a80))
  assert call(symbols['xw_stock_queue_owner_order'],state,1,0,page_out)==-1
  assert call(symbols['xw_stock_queue_owner_order'],state,1,17,page_out)==-1
  order=call(symbols['xw_stock_queue_owner_order'],state,1,2,page_out)
  expected=-8 if scenario=='order-bad-map' else -3 if scenario in ('order-many','order-wide16','order-unknown-type') else 0
  assert order==expected,(scenario,order)
  if order:assert bytes(u.mem_read(page_out,80))==prior
  else:
   assert struct.unpack('<4I',u.mem_read(page_out,16))==(4,1,2,int(scenario=='order-shuffle'))
   assert struct.unpack('<2I',u.mem_read(page_out+16,8))==((0,3) if scenario=='order-shuffle' else (1,2))
   assert call(symbols['xw_stock_queue_owner_order'],state,5,2,page_out)==-1
   assert call(symbols['xw_stock_queue_owner_order'],state,4,2,page_out)==0 and get(page_out+8)==0
  assert bytes(u.mem_read(track_impl,0x11a80))==native_before and get(sequence)==2
 if scenario.startswith('cache-'):
  u.mem_write(cache_out,b'\x5a'*1120);prior=bytes(u.mem_read(cache_out,1120));native_before=bytes(u.mem_read(track_impl,0x11a80));nodes_before=[bytes(u.mem_read(n,16)) for n in nodes]
  cached=call(symbols['xw_stock_queue_owner_cached_ids'],state,1,2,cache_out)
  expected=-2 if scenario in ('cache-miss','cache-null-id') else -4 if scenario in ('cache-locked','cache-active-reader') else -3 if scenario=='cache-bad-id' else -8 if scenario=='cache-cycle' else -6 if scenario=='cache-bad-mutex' else 0
  assert cached==expected,(scenario,cached)
  if cached:assert bytes(u.mem_read(cache_out,1120))==prior
  else:
   assert struct.unpack('<4I',u.mem_read(cache_out,16))==(4,1,2,int(scenario=='cache-shuffle'))
   physicals=(0,3) if scenario=='cache-shuffle' else (1,2)
   for i,index in enumerate(physicals):
    assert bytes(u.mem_read(cache_out+80+i*65,65)).split(b'\0')[0]==('moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=%x'%(0x100+index)).encode()
  assert bytes(u.mem_read(track_impl,0x11a80))==native_before and [bytes(u.mem_read(n,16)) for n in nodes]==nodes_before
  assert not get(symbols['xw_test_mutex_locked']) and get(sequence)==2
  if scenario=='cache-miss':
   u.mem_write(cache_out,b'\x5a'*1124)
   assert call(symbols['xw_stock_queue_owner_cached_partial'],state,1,2,cache_out)==0
   assert get(cache_out+1120)==2
   assert bytes(u.mem_read(cache_out+145,65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=102'
   assert bytes(u.mem_read(cache_out+80,65))==bytes(65)
  assert get(symbols['xw_test_unlocks'])==(2 if scenario=='cache-miss' else int(scenario not in ('cache-locked','cache-bad-mutex')))
 if scenario.startswith('query-'):
  u.mem_write(query_out,b'\x5a'*1112);before=bytes(u.mem_read(native_query,0x900))
  result=call(symbols['xw_stock_queue_owner_query'],state,query_out)
  assert result==(-2 if scenario=='query-missing' else 0),(scenario,result)
  if result:assert bytes(u.mem_read(query_out,1112))==b'\x5a'*1112
  else:
   assert struct.unpack('<5I',u.mem_read(query_out,20))==(int(scenario=='query-children'),1,1,1,1)
   if scenario=='query-children':assert bytes(u.mem_read(query_out+20,65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=1234'
  assert bytes(u.mem_read(native_query,0x900))==before and get(sequence)==2
 if scenario=='wrong-thread':
  put(symbols['xw_test_thread'],18);assert call(symbols['xw_stock_queue_owner_release'],state)==-4 and get(sequence)==2;put(symbols['xw_test_thread'],17)
 if scenario=='replaced':
  put(player+0x3ca8,replacement);call(0x27e774,sequence);assert get(sequence)==1 and not destroyed
 assert call(symbols['xw_stock_queue_owner_release'],state)==0
 assert get(sequence)==(0 if scenario=='replaced' else 1) and get(replacement)==1 and not lock[0]
 assert len(destroyed)==int(scenario=='replaced') and freed==([sequence] if scenario=='replaced' else [])
 assert call(symbols['xw_stock_queue_owner_unbind'],state)==0
 cases.append(dict(case=scenario,retained_survives_replacement=scenario=='replaced',paired_original_reference_calls=True))
report=dict(passed=True,original_sequence_retain_release=True,original_count_shuffle_index_getters=True,nonmutating_cache_id_copy=True,cases=cases,device_accessed=False,owner_callback_installed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/stock_queue_owner.h','runtime/platform/player/query_snapshot.h','tools/fixtures/stock_info_host.c','tools/fixtures/stock_host_image.c','tools/test_stock_queue_owner.py']},limits=['The caller must already be in a qualified Met owner callback; binding a thread is not proof of that context.','Mutex/pool/destructor dependencies and source objects are modeled; original reference counter instructions execute.','Original count/shuffle-index getters execute against modeled sequence fields; cached IDs are synthetic; no real full grouped queue, callback installation or SDK queue support is qualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
