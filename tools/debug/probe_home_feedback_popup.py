"""Observe stock renderer initialization up to unsupported services, PC only."""
from pathlib import Path
import io,json,hashlib,struct,sys,tarfile,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UcError
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[2];parser=argparse.ArgumentParser();parser.add_argument('--message',choices=['homebrew','stock22'],default='homebrew');parser.add_argument('--output',required=True);parser.add_argument('--native-image-manager',action='store_true');parser.add_argument('--prepare-cache',action='store_true');parser.add_argument('--instruction-budget',type=int,default=2000000);args=parser.parse_args();assert 1<=args.instruction_budget<=100000000;out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT/'work');out.mkdir(exist_ok=False);message_id=745 if args.message=='homebrew' else 22;sys.path.insert(0,str(ROOT));from scripts.upg import unpack;from scripts.resources import parse_stx
package=(ROOT/'dist/0.1.0-dev.16/diagnostic-review-5/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes();assert hashlib.sha256(package).hexdigest()=='11f466c94d091c2a7bfb905beb3d94f81ab540dcc0bc33c38597c2ae34daa8cd'
_,components=unpack(package,require_stock=False);archive=tarfile.open(fileobj=io.BytesIO(components[3]),mode='r:gz');raw=archive.extractfile('./usr/local/bin/SpiderApp').read();assert hashlib.sha256(raw).hexdigest()=='91b28344c4839e0dc9ce967ce6101634c23dfc6b794c316acc4f4e3c3fe28d16'
message=parse_stx(archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-en.stx').read())[7309]
elf=ELFFile(io.BytesIO(raw));names={s['st_value']:s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_value']}
plt=elf.get_section_by_name('.plt');u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,0x20000);u.mem_map(0x60000000,0x1000000);sp=0x50018000;path=0x50001000;u.mem_write(path,b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf\0');import tarfile
font=archive.extractfile('./usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf').read()
u.mem_map(0x61000000,(len(font)+4095)&~4095);u.mem_write(0x61000000,font);position=[0]
gcc_data=archive.extractfile('./lib/libgcc_s.so.1').read();gcc_elf=ELFFile(io.BytesIO(gcc_data));gcc_base=0x10000000;u.mem_map(gcc_base,0x100000)
for segment in gcc_elf.iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(gcc_base+segment['p_vaddr'],segment.data())
gcc_symbols={symbol.name:symbol['st_value'] for symbol in gcc_elf.get_section_by_name('.dynsym').iter_symbols() if symbol['st_value']}
from elftools.elf.relocation import RelocationSection
from elftools.elf.enums import ENUM_RELOC_TYPE_ARM
relocation_count=0;unresolved_gcc=set()
main_symbols={sym.name:sym['st_value'] for sym in elf.get_section_by_name('.dynsym').iter_symbols() if sym['st_value']}
for section in gcc_elf.iter_sections():
 if not isinstance(section,RelocationSection):continue
 table=gcc_elf.get_section(section['sh_link'])
 for relocation in section.iter_relocations():
  kind=relocation['r_info_type'];address=gcc_base+relocation['r_offset'];addend=struct.unpack('<I',u.mem_read(address,4))[0]
  if kind==ENUM_RELOC_TYPE_ARM['R_ARM_RELATIVE']:value=gcc_base+addend
  elif kind in (ENUM_RELOC_TYPE_ARM['R_ARM_JUMP_SLOT'],ENUM_RELOC_TYPE_ARM['R_ARM_GLOB_DAT'],ENUM_RELOC_TYPE_ARM['R_ARM_ABS32']):
   symbol=table.get_symbol(relocation['r_info_sym'])
   if symbol['st_shndx']!='SHN_UNDEF':value=symbol['st_value']+(0 if symbol['st_shndx']=='SHN_ABS' else gcc_base)
   elif symbol.name in main_symbols:value=main_symbols[symbol.name]
   elif symbol['st_info']['bind']=='STB_WEAK':value=0
   else:unresolved_gcc.add(symbol.name);continue
   if kind==ENUM_RELOC_TYPE_ARM['R_ARM_ABS32']:value+=addend
  elif kind==ENUM_RELOC_TYPE_ARM['R_ARM_NONE']:continue
  else:raise AssertionError('Unsupported libgcc relocation '+str(kind))
  u.mem_write(address,struct.pack('<I',value&0xffffffff));relocation_count+=1
libc_member=archive.getmember('./lib/libc.so.6')
libc_data=archive.extractfile('./lib/'+libc_member.linkname if libc_member.issym() else libc_member).read()
libc_elf=ELFFile(io.BytesIO(libc_data));libc_base=0x11000000;u.mem_map(libc_base,0x400000)
for segment in libc_elf.iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(libc_base+segment['p_vaddr'],segment.data())
libc_symbols={symbol.name:symbol['st_value'] for symbol in libc_elf.get_section_by_name('.dynsym').iter_symbols() if symbol['st_value']}
libc_relocation_count=0;unresolved_libc=set();unsupported_libc_relocations=set()
for section in libc_elf.iter_sections():
 if not isinstance(section,RelocationSection):continue
 table=libc_elf.get_section(section['sh_link'])
 for relocation in section.iter_relocations():
  kind=relocation['r_info_type'];address=libc_base+relocation['r_offset'];addend=struct.unpack('<I',u.mem_read(address,4))[0]
  if kind==ENUM_RELOC_TYPE_ARM['R_ARM_RELATIVE']:value=libc_base+addend
  elif kind in (ENUM_RELOC_TYPE_ARM['R_ARM_JUMP_SLOT'],ENUM_RELOC_TYPE_ARM['R_ARM_GLOB_DAT'],ENUM_RELOC_TYPE_ARM['R_ARM_ABS32']):
   symbol=table.get_symbol(relocation['r_info_sym'])
   if symbol['st_shndx']!='SHN_UNDEF':value=symbol['st_value']+(0 if symbol['st_shndx']=='SHN_ABS' else libc_base)
   elif symbol.name in main_symbols:value=main_symbols[symbol.name]
   elif symbol.name in gcc_symbols:value=gcc_base+gcc_symbols[symbol.name]
   elif symbol['st_info']['bind']=='STB_WEAK':value=0
   else:unresolved_libc.add(symbol.name);continue
   if kind==ENUM_RELOC_TYPE_ARM['R_ARM_ABS32']:value+=addend
  elif kind==ENUM_RELOC_TYPE_ARM['R_ARM_NONE']:continue
  else:unsupported_libc_relocations.add(kind);continue
  u.mem_write(address,struct.pack('<I',value&0xffffffff));libc_relocation_count+=1
events=[];stop=[];heap=[0x60000000];streams={};next_fd=[7];next_mapping=[0x66000000];virtual_time_us=[1700000000000000];directories={};next_directory=[0x5001d000]
def string(a):
 b=bytearray()
 for n in range(4096):
  c=bytes(u.mem_read(a+n,1))
  if c==b'\0':return bytes(b)
  b.extend(c)
 raise AssertionError('Unterminated')
def hook(uc,pc,size,_):
 if not plt['sh_addr']<=pc<plt['sh_addr']+plt['sh_size']:return
 name=names.get(pc,'UNKNOWN_PLT');a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];events.append({'pc':hex(pc),'service':name,'args':a});result=0
 if name=='memset':uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
 elif name in ('memcpy','memmove'):uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
 elif name=='strlen':result=len(string(a[0]))
 elif name=='strncpy':
  text=string(a[1])[:a[2]];uc.mem_write(a[0],text+bytes(a[2]-len(text)));result=a[0]
 elif name in ('strcat','strncat'):
  left=string(a[0]);right=string(a[1]);right=right[:a[2]] if name=='strncat' else right;uc.mem_write(a[0],left+right+b'\0');result=a[0]
 elif name=='strchr':
  text=string(a[0])+b'\0';index=text.find(bytes([a[1]&255]));result=a[0]+index if index>=0 else 0
 elif name=='strcpy':uc.mem_write(a[0],string(a[1])+b'\0');result=a[0]
 elif name=='strncmp':
  left=string(a[0])[:a[2]];right=string(a[1])[:a[2]];result=(left>right)-(left<right)
 elif name=='memcmp':
  left=bytes(uc.mem_read(a[0],a[2]));right=bytes(uc.mem_read(a[1],a[2]));result=(left>right)-(left<right)
 elif name=='strcmp':left=string(a[0]);right=string(a[1]);result=(left>right)-(left<right)
 elif name in ('malloc','calloc'):
  n=a[0] if name=='malloc' else a[0]*a[1];assert 0<n<0x1000000 and heap[0]+n<=0x61000000;result=heap[0];heap[0]+=(n+7)&~7
 elif name=='free':pass
 elif name=='gettimeofday':
  if a[0]:uc.mem_write(a[0],struct.pack('<2i',virtual_time_us[0]//1000000,virtual_time_us[0]%1000000))
  if a[1]:uc.mem_write(a[1],bytes(8))
 elif name=='__errno_location':result=0x5001c000
 elif name=='opendir':
  prefix='./'+string(a[0]).decode().lstrip('/').rstrip('/')+'/'
  children=sorted({m.name[len(prefix):].split('/')[0] for m in archive.getmembers() if m.name.startswith(prefix) and m.name[len(prefix):]})
  if not children:events[-1]['missing_archive_directory']=prefix;uc.mem_write(0x5001c000,struct.pack('<I',2));result=0
  else:
   result=next_directory[0];next_directory[0]+=0x100;directories[result]={'prefix':prefix,'entries':['.','..',*children],'position':0}
 elif name=='readdir_r':
  directory=directories[a[0]]
  if directory['position']>=len(directory['entries']):uc.mem_write(a[2],struct.pack('<I',0))
  else:
   entry=directory['entries'][directory['position']];directory['position']+=1;filename=directory['prefix']+entry
   dtype=4 if entry in ('.','..') or archive.getmember(filename).isdir() else 8
   value=bytearray(268);struct.pack_into('<IIHB',value,0,directory['position'],directory['position'],268,dtype);value[11:11+len(entry.encode())]=entry.encode()
   uc.mem_write(a[1],bytes(value));uc.mem_write(a[2],struct.pack('<I',a[1]))
 elif name=='closedir':assert a[0] in directories;del directories[a[0]]
 elif name=='__xstat':
  assert a[0]==3;filename='./'+string(a[1]).decode().lstrip('/').rstrip('/')
  try:member=archive.getmember(filename)
  except KeyError:uc.mem_write(0x5001c000,struct.pack('<I',2));result=0xffffffff
  else:
   value=bytearray(88);struct.pack_into('<I',value,16,(0o040000 if member.isdir() else 0o100000)|member.mode);struct.pack_into('<I',value,44,member.size);uc.mem_write(a[2],bytes(value))
 elif name=='open':
  assert a[1]==0;filename=string(a[0]).decode();data=archive.extractfile('./'+filename.lstrip('/')).read();fd=next_fd[0];next_fd[0]+=1
  if filename.endswith('.lcf'):base=0x61000000
  else:
   base=next_mapping[0];size=(len(data)+4095)&~4095;next_mapping[0]+=size+4096;uc.mem_map(base,size);uc.mem_write(base,data)
  streams[fd]={'data':data,'position':0,'base':base,'path':filename};result=fd
 elif name=='read':
  stream=streams[a[0]];chunk=stream['data'][stream['position']:stream['position']+a[2]];stream['position']+=len(chunk)
  if chunk:uc.mem_write(a[1],chunk)
  result=len(chunk)
 elif name=='__fxstat':
  assert a[0]==3;uc.mem_write(a[2],bytes(88));uc.mem_write(a[2]+44,len(streams[a[1]]['data']).to_bytes(4,'little'))
 elif name=='sysconf':assert a[0]==30;result=4096
 elif name=='__aeabi_uidivmod':result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
 elif name=='mmap':
  assert a[2]==1 and a[3]==1;fd=struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0];result=streams[fd]['base']
 elif name in ('close','munmap'):pass
 elif name=='snprintf':
  text=(string(a[2]).decode()%(a[3],struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0])).encode();assert len(text)<a[1];uc.mem_write(a[0],text+b'\0');result=len(text)
 elif name=='__strtol_internal':
  import re
  assert a[1]==0 and a[2]==10;m=re.match(rb'[+-]?\d+',string(a[0]));result=int(m.group()) if m else 0
 elif name=='qsort':
  target=libc_base+libc_symbols[name];assert target%4==0;events[-1]['native_library']='candidate libc qsort';uc.reg_write(UC_ARM_REG_PC,target);return
 elif (name.startswith('__aeabi_') or name in ('__modsi3','__divsi3','__umodsi3','__udivsi3')) and name in gcc_symbols:
  target=gcc_base+gcc_symbols[name];assert target%4==0;events[-1]['native_library']='candidate libgcc_s.so.1';uc.reg_write(UC_ARM_REG_PC,target);return
 else:stop.append({'reason':'unsupported service','pc':hex(pc),'service':name});uc.emu_stop();return
 uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,path);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
try:u.emu_start(0x129d84,0x50019000,count=200000)
except (UcError,AssertionError) as error:stop.append({'reason':type(error).__name__,'text':str(error),'pc':hex(u.reg_read(UC_ARM_REG_PC)),'r0':hex(u.reg_read(UC_ARM_REG_R0)),'r1':hex(u.reg_read(UC_ARM_REG_R1)),'sp':hex(u.reg_read(UC_ARM_REG_SP)),'stack_return':hex(struct.unpack('<I',u.mem_read(u.reg_read(UC_ARM_REG_SP),4))[0])})
init_return=u.reg_read(UC_ARM_REG_R0);calls=[]
def services(uc,pc,size,_):
 if pc not in (0x115e28,0x11649c,0x132a78):return
 a=uc.reg_read(UC_ARM_REG_R0);calls.append({'pc':hex(pc),'arg0':a})
 answer=0
 if pc==0x132a78:
  if a==383*4936:answer=0x65000000
  else:
   assert 0<a and heap[0]+a<=0x61000000;answer=heap[0];heap[0]+=(a+7)&~7
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,services)
def call(address,register_args,end=0x50019000):
 for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),register_args):u.reg_write(reg,value)
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
 try:u.emu_start(address,end,count=args.instruction_budget)
 except Exception as error:stop.append({'reason':type(error).__name__,'text':str(error),'pc':hex(u.reg_read(UC_ARM_REG_PC)),'r0':hex(u.reg_read(UC_ARM_REG_R0)),'r1':hex(u.reg_read(UC_ARM_REG_R1)),'sp':hex(u.reg_read(UC_ARM_REG_SP)),'stack_return':hex(struct.unpack('<I',u.mem_read(u.reg_read(UC_ARM_REG_SP),4))[0])})
 return {'pc':hex(u.reg_read(UC_ARM_REG_PC)),'r0':u.reg_read(UC_ARM_REG_R0),'stopped_at_expected':u.reg_read(UC_ARM_REG_PC)==end}
