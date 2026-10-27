"""Manager post-fork child credentials and exec, virtual libc boundaries."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R5,UC_ARM_REG_R9,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for initial_uid in (0,1000):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':
   lo=segment['p_vaddr']&~4095;hi=(segment['p_vaddr']+segment['p_memsz']+4095)&~4095
   u.mem_map(lo,hi-lo);u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x60000000,0x10000)
 u.mem_write(0x60001508,struct.pack('<2I',501,502));u.mem_write(0x60003000,b'/usr/local/bin/appproxy\0');u.mem_write(0x60002000,struct.pack('<2I',0x60003000,0))
 u.reg_write(UC_ARM_REG_R5,0x60001000);u.reg_write(UC_ARM_REG_R9,0x60002000);u.reg_write(UC_ARM_REG_SP,0x60008000)
 calls=[]
 def hook(uc,pc,size,data):
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  for name in ('close','fcntl'):
   if pc==symbols[name]:raise AssertionError('Unexpected descriptor cleanup in child path')
  name=next((name for name in ('getuid','setgid','setgroups','setuid','execvp') if pc==symbols[name]),None)
  if name is None:return
  if name=='execvp':
   assert args[:2]==[0x60003000,0x60002000];calls.append({'call':name});uc.emu_stop();return
  calls.append({'call':name,'args':args[:2] if name=='setgroups' else args[:1] if name!='getuid' else []})
  uc.reg_write(UC_ARM_REG_R0,initial_uid if name=='getuid' else 0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x11218,0,count=3000);assert u.reg_read(UC_ARM_REG_PC)==symbols['execvp']
 assert [c['call'] for c in calls]==(['getuid','setgid','setgroups','getuid','setuid','execvp'] if initial_uid==0 else ['getuid','getuid','execvp']),calls
 if initial_uid==0:assert calls[1]['args']==[502] and calls[2]['args']==[0,0] and calls[4]['args']==[501]
 rows.append({'initial_uid_fixture':initial_uid,'calls':calls})
report={'sysmgrd_sha256':digest,'physical_device_access':False,'entry':'0x11218','cases':rows,'finding':'Successful tested post-fork child paths adjust credentials then exec; no close/fcntl in these paths.','limits':['UID/GID/argv are fixtures and libc effects virtual.','Earlier descriptor flags, manager startup, fork and actual inheritance not executed.','No runtime framebuffer owner or last-close conclusion.']}
(ROOT/'sources/native-manager-child-fd-contract.json').write_text(json.dumps(report,indent=2)+'\n');print('Manager child root/nonroot success paths: original credential helpers to execvp, no close/fcntl in tested segment.')
