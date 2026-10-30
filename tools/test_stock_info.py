"""Original CtrlInfo getter/clone/release lifetime replay, without a device."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-info';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/stock_info_host.c'];artifact=work/'binding.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
assert stock[0x499068-0x8000:].split(b'\0',1)[0]==b'MetChapterInfo'
assert stock[0x499078-0x8000:].split(b'\0',1)[0].endswith(b'/MetChapterInfo.c')
helper=artifact.read_bytes();elf=ELFFile(io.BytesIO(helper));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
results=[]
for scenario in ('retained-objects','other-session-first','empty-objects','chapterless','local-id','max-id','zero-id','moved-id','metadata-id','unknown-class','unknown-domain','wrong-track-type','allocation','missing-session','unbound-controller','wrong-thread','wrong-image','changed-code'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for raw in (stock,helper):
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 stack,area,done=0x70000000,0x71000000,0x72000000;u.mem_map(stack,65536);u.mem_map(area,65536);u.mem_map(done,4096)
 context,out,handle,controller,session,data,info,owned,track,chapter=(area+x for x in (0,0x100,0x1000,0x2000,0x4000,0x5000,0x6000,0x7000,0x8000,0x9000))
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x6922d8,handle);put(handle,controller);put(handle+4,0xffffffff if scenario=='unbound-controller' else 7)
 put(controller+0xec8+0x118,0 if scenario=='missing-session' else session)
 put(session+8,1);put(session+12,1);put(session+20,7);put(session+28,data)
 if scenario=='other-session-first':
  other=area+0xf000;put(controller+0xec8+0x118,other);put(other,session);put(other+20,8)

 put(data,2);put(data+4,info);put(0x835de8,1);put(0x838744,3);put(0x822934,4)
 values=[0x7100f000,1,0,0]+[0]*22;values[11]=12345;values[12]=200000
 if scenario!='empty-objects':values[24]=track;values[25]=chapter
 if scenario=='chapterless':values[25]=0
 u.mem_write(info,struct.pack('<26I',*values));put(track+4,1);put(chapter,1);u.mem_write(out,b'\x5a'*104)
 payload,id_object,implementation=area+0xa000,area+0xb000,area+0xc000
 put(track,0 if scenario=='wrong-track-type' else 0x49a89c);put(track+8,payload);put(payload+4,id_object)
 put(id_object,0x12345678 if scenario=='unknown-class' else 0x60fc60);put(id_object+4,implementation)
 domain=0 if scenario=='max-id' else 7 if scenario=='unknown-domain' else 1
 number=0xffffffff if scenario=='max-id' else 0 if scenario=='zero-id' else 0x12345678
 put(implementation,domain);put(implementation+4,int(scenario=='metadata-id'));put(implementation+8,number)
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario=='changed-code':u.mem_write(0x27d510,b'\0')
 live=[False];allocations=[0];frees=[0];locks={1:0,2:0,3:0,4:0}
 def hook(uc,pc,size,user):
  if pc==done:uc.emu_stop();return
  def finish(value=0):uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc in (0x335788,0x3357e4):
   mutex=uc.reg_read(UC_ARM_REG_R0);assert mutex in locks;locks[mutex]+=1 if pc==0x335788 else -1;assert 0<=locks[mutex]<=1;finish();return
  if pc==0x286028:
   assert uc.reg_read(UC_ARM_REG_R0)==0x822494 and locks[2]==1
   if scenario=='allocation':finish();return
   assert not live[0];live[0]=True;allocations[0]+=1;finish(owned);return
  if pc==0x286058:
   assert uc.reg_read(UC_ARM_REG_R0)==0x822494 and uc.reg_read(UC_ARM_REG_R1)==owned and live[0]
   assert get(track+4)==1 and get(chapter)==1 and not any(locks.values())
   live[0]=False;frees[0]+=1;finish();return
  if pc==0xd85c:
   dst,src,n=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2));assert n==0x5c;uc.mem_write(dst,bytes(uc.mem_read(src,n)));finish(dst);return
  if pc in (0x285d24,0x33d8c0,0x33b83c):finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
  u.emu_start(name if isinstance(name,int) else symbols[name],done+4,count=20000000);assert u.reg_read(UC_ARM_REG_PC)==done
  value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
 rc=call('xw_stock_info_bind',context)
 if scenario in ('wrong-image','changed-code'):
  assert rc==-3 and not live[0];results.append(dict(case=scenario,bind=rc));continue
 assert rc==0
 # Execute the pinned generic MomaId constructor to establish the class/impl
 # layout used above, rather than relying only on a synthetic structure.
 call(0x299274,id_object,0x12345678 if scenario=='unknown-class' else 0x60fc60,implementation,0x1234)
 put(id_object+8,1)
 if scenario=='wrong-thread':put(symbols['xw_test_thread'],18)
 key_out=area+0xe000;u.mem_write(key_out,b'\x5a'*8)
 key_rc=call('xw_stock_info_session_key',context,key_out)
 assert key_rc==(-4 if scenario=='wrong-thread' else -2 if scenario=='unbound-controller' else 0)
 if not key_rc:assert struct.unpack('<2I',u.mem_read(key_out,8))==(controller+0xec8,7)
 else:assert bytes(u.mem_read(key_out,8))==b'\x5a'*8

 loops=1000 if scenario=='retained-objects' else 2 if scenario=='moved-id' else 1
 for _ in range(loops):
  rc=call('xw_stock_info_read',context,out)
  expected=-4 if scenario=='wrong-thread' else -2 if scenario in ('allocation','missing-session','unbound-controller') else 0
  assert rc==expected,(scenario,rc)
  if rc:assert bytes(u.mem_read(out,104))==b'\x5a'*104
  else:
   assert struct.unpack('<8I',u.mem_read(out,32))==(0,1,0,0,12345,200000,int(scenario!='empty-objects'),int(scenario not in ('empty-objects','chapterless')))
   valid=scenario not in ('empty-objects','metadata-id','unknown-class','unknown-domain','wrong-track-type')
   assert get(out+100)==int(valid)
   identity=bytes(u.mem_read(out+32,65)).split(b'\0')[0]
   expected_id=(f'moma-object:MOMA_LC;domain={"FOLDERTREE" if domain else "DOMAINALL"};type=MEDIA;id={number:x}').encode() if valid else b''
   assert identity==expected_id,(scenario,identity,expected_id)
   assert b'7100' not in identity
   if scenario=='moved-id':
    u.mem_write(area+0xd000,bytes(u.mem_read(id_object,16)));put(payload+4,area+0xd000)
  assert not live[0] and allocations[0]==frees[0] and not any(locks.values())
  assert get(session+8)==1 and get(track+4)==1 and get(chapter)==1 and get(id_object+8)==1
 if scenario=='wrong-thread':assert call('xw_stock_info_unbind',context)==-4;put(symbols['xw_test_thread'],17)
 assert call('xw_stock_info_unbind',context)==0
 results.append(dict(case=scenario,result=rc,reads=loops,allocations=allocations[0],frees=frees[0],retained_counts_unchanged=True))
report=dict(passed=True,device_accessed=False,original_controller_lookup=True,original_data_clone=True,original_object_retain_release=True,cases=results,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_info.h','tools/test_stock_info.py']},
 limits=['Pool allocation/free, mutex operations, memcpy and error logging are modeled; session lookup and release, CtrlInfo clone/dispose and track/chapter reference counts execute original code.',
         'Fields remain raw; no public state mapping, metadata extraction, timing units or installed service is claimed.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