style=(ROOT/'work/resource-analysis/style.dat').read_bytes();assert hashlib.sha256(style).hexdigest()=='84c29fb6747390c92ac28e9b3cab3410c2af28d40d12da83890b8c2d189a6635'
u.mem_map(0x64000000,(len(style)+4095)&~4095);u.mem_write(0x64000000,style);u.mem_write(0x754abc,struct.pack('<I',0x64000000));u.mem_map(0x65000000,0x200000)
manager=0x6dfa18
image_manager_initialized=call(0x11e9b8,[0x7a0660,0,0,0]) if args.native_image_manager else None
graphics_bookkeeping=call(0x119258,[0x761394,0,0,0])
global_initialized=call(0xe8800,[manager,0,0,0])
configured=call(0xe8b64,[manager,383,0,0]);opened=call(0xe9388,[manager,0,0,0],0xe948c)
stx_path=0x50001000;u.mem_write(stx_path,b'/usr/local/share/gemini/res/stx/ucs2-dev-en.stx\0');loaded=call(0xec8e4,[0x70b8dc,stx_path,0,0])
control=0x50008000;metadata=json.loads((ROOT/'work/home-feedback-resource-elf-review-1/build.json').read_text());descriptor=metadata['symbols']['hb_error_descriptor'] if args.message=='homebrew' else 0x4eb99c+22*48
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
baseline_slots=[0x65000000+i*4936 for i in range(383) if word(0x65000000+i*4936+0x460)&0x2001]
allocation_trace=[];constructor_trace=[]
def observe_alloc(uc,pc,size,_):
 if pc in (0xf344c,0xf4480,0xf58b0):
  constructor_trace.append({'tag':'DEBUG-pool-retain','pc':hex(pc),'result':uc.reg_read(UC_ARM_REG_R0),'template':uc.reg_read(UC_ARM_REG_R8) if pc==0xf58b0 else None})
 if pc==0xe9378:
  pointer=uc.reg_read(UC_ARM_REG_R0)
  allocation_trace.append({'tag':'DEBUG-pool-retain','pointer':hex(pointer),'caller':hex(word(uc.reg_read(UC_ARM_REG_SP)+8)),'r6_index':uc.reg_read(UC_ARM_REG_R6),'r8_template':uc.reg_read(UC_ARM_REG_R8)})
