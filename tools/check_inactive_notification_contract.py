"""Stock inactive-notification adapter; return success is not an acknowledgement."""
from pathlib import Path
import io,struct,hashlib,json
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0';elf=ELFFile(io.BytesIO(raw));rows=[]
for name,app,exists,callback,expected in [('zero-id',0,False,False,0x102),('missing-app',1,False,True,0x111),('no-callback',1,True,False,0),('callback-error-return',1,True,True,0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':
   lo=segment['p_vaddr']&~4095;hi=(segment['p_vaddr']+segment['p_memsz']+4095)&~4095;u.mem_map(lo,hi-lo);u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000);core=0x60001000
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 put(core+0x51bc,0x50000000 if callback else 0);put(core+0x51c0,55);events=[];lookups=[]
 def hook(uc,pc,size,data):
  if pc==0x110ac:
   assert uc.reg_read(UC_ARM_REG_R0)==core and uc.reg_read(UC_ARM_REG_R1)==app;lookups.append(app);result=0x60010000 if exists else 0
  elif pc==0x50000000:
   packet=list(struct.unpack('<3I',uc.mem_read(uc.reg_read(UC_ARM_REG_R0),12)));assert packet==[6,0,0] and uc.reg_read(UC_ARM_REG_R1)==app and uc.reg_read(UC_ARM_REG_R2)==55;events.append(packet);result=7
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,app);u.reg_write(UC_ARM_REG_R1,core);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000100);u.emu_start(0xbd74,0x50000100,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000100 and u.reg_read(UC_ARM_REG_R0)==expected
 assert events==([[6,0,0]] if exists and callback else [])
 rows.append({'case':name,'return':expected,'events':events,'lookup_count':len(lookups)})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'sysmgrd_sha256':digest,'entry':'0xbd74','tail_target':'0xa62c','cases':rows,'finding':'Zero return can occur without callback delivery, and callback return is ignored; no application inactive acknowledgement or hardware release is proved.','limits':['Original adapter/notification instructions, registry lookup and callback execution effects virtual.','No IPC, actual player state, framebuffer or process execution.']}
(ROOT/'sources/native-inactive-notification-contract.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock inactive notification: four branches passed; return0 does not establish notification/acknowledgement.')
