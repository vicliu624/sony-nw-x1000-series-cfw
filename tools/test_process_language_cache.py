"""Original language selection -> external STX load/query/cleanup; PC Unicorn only."""
from pathlib import Path
import io,tarfile,json,hashlib,struct,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack;from resources import parse_stx
area=ROOT/'work/external-language-bridge-10-process-cache-final';meta=json.loads((area/'report.json').read_text());raw=(ROOT/meta['artifact']).read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['sha256'];elf=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value']for s in elf.get_section_by_name('.dynsym').iter_symbols()};base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';_,parts=unpack(base.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as archive:stock={lang:archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-'+lang+'.stx').read()for lang in ['en','jp','cs','ct']}
packroot='/contents/HOMEBREW/languages/';choice='/contents/HOMEBREW/data/language/ui-language';external=(ROOT/'dist/0.1.0-dev.16/language-packs/en/HOMEBREW/languages/en/wording.stx').read_bytes();wordings={lang:parse_stx(data)for lang,data in stock.items()};wordings['external']=parse_stx(external)
results=[]
rebuild_helpers={0x116d4,0x33d8c0,0x33b83c,0x119a0,0xb4b9c,0xb54e8,0xb4b84,0x14d74,0x3ce08,0x11938,0x48f38,0x48fe4,0x4a584,0x4a630,0x3dda4,0xb523c}
for case in ['en','jp','zh-CN','zh-TW','bad-digest','missing-resource','stock','missing-user-volume','mmap-failure','fxstat-error','read-error','cache-busy','getter-error']:
 files={choice:((case+'\n')if case in ['en','jp','zh-CN','zh-TW']else'stock\n'if case=='stock'else'en\n').encode()}
 for ident in ['en','jp','zh-CN','zh-TW']:
  p=ROOT/'dist/0.1.0-dev.16/language-packs'/ident/'HOMEBREW/languages'/ident;files[packroot+ident+'/language.ini']=(p/'language.ini').read_bytes()
  if (p/'wording.stx').exists():files[packroot+ident+'/wording.stx']=(p/'wording.stx').read_bytes()
 files[packroot+'en/wording.stx']=external
 for lang,data in stock.items():files['/usr/local/share/gemini/res/stx/ucs2-dev-'+lang+'.stx']=data
 if case=='bad-digest':b=bytearray(external);b[24]^=1;files[packroot+'en/wording.stx']=bytes(b)
 if case=='missing-resource':files.pop(packroot+'en/wording.stx')
 if case=='missing-user-volume':files={k:v for k,v in files.items()if not k.startswith('/contents/')}
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x100000);u.mem_map(0x62000000,0x1000000);u.mem_map(0x70000000,0x800000)
 state={'fd':40,'heap':0x62000000,'mapping':0x70000000,'failed_mmap':False,'recovery':False,'getter_status':1 if case=='getter-error'else 0};fds={};allocations={};mappings={};events=[]
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 def cstr(p):
  b=bytearray()
  for i in range(4096):
   c=bytes(u.mem_read(p+i,1))
   if c==b'\0':return bytes(b)
   b+=c
  raise AssertionError('Unterminated C string')
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r)for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];answer=0
  if pc in rebuild_helpers:events.append(['rebuild-helper',hex(pc)])
  elif pc==0x37f5c:assert a[:2]==[11,0xb00];uc.mem_write(a[2],bytes([setting]))
  elif pc==0x269b3c:assert a[:3]==[0xe6019c,123,0x3e8fcc];uc.mem_write(a[3],b'\x07');answer=state['getter_status']
  elif pc==0xe87f4:answer=0x60010000
  elif pc==0x115f1c:events.append(['font',cstr(a[0]).decode()])
  elif pc==0x1291a0:pass
  elif pc==syms['open']:
   name=cstr(a[0]).decode();assert not(state['recovery'] and name.startswith('/contents/')),('external IO during recovery',case,name);assert a[1]in (0,0x8800),hex(a[1]);events.append(['open',name,a[1]])
   if name not in files:answer=0xffffffff
   else:state['fd']+=1;answer=state['fd'];fds[answer]={'name':name,'bytes':files[name],'at':0}
  elif pc==syms['read']:
   assert a[0]in fds,a;f=fds[a[0]]
   if case=='read-error'and f['name'].endswith('/wording.stx')and f['name'].startswith(packroot):uc.reg_write(UC_ARM_REG_R0,0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   b=f['bytes'][f['at']:f['at']+a[2]];f['at']+=len(b)
   if b:uc.mem_write(a[1],b)
   answer=len(b)
  elif pc==syms['close']:
   if a[0]==0xffffffff:answer=0xffffffff
   else:assert a[0]in fds,('unexpected fd close',a[0]);events.append(['close',fds[a[0]]['name']]);del fds[a[0]]
  elif pc==syms['malloc']:
   assert 0<a[0]<=2097152;answer=state['heap'];state['heap']+=(a[0]+15)&~15;assert state['heap']<0x63000000;allocations[answer]=a[0]
  elif pc==syms['free']:assert a[0]in allocations;del allocations[a[0]]
  elif pc==syms['memset']:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);answer=a[0]
  elif pc in (syms['memcpy'],):uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));answer=a[0]
  elif pc==syms['memcmp']:
   x=bytes(uc.mem_read(a[0],a[2]));y=bytes(uc.mem_read(a[1],a[2]));answer=(x>y)-(x<y)
  elif pc==syms['strcmp']:x=cstr(a[0]);y=cstr(a[1]);answer=(x>y)-(x<y)
  elif pc==syms['strcpy']:uc.mem_write(a[0],cstr(a[1])+b'\0');answer=a[0]
  elif pc==syms['strcat']:uc.mem_write(a[0]+len(cstr(a[0])),cstr(a[1])+b'\0');answer=a[0]
  elif pc==syms['strlen']:answer=len(cstr(a[0]))
  elif pc==syms['sysconf']:assert a[0]==30;answer=4096
  elif pc==syms['__aeabi_uidivmod']:assert a[1];answer=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
  elif pc==syms['mmap']:
   assert a[0]==0
   fd=word(uc.reg_read(UC_ARM_REG_SP))
   if a[2:]==[3,0x22]:
    assert fd==0xffffffff and word(uc.reg_read(UC_ARM_REG_SP)+4)==0
    events.append(['anonymous-mmap',a[1]])
    if case=='mmap-failure':answer=0xffffffff
    else:
     answer=state['mapping'];state['mapping']+=0x100000
     uc.mem_write(answer,bytes(a[1]));mappings[answer]={'name':'anonymous-language-snapshot','size':a[1]}
    uc.reg_write(UC_ARM_REG_R0,answer&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert a[2:]==[1,1];assert fd in fds;f=fds[fd];events.append(['mmap',f['name'],a[1]])
   if case=='mmap-failure'and f['name'].startswith(packroot)and not state['failed_mmap']:state['failed_mmap']=True;answer=0xffffffff
   else:
    assert a[1]==(len(f['bytes'])+4095)&~4095;answer=state['mapping'];state['mapping']+=0x100000;assert state['mapping']<=0x70800000;uc.mem_write(answer,f['bytes']);
    if case=='mapped-data-corrupt'and f['name'].startswith(packroot):uc.mem_write(answer+24,bytes([f['bytes'][24]^1]))
    mappings[answer]={'name':f['name'],'size':a[1]}
  elif pc==syms['munmap']:
   if a[0]==0xffffffff:answer=0xffffffff
   else:assert a[0]in mappings and mappings[a[0]]['size']==a[1];del mappings[a[0]]
  elif pc==syms['__fxstat']:
   if case=='fxstat-error'and fds[a[1]]['name'].startswith(packroot):
    uc.reg_write(UC_ARM_REG_R0,0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert a[0]==3 and a[1]in fds;b=bytearray(88);struct.pack_into('<I',b,16,0o100644);struct.pack_into('<I',b,44,len(fds[a[1]]['bytes']));struct.pack_into('<I',b,48,4096);uc.mem_write(a[2],bytes(b))
  else:return
  uc.reg_write(UC_ARM_REG_R0,answer&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 # Hook only PLT and explicit backend boundaries, not every SHA instruction.
 u.hook_add(UC_HOOK_CODE,hook,begin=0xd000,end=0xe500)
 for address in [0x269b3c,0xe87f4,0x115f1c,0x1291a0,0x37f5c]+list(rebuild_helpers):u.hook_add(UC_HOOK_CODE,hook,begin=address,end=address)
 def call(pc,args=(),stop=0x50000000,limit=100000000):
  for r,n in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,n)
  u.reg_write(UC_ARM_REG_SP,0x600f0000);u.reg_write(UC_ARM_REG_LR,0x50000000);u.emu_start(pc,stop,count=limit);assert u.reg_read(UC_ARM_REG_PC)==stop,(case,hex(u.reg_read(UC_ARM_REG_PC)));return u.reg_read(UC_ARM_REG_R0)
 context=call(0xec864);u.mem_write(context,bytes(416));u.mem_write(context+80,struct.pack('<I',0xffffffff));u.mem_write(0x65e8ec,b'\x07')
 cache=int(meta['cache_address'],16)
 if case=='cache-busy':u.mem_write(cache,struct.pack('<I',1))
 assert call(0x3a25c,(123,0x3e8fcc,0x65e8ec),0x3a260)==(1 if case=='getter-error'else 0)
 setting=bytes(u.mem_read(0x65e8ec,1))[0]
 expected_setting={'en':1,'zh-CN':9,'zh-TW':10}.get(case,7)
 assert setting==expected_setting,(case,setting)
 assert not allocations and not fds
 external_case=case in ['en','zh-CN','zh-TW']
 # Entire user storage disappears before any binding or rebuild. No external
 # open/read is allowed from this point, including an initial failure latch.
 saved_files=files.copy()
 files={k:v for k,v in files.items()if not k.startswith('/contents/')}
 state['recovery']=True
 call(0xb5034,(setting,))
 source=case if case in ['zh-CN','zh-TW']else'external'if external_case else'jp'
 if case in ['zh-CN','zh-TW']:
  wordings[case]=parse_stx(saved_files[packroot+case+'/wording.stx'])
  assert any(x[0]=='font'and x[1].endswith('ucs2-dev-cs-ct.lcf')for x in events)
 query_ids=range(7310)if case in ['en','jp','zh-CN','zh-TW']else[0,2600,5003,6046,7308,7309]
 for ident in query_ids:
  pointer=call(0xeca30,(context,ident));expected=wordings[source][ident]
  if expected:assert bytes(u.mem_read(pointer,len(expected.encode('utf-16le'))+2))==expected.encode('utf-16le')+b'\0\0',(case,ident)
  else:assert pointer==0
 assert not allocations
 assert len(fds)==(0 if external_case else 1)
 owned=next((p for p,v in mappings.items()if v['name']=='anonymous-language-snapshot'),None)
 assert bool(owned)==external_case
 if external_case:assert word(context+72)==owned and len(mappings)==1
 call(0xec870,(context,));assert not fds and not allocations
 assert len(mappings)==(1 if external_case else 0)
 cycles=0
 if external_case:
  # Stock cleanup detaches only the cache view. Rebuild reuses exact address.
  for cycles in range(1,129):
   call(0x12ef8,(0x60020000,))
   assert word(context+72)==owned and len(mappings)==1 and not fds and not allocations
   pointer=call(0xeca30,(context,2600));expected=wordings[source][2600]
   if expected:assert bytes(u.mem_read(pointer,len(expected.encode('utf-16le'))+2))==expected.encode('utf-16le')+b'\0\0'
   call(0xec870,(context,));assert word(context+72)==0 and owned in mappings
  # Stock resources still own their ordinary mapping/fd, and cleanup releases it.
  call(0xb5034,(7,));assert len(mappings)==2 and len(fds)==1
  call(0xec870,(0,));assert len(mappings)==1 and not fds and owned in mappings
  # Another context can attach/detach without freeing the process-owned copy.
  other=0x60030000;u.mem_write(other,bytes(416))
  assert call(0xec46c,(other,word(cache+12)))==0
  assert word(other+72)==owned
  call(0xec870,(other,));assert owned in mappings and not fds
 # Preference changes apply to a new process, never reread during this session.
 files.update(saved_files);files[choice]=b'jp\n';state['getter_status']=0
 assert call(0x3a25c,(123,0x3e8fcc,0x65e8ec),0x3a260)==0
 assert bytes(u.mem_read(0x65e8ec,1))[0]==expected_setting
 assert not fds and not allocations
 results.append({'case':case,'setting':setting,'records_checked':len(query_ids),'original_rebuild_cleanup_cycles':cycles,'process_owned_mappings':len(mappings),'fds_after_cleanup':len(fds),'external_io_during_recovery':False,'events':events})
 print('Passed cached process:',case,flush=True)
pack_inputs={}
for ident in ['en','jp','zh-CN','zh-TW']:
 folder=ROOT/'dist/0.1.0-dev.16/language-packs'/ident/'HOMEBREW/languages'/ident
 pack_inputs[ident]={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in folder.iterdir()if p.is_file()}
report={'pack_inputs':pack_inputs,'passed':True,'candidate_sha256':meta['sha256'],'cases':results,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Exact patched startup getter, original12ef8/b5034, native STX query and cleanup hook/original cleanup trampoline. User storage absent and forbidden after startup. Other page/config/libc/mmap boundaries virtual. One intentional anonymous cache survives until process exit; no whole hardware sleep proof.','hardware_tested':False}
(area/'native-cache-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('All cached language lifecycle cases passed')
