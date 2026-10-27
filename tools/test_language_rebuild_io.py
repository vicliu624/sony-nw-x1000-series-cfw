"""Original language selection -> external STX load/query/cleanup; PC Unicorn only."""
from pathlib import Path
import io,tarfile,json,hashlib,struct,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack;from resources import parse_stx
area=ROOT/'work/external-language-bridge-8-ram-snapshot';meta=json.loads((area/'report.json').read_text());raw=(ROOT/meta['artifact']).read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['sha256'];elf=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value']for s in elf.get_section_by_name('.dynsym').iter_symbols()};base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';_,parts=unpack(base.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as archive:stock={lang:archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-'+lang+'.stx').read()for lang in ['en','jp','cs','ct']}
packroot='/contents/HOMEBREW/languages/';choice='/contents/HOMEBREW/data/language/ui-language';external=(ROOT/'dist/0.1.0-dev.16/language-packs/en/HOMEBREW/languages/en/wording.stx').read_bytes();wordings={lang:parse_stx(data)for lang,data in stock.items()};wordings['external']=parse_stx(external)
results=[]
rebuild_helpers={0x116d4,0x33d8c0,0x33b83c,0x119a0,0xb4b9c,0xb54e8,0xb4b84,0x14d74,0x3ce08,0x11938,0x48f38,0x48fe4,0x4a584,0x4a630,0x3dda4,0xb523c}
for case in ['en']:
 files={choice:((case+'\n')if case in ['en','jp','zh-CN','zh-TW']else'stock\n'if case=='stock'else'en\n').encode()}
 for ident in ['en','jp','zh-CN','zh-TW']:
  p=ROOT/'dist/0.1.0-dev.16/language-packs'/ident/'HOMEBREW/languages'/ident;files[packroot+ident+'/language.ini']=(p/'language.ini').read_bytes()
  if (p/'wording.stx').exists():files[packroot+ident+'/wording.stx']=(p/'wording.stx').read_bytes()
 files[packroot+'en/wording.stx']=external
 for lang,data in stock.items():files['/usr/local/share/gemini/res/stx/ucs2-dev-'+lang+'.stx']=data
 if case=='bad-digest':b=bytearray(external);b[24]^=1;files[packroot+'en/wording.stx']=bytes(b)
 if case=='missing-resource':files.pop(packroot+'en/wording.stx')
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x100000);u.mem_map(0x62000000,0x1000000);u.mem_map(0x70000000,0x800000)
 state={'delay_read':False,'blocked':False,'fd':40,'heap':0x62000000,'mapping':0x70000000,'failed_mmap':False};fds={};allocations={};mappings={};events=[]
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
  elif pc==0x269b3c:assert a[:3]==[0xe6019c,123,0x3e8fcc];uc.mem_write(a[3],b'\x07')
  elif pc==0xe87f4:answer=0x60010000
  elif pc==0x115f1c:events.append(['font',cstr(a[0]).decode()])
  elif pc==0x1291a0:pass
  elif pc==syms['open']:
   name=cstr(a[0]).decode();assert a[1]in (0,0x8800),hex(a[1]);events.append(['open',name,a[1]])
   if name not in files:answer=0xffffffff
   else:state['fd']+=1;answer=state['fd'];fds[answer]={'name':name,'bytes':files[name],'at':0}
  elif pc==syms['read']:
   assert a[0]in fds,a;f=fds[a[0]]
   if state['delay_read'] and f['name']==packroot+'en/wording.stx':
    state['blocked']=True;events.append(['blocked-read',f['name']]);uc.emu_stop();return
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
    if case=='snapshot-allocation-failure':answer=0xffffffff
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
 context=call(0xec864);u.mem_write(context,bytes(84));u.mem_write(context+80,struct.pack('<I',0xffffffff));u.mem_write(0x65e8ec,b'\x07')
 assert call(0x3a25c,(123,0x3e8fcc,0x65e8ec),0x3a260)==0
 setting=bytes(u.mem_read(0x65e8ec,1))[0];expected_setting=9 if case=='zh-CN'else 10 if case=='zh-TW'else 7 if case in ['jp','stock','bad-digest','missing-resource']else 1;assert setting==expected_setting,(case,setting);assert not allocations and not fds
 available_files=files.copy()
 if case=='removed-after-getter':files.pop(packroot+'en/wording.stx')
 call(0xb5034,(setting,));assert not allocations
 if case in ['zh-CN','zh-TW']:
  wordings[case]=parse_stx(files[packroot+case+'/wording.stx']);assert any(e[0]=='font'and e[1].endswith('ucs2-dev-cs-ct.lcf')for e in events)
 expected_source=case if case in ['zh-CN','zh-TW']else'external'if case=='en'else'en'if case in ['removed-after-getter','mmap-failure','mapped-data-corrupt','fxstat-error','snapshot-allocation-failure']else'jp'
 if case in ['en','zh-CN','zh-TW']:
  assert not fds,('external descriptor retained',case,fds)
  assert len(mappings)==1 and next(iter(mappings.values()))['name']=='anonymous-language-snapshot'
  # Remove every user-storage fixture after loading: all subsequent native
  # queries must use detached RAM, with no further external I/O.
  for name in list(files):
   if name.startswith('/contents/'):del files[name]
  events.append(['user-storage-unavailable-before-all-queries'])
 query_ids=range(7310)if case in ['en','jp','zh-CN','zh-TW']else[0,2600,5003,6046,7308,7309]
 for ident in query_ids:
  pointer=call(0xeca30,(context,ident));expected=wordings[expected_source][ident]
  if expected:encoded=expected.encode('utf-16le')+b'\0\0';assert bytes(u.mem_read(pointer,len(encoded)))==encoded,(case,ident)
  else:assert pointer==0
 assert len(fds)==(0 if case in ['en','zh-CN','zh-TW'] else 1) and len(mappings)==1
 loaded=next(iter(mappings.values()))['name'];assert loaded=='anonymous-language-snapshot'if case in ['en','zh-CN','zh-TW']else loaded.endswith('ucs2-dev-'+expected_source+'.stx'),(case,loaded)
 files.update(available_files)
 before=len(events)
 call(0x12ef8,(0x60020000,))
 normal_rebuild=events[before:]
 assert any(x[0]=='open' and x[1].startswith('/contents/') for x in normal_rebuild)
 assert not fds and not allocations and len(mappings)==1
 # Pause the exact patched rebuild at its read boundary; no return/fallback
 # is claimed while the underlying synchronous read has not returned.
 state['delay_read']=True
 u.reg_write(UC_ARM_REG_R0,0x60020000);u.reg_write(UC_ARM_REG_SP,0x600f0000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0x12ef8,0x50000000,count=100000000)
 assert state['blocked'] and u.reg_read(UC_ARM_REG_PC)==syms['read']
 assert allocations and fds
 state['delay_read']=False
 u.emu_start(syms['read'],0x50000000,count=100000000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and not allocations and not fds
 assert len(mappings)==1
 call(0xec870,(context,));assert not fds and not mappings and not allocations
 reload_cycles=0
 if case in ['en','zh-CN','zh-TW']:
  for reload_cycles in range(1,17):
   files.update(available_files)
   state['mapping']=0x70000000
   state['heap']=0x62000000
   call(0xb5034,(setting,))
   assert not fds and not allocations and len(mappings)==1
   assert next(iter(mappings.values()))['name']=='anonymous-language-snapshot'
   pointer=call(0xeca30,(context,2600))
   expected=wordings[expected_source][2600]
   if expected:assert bytes(u.mem_read(pointer,len(expected.encode('utf-16le'))+2))==expected.encode('utf-16le')+b'\0\0'
   call(0xec870,(context,))
   assert not fds and not allocations and not mappings
 results.append({'reload_cleanup_cycles':reload_cycles,'case':case,'setting':setting,'loaded':loaded,'queried_records':len(query_ids),'sample_ids':[0,2600,5003,6046,7308,7309],'original_cleanup_released_all':True,'events':events})
 print('Passed native external pipeline:',case,flush=True)
pack_inputs={}
for ident in ['en','jp','zh-CN','zh-TW']:
 folder=ROOT/'dist/0.1.0-dev.16/language-packs'/ident/'HOMEBREW/languages'/ident
 pack_inputs[ident]={'manifest_sha256':hashlib.sha256((folder/'language.ini').read_bytes()).hexdigest(),'wording_sha256':hashlib.sha256((folder/'wording.stx').read_bytes()).hexdigest()if(folder/'wording.stx').exists()else None}
report={'passed':True,'candidate_sha256':meta['sha256'],'cases':results,'pack_inputs':pack_inputs,'source_hashes':{str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'rebuild_io_confirmed':True,'blocked_read_resumed_without_leak':True,'scope':'Exact original12ef8 executes patched b5034; logging/config/other page services virtual. Delayed syscall is injected, not a measured device hang. RAM snapshot loaded, external fixtures removed before queries; not a hardware suspend/resume reproduction. Exact patched getter and original b5034/eb340/ec44c/ec8e4/ec9c4/eca30/ec870; file/heap/mmap/font/backend boundaries virtual; no full Sony boot or hardware','hardware_tested':False};(area/'language-rebuild-io.json').write_text(json.dumps(report,indent=2)+'\n');print('All native language-package and fallback cases passed')
