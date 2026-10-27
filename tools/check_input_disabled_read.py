"""Original input poll/read cycle with software-enable and select readiness fixtures."""
from pathlib import Path
import hashlib,io,json,struct,itertools
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for enabled,ready in itertools.product((0,1),(0,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 context=0x6bafb8
 put(context,enabled);put(0x4f7820,0x60004000);put(0x60004298,200000);put(0x761120,23)
 packet=bytearray(11);packet[1]=1;struct.pack_into('>HH',packet,2,1464,2640)
 reads=[];selects=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  result=0
  if pc==symbols['memcpy']:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
  elif pc==symbols['select']:
   assert a[0]==24
   bits=bytearray(128)
   if ready:struct.pack_into('<I',bits,0,1<<23)
   uc.mem_write(a[1],bytes(bits));selects.append(ready);result=ready
  elif pc==symbols['ioctl']:
   assert a[:2]==[23,0x80045401]
   reads.append(a[:2]);uc.mem_write(a[2],bytes(packet))
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 def call(pc,values):
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(pc,0x50000000,count=50000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
  return u.reg_read(UC_ARM_REG_R0)
 assert call(0xe18e4,(context,0xe1c1c,23))==0
 assert call(0xe1aa0,(context,))==0
 assert selects==[ready] and len(reads)==1 and word(context)==enabled
 rows.append({'software_enable_fixture':enabled,'select_ready_fixture':ready,'native_touch_reads':reads,'software_enable_after':word(context)})
report={'input_sha256':digest,'procedures':['0xe18e4 register','0xe1aa0 select cycle','0xe1c1c read callback','0x115acc touch classifier'],'cases':rows,'limits':['Input context, backend pointer/interval, touch fd and select/GETVAL payload are fixtures; actual registration/poll/classifier instructions run.','Does not prove concurrent-reader interference: cached GETVAL and driver per-open poll state must be examined separately.','No full app scheduler, actual fd/select/driver, UI dispatch or hardware ownership qualification.']}
(ROOT/'sources/native-input-disabled-read.json').write_text(json.dumps(report,indent=2)+'\n')
print('Four native input cycles verified: software flag0 does not itself stop GETVAL, including select-not-ready fixture')
