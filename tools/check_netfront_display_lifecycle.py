"""Bounded stock NetFront framebuffer init/finalize replay; no hardware."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/netfront';raw=path.read_bytes();packed=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
assert hashlib.sha256(raw).hexdigest()=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
with tarfile.open(packed,'r:gz') as archive:assert archive.extractfile('./usr/local/bin/netfront').read()==raw
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for page in (0,1):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  start=segment['p_vaddr']&~4095;end=(segment['p_vaddr']+segment['p_memsz']+4095)&~4095;u.mem_map(start,end-start);u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x60000000,0x20000);u.mem_map(0x61000000,0x500000);obj=0x60001000;sentinel=0x6001f000;events=[];aux=[]
 for address in list(range(0x918dc0,0x918de4,4))+[0x918e34,0x918e38]:u.mem_write(address,struct.pack('<I',0xa5a5a5a5))
 def words(address,count):return list(struct.unpack('<'+'I'*count,u.mem_read(address,count*4)))
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if pc==sentinel:uc.emu_stop();return
  if pc in (0x39d8d8,0x3ad088,0x3ad480):aux.append(hex(pc));return
  elif pc==symbols['open']:
   name=bytes(uc.mem_read(a[0],64)).split(b'\0')[0].decode();assert name=='/dev/fb/0' and a[1]==2;events.append({'open':name,'flags':2});result=17
  elif pc==symbols['mmap']:
   assert a==[0,0x500000,3,1] and words(uc.reg_read(UC_ARM_REG_SP),2)==[17,0];events.append({'mmap_bytes':0x500000});result=0x61000000
  elif pc==symbols['ioctl']:
   assert a[0]==17
   if a[1]==0x80044e04:assert words(a[2],2)==[0,33];events.append({'ioctl':hex(a[1]),'payload':[0,33]})
   else:
    assert a[1]==0x80044e00 and words(a[2],1)==[100];uc.mem_write(a[2],struct.pack('<3I',100,page,1-page));events.append({'ioctl':hex(a[1]),'ready_fixture':[100,page,1-page]})
   result=0
  elif pc==symbols['munmap']:assert a[:2]==[0x61000000,0x500000];events.append({'munmap_bytes':a[1]});result=0
  elif pc==symbols['close']:assert a[0]==17;events.append({'close_fd':17});result=0
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,sentinel)
 u.emu_start(0x3ac7d4,0,count=3000);assert u.reg_read(UC_ARM_REG_PC)==sentinel
 assert aux==['0x39d8d8','0x3ad088','0x3ad480'];assert words(obj+0x1c,3)==[page,255,1]
 assert words(0x918dc0,9)==[0]*9 and words(0x918e34,2)==[0,0]
 init_events=events.copy();events.clear()
 u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,sentinel)
 u.emu_start(0x3ac900,0,count=3000);assert u.reg_read(UC_ARM_REG_PC)==sentinel
 assert events==[{'munmap_bytes':0x500000},{'close_fd':17}]
 rows.append({'available_page_fixture':page,'init_events':init_events,'finalize_events':events,'native_memory_initializers_executed':aux})
report={'passed':True,'netfront_sha256':hashlib.sha256(raw).hexdigest(),'init_entry':'0x3ac7d4','finalize_entry':'0x3ac900','cases':rows,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),path,packed]},'hardware_tested':False,'limits':['Original ARM instructions execute; Only libc operations/readiness are replaced; memory initializers execute original instructions.','5MiB map is stock behaviour, not a proposed change to the bounded 0xc0000 app adapter.','No actual browser startup, APF switch, LCD completion or kernel workqueue execution.','Software-only initializer observations do not replace driver/hardware initialization qualification.']}
(ROOT/'sources/native-netfront-display-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock NetFront display: open/map -> timeout[0,33] -> ready query; unmap/close ordering confirmed in two bounded cases.')