u.hook_add(UC_HOOK_CODE,observe_alloc)
created=call(0xc6880,[control,descriptor,0,0]) if not stop else None
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
content=word(control+40);text_control=word(content+0xafc) if content else 0
line_count=word(content+0xaf4) if content else None;content_height=word(content+0x3ac) if content else None
children=call(0xed074,[content,0,0,0]) if created and created['stopped_at_expected'] and not stop else None
show_target=call(0xc6ac4,[control,0,0,0]) if not stop else None
shown=call(0xc68f0,[control,show_target['r0'],show_target['r0'],0]) if not stop else None
pending_before=word(manager+0x788);active_before=word(manager+0x37c)
pending_objects=[0x65000000+i*4936 for i in range(383) if word(0x65000000+i*4936+0x460)&0x2000]
committed=call(0xe8de8,[manager,0,0,0],0xe8e58) if not stop else None
commit_ok=not stop and committed['stopped_at_expected'] and len(pending_objects)==pending_before and word(manager+0x788)==0 and word(manager+0x37c)==active_before+pending_before and all(word(p+0x460)&1 and not word(p+0x460)&0x2000 for p in pending_objects)
receiver=call(0x104870,[0,0,0,0]) if commit_ok else None
receiver_started=call(0x10490c,[receiver['r0'],0,0,0]) if commit_ok and not stop else None
frame_trace=[]
def observe_frame(uc,pc,size,_):
 if pc in (0xc743c,0xc75d0,0xc71b8,0x104a14,0x105498,0x107034,0x107134,0x1071ec,0x104f64):frame_trace.append(hex(pc))
