"""Original proxy descriptor flags and child branch; services virtual, no device."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/appproxy').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def machine():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000);u.mem_map(0x60000000,0x10000)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 u.reg_write(UC_ARM_REG_SP,0x60008000);return u
u=machine();u.mem_write(0x60001000,struct.pack('<2I',32,33));u.reg_write(UC_ARM_REG_R4,0x60001000);u.reg_write(UC_ARM_REG_R0,0);flags=[]
def flag_hook(uc,pc,size,data):
 if pc==symbols['fcntl']:
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];flags.append(args);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,flag_hook);u.emu_start(0x9704,0x9740,count=1000);assert u.reg_read(UC_ARM_REG_PC)==0x9740 and flags==[[32,2,1],[33,2,1]],flags
u=machine();u.mem_write(0x1ca4c,struct.pack('<I',0x60002000));u.mem_write(0x1ca50,struct.pack('<I',0x60003000));u.mem_write(0x60002000,b'/contents/HOMEBREW/launcher/app\0');u.mem_write(0x60003000,struct.pack('<2I',0x60002000,0));calls=[]
def child_hook(uc,pc,size,data):
 if pc==symbols['fork']:
  calls.append('fork');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 elif pc==symbols['execvp']:
  assert uc.reg_read(UC_ARM_REG_R0)==0x60002000 and uc.reg_read(UC_ARM_REG_R1)==0x60003000;calls.append('execvp');uc.emu_stop()
 elif pc in (symbols['close'],symbols['fcntl']):raise AssertionError('Unexpected child descriptor operation')
u.hook_add(UC_HOOK_CODE,child_hook);u.emu_start(0x95e4,0,count=1000);assert calls==['fork','execvp'] and u.reg_read(UC_ARM_REG_PC)==symbols['execvp']
report={'appproxy_sha256':digest,'physical_device_access':False,'pipe_fcntl_calls':flags,'pipe_semantics':'F_SETFD=2, FD_CLOEXEC=1 for both supplied pipe endpoints','child_path_calls':calls,'finding':'Replay protects proxy pipe endpoints with close-on-exec; tested post-fork child branch goes directly to execvp without general fd cleanup.','limits':['Pipe descriptors and exec arguments supplied; fcntl/fork/execvp virtual.','No proof of all inherited fds or earlier manager/library fd flags.','Does not establish framebuffer ownership or last-close state.']}
(ROOT/'sources/native-proxy-fd-contract.json').write_text(json.dumps(report,indent=2)+'\n');print('Original proxy: both pipe ends CLOEXEC; post-fork child directly execvp, no general fd cleanup in tested branch.')
