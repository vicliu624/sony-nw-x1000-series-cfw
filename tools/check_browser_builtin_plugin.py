"""Replay stock built-in plugin descriptor construction with virtual registration."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:b=tar.extractfile('./usr/local/bin/netfront').read()
sha=hashlib.sha256(b).hexdigest();assert sha=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
e=ELFFile(io.BytesIO(b));rows=[]
for accept in (1,0):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);stop=0x1000100;strings=[];captured=[];frees=[]
 def hook(uc,pc,size,unused):
  if pc not in (0xef984,0x103720,0x257a74,0x26ee84):return
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if pc==0xef984:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
  elif pc==0x103720:
   value=bytes(uc.mem_read(a[0],128)).split(b'\0')[0];result=0x1002000+len(strings)*256
   uc.mem_write(result,value+b'\0');strings.append(value.decode())
  elif pc==0x257a74:
   data=bytes(uc.mem_read(a[1],128));callbacks={hex(off):hex(struct.unpack_from('<I',data,off)[0]) for off in (0x20,0x24,0x2c,0x30,0x34,0x38,0x3c,0x40,0x44,0x48,0x50,0x5c)}
   assert all(0xa000<int(v,16)<0x3e8000 for v in callbacks.values());captured.append(callbacks);result=accept
  else:frees.append(a[0])
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_SP,0x101e000);u.reg_write(UC_ARM_REG_LR,stop);u.reg_write(UC_ARM_REG_R0,0x1001000)
 u.emu_start(0x256e14,stop,count=1000);assert u.reg_read(UC_ARM_REG_PC)==stop
 assert len(captured)==1 and len(strings)==5 and 'application/x-simple-plugin' in strings
 assert u.reg_read(UC_ARM_REG_R0)==accept and len(frees)==(0 if accept else 5)
 rows.append({'supplied_registration_result':accept,'metadata':strings,'builtin_callbacks':captured[0],'cleanup_count':len(frees)})
report={'netfront_sha256':sha,'entry':'0x256e14','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original simple-plugin descriptor construction executes; memory/string allocation, registration and cleanup are virtual.','Captured callback addresses are built into this browser binary; this path does not dynamically load an external plugin.','Individual callbacks and plugin content parsing are not executed; other MIME handlers and URI schemes remain unqualified.','This is normal feature analysis only, with no vulnerability investigation or device payload.']}
(ROOT/'sources/native-browser-builtin-plugin.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

