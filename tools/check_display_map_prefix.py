"""Original display allocation prefix, stopped before backend setup or QFB ioctls."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
u.mem_map(low,high-low)
for s in segments:u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x60000000,0x20000)
def words(p,n):return list(struct.unpack('<'+'I'*n,u.mem_read(p,4*n)))
calls=[]
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==symbols['open']:
  name=bytes(uc.mem_read(a[0],64)).split(b'\0')[0].decode();assert name=='/dev/fb/0' and a[1]==2
  calls.append({'call':'open','path':name,'flags':a[1]});result=17
 elif pc==symbols['mmap']:
  stack=words(uc.reg_read(UC_ARM_REG_SP),2)
  assert a==[0,0x500000,3,1] and stack==[17,0]
  calls.append({'call':'mmap','args':a+stack});result=0x61000000
 else:return
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
u.reg_write(UC_ARM_REG_R0,0x60000000);u.reg_write(UC_ARM_REG_SP,0x60018000)
u.emu_start(0x14a2c4,0x14a398,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==0x14a398
state=words(0x60000000,34)
assert state[:7]==[17,0x61000000,0x61060000,0x33000000,0x33060000,0x61000000,0x61060000]
assert state[11:19]==[0x61200000+0x40000*i for i in range(8)]
assert state[19:27]==[0]*8
assert state[27:34]==[0]*7
report={'input_sha256':digest,'native_range':['0x14a2c4','0x14a398 exclusive'],'calls':calls,'state_words':state,'limits':['Only successful virtual open/mmap; returned pointer is a fixture and mapping is not physically allocated.','Execution stops before13b3c8, render-context slot setup, QFB ioctl and frame readiness wait; no completed display initialization claim.','Physical-address constants are observed stock values, not instructions for hardware access or a safe homebrew profile.']}
(ROOT/'sources/native-display-map-prefix.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original display mapping prefix verified: fb/0,5MiB, two page pointers and eight auxiliary slots; backend not executed')