u.hook_add(UC_HOOK_CODE,observe_frame)
upstream_before=word(0x74e22c)
frame_updated=call(0xe8de8,[manager,0,0,0]) if commit_ok else None
passed=frame_updated is not None and frame_updated['stopped_at_expected'] and frame_updated['r0']==0 and commit_ok and shown['stopped_at_expected'] and word(control+28)==1 and not stop and init_return==0 and global_initialized['stopped_at_expected'] and opened['stopped_at_expected'] and loaded['r0']==0 and created['stopped_at_expected'] and created['r0']==0 and word(control+24)==message_id and word(control+32)==descriptor and (args.message=='stock22' or (line_count==2 and content_height==80)) and 0x65000000<=content<0x65000000+383*4936 and text_control!=0
cache_cycles=[]
def prepare_live_popup(cycle):
 prepared=call(0xe91c4,[manager,0,0,0])
 if stop or not prepared['stopped_at_expected']:
  return {'cycle':cycle,'complete':False,'result':prepared,'stop':stop.copy()}
 current_content=word(control+40);current_text=word(current_content+0xafc)
 lookup=0x5001f000;image_query=call(0x132fd0,[word(current_text+0xb08),lookup,0,0])
 assert image_query['stopped_at_expected'] and image_query['r0']==0
 bitmap=struct.unpack('<16I',u.mem_read(word(lookup),64));width,height,flags=bitmap[:3]
 assert flags&8 and 0<width<=2048 and 0<height<=2048
 plane=bytes(u.mem_read(bitmap[6],width*height*3))
 return {'cycle':cycle,'complete':True,'result':prepared,'width':width,'height':height,'nonzero_bytes':sum(value!=0 for value in plane),'sha256':hashlib.sha256(plane).hexdigest()}
