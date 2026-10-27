"""Original b4fd8 ->115ac4 ->14b558 touch mode gate. Virtual ioctl only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for initial,enabled,ioctl_result in ((0,0,0),(1,1,0),(0,1,0),(1,0,0),(0,0,-1),(1,1,-1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 context=0x76111c;put(context+4,23);put(context+4+0x228,initial)
 calls=[]
 def hook(uc,pc,size,data):
  if pc!=symbols['ioctl']:return
  calls.append([uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)])
  uc.reg_write(UC_ARM_REG_R0,ioctl_result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_R0,enabled);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0xb4fd8,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 target=0 if enabled else 1
 expected=[] if initial==target else [[23,0x5404 if enabled else 0x5403]]
 assert calls==expected
 result=u.reg_read(UC_ARM_REG_R0);after=word(context+4+0x228)
 failed=bool(expected) and ioctl_result!=0
 assert result==(0x100 if failed else 0)
 assert after==(initial if failed else target)
 assert word(context+4)==23
 rows.append({'initial_mode':initial,'enabled_argument':enabled,'ioctl_result_fixture':ioctl_result,'ioctl_calls':calls,'native_return':result,'mode_after':after,'fd_unchanged':True})
report={'input_sha256':digest,'procedures':['0xb4fd8','0x115a60','0x115ac4','0x14b558'],'cases':rows,'limits':['Original gate/getter/wrapper/mode setter execute; initial context/fd and ioctl response are fixtures.','No actual touch deep-sleep/wake or hardware ownership verified. Call-site association with APF deactivation remains incomplete.']}
(ROOT/'sources/native-touch-mode-gate.json').write_text(json.dumps(report,indent=2)+'\n')
print('Six original touch normal/deep-sleep gate cases passed; failed ioctl preserves prior mode and fd')
