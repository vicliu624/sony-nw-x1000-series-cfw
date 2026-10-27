"""Replay original callback branch stubs; kill() is mocked, no signal is sent."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/appproxy').read_bytes();assert hashlib.sha256(raw).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
e=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value']for s in e.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for event,callback in [(4,0x95c0),(6,0x969c)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x20000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x1000);u.mem_map(0x60000000,0x10000);u.mem_write(0x1c834,struct.pack('<I',321));u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000);calls=[]
 def hook(uc,pc,size,data):
  if pc==syms['kill']:
   calls.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)]);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(callback,0x50000000,count=1000);assert calls==[[321,15]]
 rows.append({'event':event,'callback':hex(callback),'mocked_kill_calls':calls})
r={'scope':'original branch/helper instructions; mocked kill, no real process or APF manager','rows':rows};(ROOT/'sources/native-proxy-termination.json').write_text(json.dumps(r,indent=2));print('Two original proxy callbacks request SIGTERM on the direct child')