if passed and args.prepare_cache:
 cache_cycles.append(prepare_live_popup(1));passed=not stop and cache_cycles[-1]['complete'] and cache_cycles[-1]['nonzero_bytes']>0
text_kind_before_destroy=word(text_control+0xae4) if text_control else None
creation_and_frame_passed=passed
before_destroy={'pool_used':struct.unpack('<H',u.mem_read(manager+0x380,2))[0],'active':word(manager+0x37c),'pending':word(manager+0x788),'id':word(control+24)}
destroyed=call(0xc6a20,[control,0,0,0]) if passed else None
after_destroy={'pool_used':struct.unpack('<H',u.mem_read(manager+0x380,2))[0],'active':word(manager+0x37c),'pending':word(manager+0x788),'id':word(control+24)}
after_destroy_frame=call(0xe8de8,[manager,0,0,0]) if not stop and creation_and_frame_passed else None
final_pool={'pool_used':struct.unpack('<H',u.mem_read(manager+0x380,2))[0],'active':word(manager+0x37c),'pending':word(manager+0x788),'id':word(control+24)}
passed=creation_and_frame_passed and not stop and destroyed['stopped_at_expected'] and after_destroy_frame['stopped_at_expected'] and after_destroy_frame['r0']==0 and final_pool=={'pool_used':1,'active':1,'pending':0,'id':0}
repeat_cycles=[]
if creation_and_frame_passed and not stop:
 for cycle in range(2,5):
  create_cycle=call(0xc6880,[control,descriptor,0,0]);target_cycle=call(0xc6ac4,[control,0,0,0]);show_cycle=call(0xc68f0,[control,target_cycle['r0'],target_cycle['r0'],0]);frame_cycle=call(0xe8de8,[manager,0,0,0])
  if args.prepare_cache and not stop:cache_cycles.append(prepare_live_popup(cycle))
  delete_cycle=call(0xc6a20,[control,0,0,0]);finish_cycle=call(0xe8de8,[manager,0,0,0])
  repeat_cycles.append({'cycle':cycle,'pool_used':struct.unpack('<H',u.mem_read(manager+0x380,2))[0],'active':word(manager+0x37c),'pending':word(manager+0x788),'create_return':create_cycle['r0'],'frame_return':frame_cycle['r0'],'finish_return':finish_cycle['r0'],'all_returned':all(r['stopped_at_expected'] for r in [create_cycle,target_cycle,show_cycle,frame_cycle,delete_cycle,finish_cycle])})
  if stop:break
