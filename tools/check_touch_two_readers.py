"""Original touch module open/queue/poll/GETVAL with two virtual file objects."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/icx_touch_screen.ko').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='73786cd7659db2534bf2cf8cee30615214c9938ec0a762b41ed70a076a5a08e9'
elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
u.mem_map(0x10000000,0x100000);u.mem_map(0x10100000,0x10000);u.mem_map(0x10200000,4096);u.mem_map(0x20000000,0x20000)
section_bases={};cursor=0x10000000
for i,s in enumerate(elf.iter_sections()):
 if s['sh_flags']&2 and s['sh_size']:
  cursor=(cursor+4095)&~4095;section_bases[i]=cursor
  if s['sh_type']!='SHT_NOBITS':u.mem_write(cursor,s.data())
  cursor+=s['sh_size']
assert cursor<0x10100000
symtab=elf.get_section_by_name('.symtab');external={};named={}
def address(symbol):
 index=symbol['st_shndx']
 if index=='SHN_UNDEF':
  if not symbol.name:return 0
  if symbol.name not in external:external[symbol.name]=0x10100000+len(external)*16
  return external[symbol.name]
 if index=='SHN_ABS':return symbol['st_value']
 return section_bases[index]+symbol['st_value']
for symbol in symtab.iter_symbols():
 if symbol.name and (symbol['st_shndx'] in section_bases or symbol['st_shndx'] in ('SHN_UNDEF','SHN_ABS')):named[symbol.name]=address(symbol)
relocation_types={}
for section in elf.iter_sections():
 if section['sh_type']!='SHT_REL' or section['sh_info'] not in section_bases:continue
 table=elf.get_section(section['sh_link'])
 for relocation in section.iter_relocations():
  place=section_bases[section['sh_info']]+relocation['r_offset'];kind=relocation['r_info_type'];value=struct.unpack('<I',u.mem_read(place,4))[0];symbol=table.get_symbol(relocation['r_info_sym']);target=address(symbol)
  relocation_types[str(kind)]=relocation_types.get(str(kind),0)+1
  if kind==2:value=(value+target)&0xffffffff
  elif kind==1:
   delta=value&0xffffff
   if delta&0x800000:delta-=0x1000000
   delta=delta*4+target-place
   assert delta%4==0 and -(1<<25)<=delta<(1<<25)
   value=(value&0xff000000)|((delta>>2)&0xffffff)
  elif kind==40:continue
  else:raise AssertionError(f'Unsupported relocation {kind}')
  u.mem_write(place,struct.pack('<I',value))
def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
for name in ('Semaphore','ListSemaphore','ModeSemaphore'):put(named[name],1)
head=named['icx_ts_list'];put(head,head);put(head+4,head)
put(named['Client'],0x20006000);put(0x2000600c,0x20006100);put(0x20016008,0xffffffff)
allocations=[];wakeups=[];mode_calls=[];mode_control_result=0;sample=bytearray(11);sample[1]=1;struct.pack_into('>HH',sample,2,1464,2640)
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
 if pc==named['icx_touch_screen_dev_ctl']:
  mode_calls.append(a[0]);result=mode_control_result
 elif pc==named['icx_touch_screen_i2c_transfer']:
  uc.mem_write(named['ReadBuff'],bytes(sample));result=2
 elif pc==external['kmem_cache_alloc']:
  result=0x20004000+len(allocations)*0x100;allocations.append(result)
 elif pc==external['__memzero']:uc.mem_write(a[0],bytes(a[1]))
 elif pc==external['memcpy']:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
 elif pc==external['__arch_copy_to_user']:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])))
 elif pc==external['__wake_up']:wakeups.append(a)
 elif 0x10100000<=pc<0x10110000:raise AssertionError(f'Unexpected external service {hex(pc)}')
 else:return
 uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr);u.reg_write(UC_ARM_REG_CPSR,0x13)
def call(name,values):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,0x20018000);u.reg_write(UC_ARM_REG_LR,0x10200000)
 u.emu_start(named[name],0x10200000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x10200000
 return u.reg_read(UC_ARM_REG_R0)
files=[0x20001000,0x20002000]
for file in files:assert call('icx_touch_screen_open',(0,file))==0
private=[word(file+0x80) for file in files];assert private==allocations and private[0]!=private[1]
rows=[]
for order in ((0,1),(1,0)):
 assert [call('icx_touch_screen_poll',(file,0)) for file in files]==[0,0]
 call('touch_screen_queue',())
 assert all(word(p+0xc)!=word(p+8) for p in private)
 sequence=[]
 for index in order:
  assert call('icx_touch_screen_poll',(files[index],0))==0x41
  assert call('icx_touch_screen_poll',(files[index],0))==0
  sequence.append(index)
  if len(sequence)==1:assert word(private[order[1]]+0xc)!=word(private[order[1]]+8)
  output=0x20008000+index*256
  assert call('icx_touch_screen_ioctl',(0,files[index],0x80045401,output))==0
  assert bytes(u.mem_read(output,11))==bytes(sample)
 rows.append({'poll_order':list(order),'ready_each_once':True,'same_getval_snapshot':True})
sample[1]=1
call('touch_screen_queue',())
pending_after_press=[word(p+0xc) for p in private]
sample[1]=0
call('touch_screen_queue',())
assert [word(p+0xc) for p in private]==pending_after_press
for index,file in enumerate(files):
 assert call('icx_touch_screen_poll',(file,0))==0x41
 assert call('icx_touch_screen_ioctl',(0,file,0x80045401,0x20008000+index*256))==0
 assert bytes(u.mem_read(0x20008000+index*256,11))==bytes(sample)
 assert call('icx_touch_screen_poll',(file,0))==0
mode_cases=[]
for old_mode,mode_control_result in ((1,0),(0,0),(0,-121)):
 put(named['DirverReady'],1);put(named['DeviceModeState'],old_mode);mode_calls.clear()
 before_private=[bytes(u.mem_read(p,16)) for p in private];before_snapshot=bytes(u.mem_read(named['GetValBuff'],11))
 result=call('icx_touch_screen_ioctl',(0,files[1],0x5404,0))
 assert mode_calls==([] if old_mode==1 else [1])
 assert result==((mode_control_result if old_mode==0 else 0)&0xffffffff)
 assert word(named['DeviceModeState'])==(1 if old_mode==1 or mode_control_result==0 else 0)
 assert word(named['Semaphore'])==word(named['ModeSemaphore'])==1
 if old_mode==1:
  assert [bytes(u.mem_read(p,16)) for p in private]==before_private
  assert bytes(u.mem_read(named['GetValBuff'],11))==before_snapshot
 mode_cases.append({'initial_mode_fixture':old_mode,'device_control_result_fixture':mode_control_result,'normal_ioctl_return':result,'device_control_calls':mode_calls.copy(),'mode_after':word(named['DeviceModeState']),'already_normal_preserves_private_and_snapshot':True if old_mode==1 else None})
report={'module_sha256':digest,'relocation_counts':relocation_types,'private_objects':[hex(p) for p in private],'cases':rows,'burst_observation':{'press_then_release_before_poll':True,'getval_contact_byte_each':0,'readiness_latched_once_each':True},'normal_mode_cases':mode_cases,'wake_count':len(wakeups),'limits':['ET_REL sections loaded at virtual bases; ABS32/PC24 relocations applied, external kernel services and I2C sample virtual.','Empty list, semaphores, client/adapter and address limit are supplied; original open/list insertion/queue/poll/GETVAL code executes.','Mode cases set DriverReady1; actual ioctl gate executes, dev_ctl transition returns virtual success/failure. Only already-normal case proves unchanged private objects/cache without device-control stub effects.','Does not prove actual concurrent scheduling, delivery latency, normal/deep-sleep sharing or hardware qualification. Burst case demonstrates latest-snapshot behavior, not lossless every-edge buffering.']}
(ROOT/'sources/native-touch-two-readers.json').write_text(json.dumps(report,indent=2)+'\n')
print('Two native open objects retain independent readiness in both polling orders; GETVAL snapshots match')
