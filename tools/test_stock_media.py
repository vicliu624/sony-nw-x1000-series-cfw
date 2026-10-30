"""Native Moma binding ABI/lifetime replay; database projection is modeled."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-media';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/stock_media.c','runtime/platform/player/stock_query.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/media_text.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/stock_info_host.c'];artifact=work/'reader.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
# Pin field meaning to the actual name/key registry, not modeled row values.
def named_key(name):
 text=name.encode()+b'\0';offset=stock.index(text)
 image=ELFFile(io.BytesIO(stock));addresses=[]
 for segment in image.iter_segments():
  if segment['p_type']=='PT_LOAD' and int(segment['p_offset'])<=offset<int(segment['p_offset'])+int(segment['p_filesz']):addresses.append(int(segment['p_vaddr'])+offset-int(segment['p_offset']))
 assert len(addresses)==1
 references=[];pattern=struct.pack('<I',addresses[0]);start=0
 while True:
  at=stock.find(pattern,start)
  if at<0:break
  if at>=4:references.append(struct.unpack_from('<I',stock,at-4)[0])
  start=at+4
 assert len(references)==1,(name,references)
 return references[0]
artist_key=named_key('MOMA_METADATA_KEY_ARTIST');album_key=named_key('MOMA_METADATA_KEY_ALBUM')
assert (artist_key,album_key)==(11,12)
assert named_key('MOMA_METADATA_KEY_FORMAT')==2
assert named_key('MOMA_METADATA_KEY_OBJECT_TYPE')==0 and named_key('MOMA_METADATA_KEY_MEDIA_TYPE')==1
assert named_key('MOMA_LC_METADATA_KEY_TITLE_INITIAL')==0xfe130002
assert named_key('MOMA_LC_METADATA_KEY_TITLE_SORTSTR')==0xfe130003
helper=artifact.read_bytes();elf=ELFFile(io.BytesIO(helper));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
cases=[]
for scenario in ('probe-audio','probe-video','probe-nonmedia','probe-missing-field','probe-unwritten-type','probe-wrong-scalar','probe-wrong-id','probe-missing-object','snapshot-page','snapshot-page-child','snapshot-page-empty','snapshot-page-full','snapshot-page-error','snapshot-search','snapshot-domainall','snapshot-child','snapshot-bad-query','snapshot-bad-parent','snapshot-eof','snapshot-error','snapshot-domain-failure','invalid-id','invalid-parent','format3-lists','format3-children','format3-wrong-parent','format3-missing-parent','format3-malformed','tracks','tracks-domain-failure','tracks-error','tracks-malformed','tracks-full','children','children-empty','children-error','children-malformed','children-full','utf16','utf8','missing-artist','truncated','malformed','oversized','repeat','inactive','invalid-token','missing-manager','connect-failure','client-allocation','id-allocation','query-failure','wrong-image','changed-code'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for raw in (stock,helper):
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 stack,area,done=0x70000000,0x71000000,0x72000000;u.mem_map(stack,65536);u.mem_map(area,131072);u.mem_map(done,4096)
 context,identity,out,client,manager,native_id,object_,metadata,plugin,text=(area+x for x in (0,0x100,0x1000,0x2000,0x3000,0x4000,0x5000,0x6000,0x7000,0x8000))
 callback=done+0x100
 child_list,list_table,child_id,child_impl,query,page_out=(area+x for x in (0x8600,0x8640,0x8800,0x8840,0x9000,0xa000))
 emitted=[0];list_live=[0];domain_live=[0];search_domain=area+0x8c00
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x6920c4,scenario!='inactive');put(0x692080,int(scenario in ('invalid-token','connect-failure')));put(0x692084,0 if scenario=='missing-manager' else manager)
 put(plugin+0x38,callback+4);put(plugin+0x30,callback+4);put(child_list,list_table);put(list_table,callback+12);put(list_table+12,callback+8);put(child_id,0x60fc60);put(child_id+4,child_impl);put(child_impl,1);put(child_impl+4,0);put(child_impl+8,0x124);put(object_+8,child_id)
 if scenario.startswith('probe-'):put(child_impl+8,0x124 if scenario=='probe-wrong-id' else 0x123)
 put(plugin+0x2c,callback);put(object_+24,metadata);put(native_id,0x60fc60)
 id_text=b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=123'
 u.mem_write(identity,id_text+b'\0');u.mem_write(out,b'\x5a'*844)
 title=[ord('T'),0x732b,0xd83d,0xde3a]
 if scenario=='truncated':title=[0x732b]*100
 if scenario in ('malformed','children-malformed','tracks-malformed','format3-malformed'):title=[0xd800]
 u.mem_write(text,struct.pack('<'+'H'*len(title),*title));u.mem_write(text+512,'Artist'.encode('utf-16-le'));u.mem_write(text+1024,b'Title UTF8 \xe7\x8c\xab')
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario=='changed-code':u.mem_write(0x295ce8,bytes([u.mem_read(0x295ce8,1)[0]^1]))
 live={'client':0,'id':0,'object':0,'guard':0};manager_refs=[1];queries=[]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  def finish(value=0):uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0x297ce0:
   assert uc.reg_read(UC_ARM_REG_R0)==0xab8764 and not live['client']
   if scenario=='client-allocation':finish();return
   live['client']=1;finish(client);return
  if pc==0x297d44:
   assert uc.reg_read(UC_ARM_REG_R0)==0xab8764 and uc.reg_read(UC_ARM_REG_R1)==client and live['client'];live['client']=0;finish();return
  if pc in (0x2963f4,0x29642c):assert uc.reg_read(UC_ARM_REG_R0)==manager;manager_refs[0]+=1 if pc==0x2963f4 else -1;finish();return
  if pc==0x28d704:
   assert uc.reg_read(UC_ARM_REG_R0)==1 and uc.reg_read(UC_ARM_REG_R1)==0 and get(uc.reg_read(UC_ARM_REG_R2))==0x123
   if scenario=='id-allocation':finish();return
   assert not live['id'];live['id']=1;finish(native_id);return
  if pc==0x29661c:
   assert uc.reg_read(UC_ARM_REG_R0)==manager and uc.reg_read(UC_ARM_REG_R1)==0 and uc.reg_read(UC_ARM_REG_R2)==19
   mask=uc.reg_read(UC_ARM_REG_R3)
   if get(mask+4)==1:assert scenario.startswith('format3-') and get(get(mask))==2
   elif scenario.startswith('probe-'):assert get(mask+4)==2 and struct.unpack('<2I',uc.mem_read(get(mask),8))==(0,1)
   else:assert get(mask+4)==3 and struct.unpack('<3I',uc.mem_read(get(mask),12))==(9,artist_key,album_key)
   assert not live['guard'];live['guard']=1;put(get(uc.reg_read(UC_ARM_REG_SP)),plugin);finish();return
  if pc==0x296464:
   name=b'moma-domain:MOMA_LC:DOMAINALL' if scenario=='snapshot-domainall' else b'moma-domain:MOMA_LC:FOLDERTREE'
   assert uc.reg_read(UC_ARM_REG_R0)==manager and uc.reg_read(UC_ARM_REG_R2)==len(name)
   assert bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1),len(name)))==name
   if scenario in ('tracks-domain-failure','snapshot-domain-failure'):finish(0x2214);return
   domain_live[0]=1;put(uc.reg_read(UC_ARM_REG_R3),search_domain);finish();return
  if pc==0x299670:
   assert uc.reg_read(UC_ARM_REG_R0)==search_domain and domain_live[0];finish(19);return
  if pc==0x299648:
   assert uc.reg_read(UC_ARM_REG_R0)==search_domain and domain_live[0] and not list_live[0];domain_live[0]=0;finish();return
  if pc==callback+4:
   frame=uc.reg_read(UC_ARM_REG_SP)
   assert live['guard'] and uc.reg_read(UC_ARM_REG_R0)==plugin and uc.reg_read(UC_ARM_REG_R3)==(search_domain if scenario.startswith('tracks') or scenario=='format3-lists' or (scenario.startswith('snapshot-') and scenario not in ('snapshot-child','snapshot-page-child','snapshot-bad-parent')) else native_id)
   if scenario.startswith('snapshot-'):
    root=get(frame);sort=get(frame+16)
    if scenario in ('snapshot-child','snapshot-page-child'):assert struct.unpack('<5I',uc.mem_read(root,20))==(1,0,9,0,0) and get(sort+4)==1 and struct.unpack('<2I',uc.mem_read(get(sort),8))==(0x22,0)
    else:assert get(root)==9 and get(sort+4)==2 and struct.unpack('<4I',uc.mem_read(get(sort),16))==(0xfe130002,0,9,1)
   elif scenario.startswith('tracks'):

    root=get(frame);assert get(root)==9 and get(root+4)==0xffffffff
    sort=get(frame+16);assert get(sort+4)==3 and struct.unpack('<6I',uc.mem_read(get(sort),24))==(0xfe130002,0,0xfe130003,0,9,0)
   elif scenario.startswith('format3-'):
    root=get(frame);assert struct.unpack('<5I',uc.mem_read(root,20))==(1,2 if scenario=='format3-lists' else 0,9,0,3 if scenario=='format3-lists' else 0)
    sort=get(frame+16)
    if scenario=='format3-lists':assert get(sort+4)==3 and struct.unpack('<6I',uc.mem_read(get(sort),24))==(0xfe130002,0,0xfe130003,0,9,0)
    else:assert get(sort+4)==1 and struct.unpack('<2I',uc.mem_read(get(sort),8))==(0x22,0)
   else:assert get(frame)==0
   assert get(frame+4)==7 and get(frame+8)==(1 if scenario.startswith('snapshot-') and not scenario.startswith('snapshot-page') else 3)
   if not scenario.startswith(('tracks','format3-','snapshot-')):assert get(frame+16)==0
   projection=get(frame+12);assert get(projection+4)==3
   list_live[0]=1;put(get(frame+20),child_list);finish();return
  if pc==callback+8:
   if scenario=='snapshot-eof':finish(0x2202);return
   if scenario=='snapshot-error':finish(0x106);return
   assert uc.reg_read(UC_ARM_REG_R0)==child_list and uc.reg_read(UC_ARM_REG_R1)==0 and list_live[0]
   if scenario in ('children-error','tracks-error','snapshot-page-error') and emitted[0]==1:finish(0x106);return
   if emitted[0]==(0 if scenario in ('children-empty','snapshot-page-empty') else 3 if scenario in ('children-full','tracks-full','snapshot-page-full') else 2):finish(0x2202);return
   assert not live['object'];live['object']=1;emitted[0]+=1
   put(uc.reg_read(UC_ARM_REG_R2),object_);finish();return
  if pc==callback+12:
   assert uc.reg_read(UC_ARM_REG_R0)==child_list and list_live[0];list_live[0]=0;finish();return
  if pc==callback:
   assert live['guard'] and uc.reg_read(UC_ARM_REG_R0)==plugin and uc.reg_read(UC_ARM_REG_R2)==native_id;queries.append(pc)
   if scenario.startswith('probe-'):
    projection=uc.reg_read(UC_ARM_REG_R3);assert get(projection+4)==2 and struct.unpack('<2I',uc.mem_read(get(projection),8))==(0,1)
   if scenario=='probe-missing-object':finish(0x2202);return
   if scenario=='query-failure':finish(0x210d);return
   assert not live['object'];live['object']=1;put(get(uc.reg_read(UC_ARM_REG_SP)),object_);finish();return
  if pc==0x29672c:assert live['guard'];live['guard']=0;finish();return
  if pc==0x2988f8 and scenario=='probe-unwritten-type' and uc.reg_read(UC_ARM_REG_R1)==0:finish();return
  if pc==0x298738:
   assert uc.reg_read(UC_ARM_REG_R0)==metadata;key=uc.reg_read(UC_ARM_REG_R1);kind=uc.reg_read(UC_ARM_REG_R2);dest=uc.reg_read(UC_ARM_REG_R3)
   if scenario.startswith('probe-'):
    assert key in (0,1) and kind==9
    if scenario=='probe-missing-field' and key==1:finish(0x2204);return
    if scenario=='probe-wrong-scalar':finish(0x220a);return
    put(dest,(1 if scenario=='probe-nonmedia' else 0) if key==0 else (2 if scenario=='probe-video' else 1));finish();return
   if key==2:
    assert kind==9 and scenario.startswith('format3-')
    if scenario=='format3-missing-parent':finish(0x2204);return
    put(dest,2 if scenario=='format3-wrong-parent' else 3);finish();return
   if key==artist_key and scenario=='missing-artist':finish(0x2204);return
   if key==9 and scenario=='utf8':
    if kind==11:finish(0x220a);return
    assert kind==10;put(dest,text+1024);put(dest+4,14);finish();return
   if kind!=11:finish(0x2209);return
   if key==9:put(dest,text);put(dest+4,32769 if scenario=='oversized' else len(title))
   elif key==artist_key:put(dest,text+512);put(dest+4,6)
   elif key==album_key:put(dest,0);put(dest+4,0)
   else:raise AssertionError(hex(key))
   finish();return
  if pc==0x2981f0:assert uc.reg_read(UC_ARM_REG_R0)==object_ and live['object'];live['object']=0;finish();return
  if pc==0x2995e8:assert uc.reg_read(UC_ARM_REG_R0)==native_id and live['id'];live['id']=0;finish();return
  if pc in (0x299694,0x33b918,0x33b83c,0x33d8c0):finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,v)
  for i,v in enumerate(args[4:]):put(stack+65520+i*4,v)
  u.emu_start(symbols[name],done+4,count=25000000);assert u.reg_read(UC_ARM_REG_PC)==done
  value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
 assert call('xw_stock_media_source_ready')==int(scenario not in ('wrong-image','inactive','invalid-token','missing-manager','connect-failure')),scenario
 rc=call('xw_stock_media_open',context)
 if scenario in ('wrong-image','changed-code','inactive','invalid-token','missing-manager','connect-failure','client-allocation'):
  assert rc==(-3 if scenario in ('wrong-image','changed-code') else -2) and not any(live.values()) and manager_refs[0]==1,(scenario,rc,live,manager_refs)
  cases.append(dict(case=scenario,open=rc));continue
 assert rc==0 and live['client']==1 and manager_refs[0]==2
 if scenario.startswith('probe-'):
  u.mem_write(out,b'\x5a'*76);prior=bytes(u.mem_read(out,76));assert call('xw_stock_media_validate_audio',context,identity,out)==-4
  put(symbols['xw_test_thread'],18);assert call('xw_stock_media_validate_audio',context,identity,0)==-1
  assert call('xw_stock_media_validate_audio',context,identity,context)==-1
  assert call('xw_stock_media_validate_audio',context,identity,identity)==-1
  result=call('xw_stock_media_validate_audio',context,identity,out)
  expected=0 if scenario=='probe-audio' else -3 if scenario in ('probe-video','probe-nonmedia') else -2 if scenario in ('probe-missing-field','probe-unwritten-type','probe-missing-object') else -5 if scenario=='probe-wrong-id' else -8
  assert result==expected,(scenario,result)
  if result:assert bytes(u.mem_read(out,76))==prior
  else:assert bytes(u.mem_read(out,65)).split(b'\0')[0]==id_text and struct.unpack('<2I',u.mem_read(out+68,8))==(0,1)
  assert live=={'client':1,'id':0,'object':0,'guard':0}
  assert call('xw_stock_media_close',context)==0 and manager_refs[0]==1 and not any(live.values())
  cases.append(dict(case=scenario,result=result,projected_fields_only=True,worker_error_cleanup=True));continue

 if scenario.startswith('snapshot-'):
  u.mem_write(query,bytes(1112));child=scenario in ('snapshot-child','snapshot-page-child','snapshot-bad-parent')
  put(query,int(child));put(query+4,0 if scenario=='snapshot-domainall' else 1);put(query+8,1);put(query+12,1 if child else 3);put(query+16,1 if child else 2)
  if child:u.mem_write(query+20,(b'invalid' if scenario=='snapshot-bad-parent' else id_text)+b'\0')
  nodes=[(1,0,9,0,0,0,0)] if child else [(9,0xffffffff,0,0,0,1 if scenario=='snapshot-bad-query' else 2,3),(1,0,9,0,0,0,0),(1,1,9,1,0,0,0)]
  for i,node in enumerate(nodes):u.mem_write(query+88+i*28,struct.pack('<7I',*node))
  u.mem_write(query+984,struct.pack('<2I',0x22,0) if child else struct.pack('<4I',0xfe130002,0,9,1));u.mem_write(page_out,b'\x5a'*844)
  if scenario.startswith('snapshot-page'):
   workspace=area+0x10000;size=16*844+8;u.mem_write(page_out,b'\x5a'*size);prior=bytes(u.mem_read(page_out,size))
   assert call('xw_stock_media_snapshot_page',context,query,7,3,workspace,page_out)==-4
   put(symbols['xw_test_thread'],18)
   for offset,limit in ((7,0),(7,17),(0x7fffffff,3)):
    assert call('xw_stock_media_snapshot_page',context,query,offset,limit,workspace,page_out)==-1
   assert call('xw_stock_media_snapshot_page',context,query,7,3,page_out,page_out)==-1
   result=call('xw_stock_media_snapshot_page',context,query,7,3,workspace,page_out)
   assert result==(-4 if scenario=='snapshot-page-error' else 0),(scenario,result)
   if result:assert bytes(u.mem_read(page_out,size))==prior
   else:
    count=0 if scenario=='snapshot-page-empty' else 3 if scenario=='snapshot-page-full' else 2
    assert get(page_out+16*844)==count and get(page_out+16*844+4)==int(count<3)
   assert not domain_live[0] and not list_live[0] and live=={'client':1,'id':0,'object':0,'guard':0}
   assert call('xw_stock_media_close',context)==0 and manager_refs[0]==1 and not any(live.values())
   cases.append(dict(case=scenario,result=result,paged_query=True,atomic_output=True,worker_error_cleanup=True));continue
  assert call('xw_stock_media_snapshot_one',context,query,7,page_out)==-4
  put(symbols['xw_test_thread'],18)
  assert call('xw_stock_media_snapshot_one',context,query,0xffffffff,page_out)==-1
  result=call('xw_stock_media_snapshot_one',context,query,7,page_out)
  expected=-8 if scenario in ('snapshot-bad-query','snapshot-bad-parent') else -5 if scenario=='snapshot-eof' else -4 if scenario=='snapshot-error' else -2 if scenario=='snapshot-domain-failure' else 0
  assert result==expected,(scenario,result)
  if result:assert bytes(u.mem_read(page_out,844))==b'\x5a'*844
  else:assert bytes(u.mem_read(page_out,65)).split(b'\0')[0]==id_text[:-3]+b'124' and bytes(u.mem_read(page_out+65,256)).split(b'\0')[0]=='T猫😺'.encode()
  assert not domain_live[0] and not list_live[0] and live=={'client':1,'id':0,'object':0,'guard':0}
  assert call('xw_stock_media_close',context)==0 and manager_refs[0]==1
  cases.append(dict(case=scenario,result=result,worker_error_cleanup=True));continue
 if scenario=='invalid-id':
  put(symbols['xw_test_thread'],18);u.mem_write(identity,b'invalid\0');assert call('xw_stock_media_fetch',context,identity,out)==-1
  assert call('xw_stock_media_close',context)==0 and not any(live.values()) and manager_refs[0]==1
  cases.append(dict(case=scenario,worker_error_cleanup=True));continue
 if scenario.startswith(('children','tracks','format3-','invalid-parent')):
  u.mem_write(query,id_text+b'\0'+b'\0'*(65-len(id_text)-1));put(query+68,7);put(query+72,3);put(query+76,2 if scenario=='format3-lists' else 3 if scenario.startswith('format3-') else int(scenario.startswith('tracks')))
  u.mem_write(page_out,b'\x5a'*(844*16+8))
  assert call('xw_stock_media_children',context,query,page_out)==-4
  put(symbols['xw_test_thread'],18)
  # Invalid count/overflow must not query or adopt an original list.
  put(query+72,0);assert call('xw_stock_media_children',context,query,page_out)==-1
  put(query+72,17);assert call('xw_stock_media_children',context,query,page_out)==-1
  put(query+72,3);put(query+68,0x7fffffff);assert call('xw_stock_media_children',context,query,page_out)==-1
  put(query+68,7)
  if scenario=='invalid-parent':u.mem_write(query,b'invalid\0')
  rc=call('xw_stock_media_children',context,query,page_out)
  expected=-1 if scenario=='invalid-parent' else -3 if scenario=='format3-wrong-parent' else -2 if scenario in ('tracks-domain-failure','format3-missing-parent') else -4 if scenario in ('children-error','tracks-error') else -8 if scenario in ('children-malformed','tracks-malformed','format3-malformed') else 0
  assert rc==expected,(scenario,rc)
  if rc:assert bytes(u.mem_read(page_out,844*16+8))==b'\x5a'*(844*16+8)
  else:
   count=0 if scenario=='children-empty' else 3 if scenario in ('children-full','tracks-full') else 2
   assert get(page_out+844*16)==count and get(page_out+844*16+4)==int(count<3)
   for index in range(count):
    assert bytes(u.mem_read(page_out+index*844,65)).split(b'\0')[0]==id_text[:-3]+b'124'
    assert bytes(u.mem_read(page_out+index*844+65,256)).split(b'\0')[0]=='T猫😺'.encode()
  assert not list_live[0] and not domain_live[0] and live=={'client':1,'id':0,'object':0,'guard':0}
  assert call('xw_stock_media_close',context)==0 and manager_refs[0]==1
  cases.append(dict(case=scenario,result=rc,emitted=emitted[0],balanced=True));continue
 assert call('xw_stock_media_fetch',context,identity,out)==-4 and not queries
 put(symbols['xw_test_thread'],18)
 for _ in range(100 if scenario=='repeat' else 1):
  rc=call('xw_stock_media_fetch',context,identity,out)
  expected=-8 if scenario in ('malformed','oversized') else -2 if scenario in ('id-allocation','query-failure') else 0
  assert rc==expected,(scenario,rc)
  if rc:assert bytes(u.mem_read(out,844))==b'\x5a'*844
  else:
   assert bytes(u.mem_read(out,65)).split(b'\0')[0]==id_text
   actual_title=bytes(u.mem_read(out+65,256)).split(b'\0')[0]
   expected_title=('猫'*85).encode() if scenario=='truncated' else b'Title UTF8 \xe7\x8c\xab' if scenario=='utf8' else 'T猫😺'.encode()
   assert actual_title==expected_title,(scenario,actual_title)
   assert get(out+840)==((5 if scenario=='missing-artist' else 7)|(256 if scenario=='truncated' else 0))
  assert live=={'client':1,'id':0,'object':0,'guard':0} and manager_refs[0]==2
 put(symbols['xw_test_thread'],19);assert call('xw_stock_media_close',context)==-4
 put(symbols['xw_test_thread'],18);assert call('xw_stock_media_close',context)==0 and not any(live.values()) and manager_refs[0]==1
 cases.append(dict(case=scenario,result=rc,queries=len(queries),balanced=True))
report=dict(passed=True,device_accessed=False,original_client_connect=True,original_metadata_registry_verified=True,original_manager_dispatch=True,original_text_getters=True,cases=cases,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_media.h','runtime/platform/player/media_text.h','tools/test_stock_media.py']},
 limits=['Loader identity, pools, manager retain/release/provider guard, ID creation/disposal, domain lookup/disposal, media-object disposal, logging and database-projected values are modeled.',
         'Original connection-token/client/get-object/get-domain/get-children/search/list-next dispatch and typed enum/ustr/cstr getter instructions execute; source text and resource states are synthetic.',
         'No background worker, native database access, sleep/USB behavior or hardware integration is qualified.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