survivors=[{'address':hex(0x65000000+i*4936),'kind':word(0x65000000+i*4936+0xae4),'parent':hex(word(0x65000000+i*4936+0x4c4)),'owner':hex(word(0x65000000+i*4936+0xae8)),'flags':hex(word(0x65000000+i*4936+0x460))} for i in range(383) if word(0x65000000+i*4936+0x460)&0x2001]
j={'passed':passed,'diagnostic_tag':'DEBUG-pool-retain','comparison_message':args.message,'message_id':message_id,'cache_cycles':cache_cycles,'image_manager_initialized':image_manager_initialized,'constructor_trace':constructor_trace,'allocation_trace':allocation_trace,'repeat_cycles':repeat_cycles,'baseline_slots':list(map(hex,baseline_slots)),'surviving_objects':survivors,'text_control_kind_before_destroy':text_kind_before_destroy,'creation_and_frame_passed':creation_and_frame_passed,'before_destroy':before_destroy,'destroyed':destroyed,'after_destroy':after_destroy,'after_destroy_frame':after_destroy_frame,'final_pool':final_pool,'shown':shown,'show_state':word(control+28),'commit_prefix':committed,'pending_before':pending_before,'active_before':active_before,'active_after':word(manager+0x37c),'pending_objects':list(map(hex,pending_objects)),'native_commit_verified':commit_ok,'receiver':receiver,'receiver_started':receiver_started,'frame_update':frame_updated,'frame_trace':frame_trace,'upstream_before':upstream_before,'upstream_after':word(0x74e22c),'native_libc_sha256':hashlib.sha256(libc_data).hexdigest(),'native_libc_relocations':libc_relocation_count,'unresolved_libc_symbols':sorted(unresolved_libc),'unsupported_libc_relocations':sorted(unsupported_libc_relocations),'native_libgcc_relocations':relocation_count,'unresolved_libgcc_symbols':sorted(unresolved_gcc),'native_libgcc_sha256':hashlib.sha256(gcc_data).hexdigest(),'native_libgcc_helpers':sorted({event['service'] for event in events if event.get('native_library')}),'gettimeofday_is_fixture':True,'virtual_time_us':virtual_time_us[0],'content_control':hex(content),'text_control':hex(text_control),'line_count':line_count,'content_height':content_height,'native_child_query':children,'candidate_upg_sha256':hashlib.sha256(package).hexdigest(),'candidate_elf_sha256':hashlib.sha256(raw).hexdigest(),'scope':'Candidate5 message factory attempt with stock native pool/root prefix, stock style.dat, virtual file/libc/heap/display-init/allocation services','init_return':init_return,'graphics_bookkeeping':graphics_bookkeeping,'global_initialized':global_initialized,'configured':configured,'opened_prefix':opened,'stx_loaded':loaded,'created':created,'stop':stop,'services':calls,'events':events,'pool_used':struct.unpack('<H',u.mem_read(manager+0x380,2))[0],'pending_controls':word(manager+0x788),'control_id':word(control+24),'control_descriptor':hex(word(control+32)),'candidate5_changed':False,'physical_display_verified':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'report.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({k:j[k] for k in ['passed','image_manager_initialized','created','stop','repeat_cycles','before_destroy','after_destroy','final_pool','pool_used','pending_controls','text_control']},indent=2))
