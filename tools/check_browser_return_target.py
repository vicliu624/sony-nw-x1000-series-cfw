"""Replay stock browser application-end target selection with virtual services."""
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
for mode,target,expected in [(0,0,1),(1,0,2),(2,0x30001,0x30001),(2,0,1),(3,0,1),(4,0,None)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);context=0x1001000;stack=0x101e000;stop=0x1000100
 u.mem_write(0x7de9f0,struct.pack('<I',context));u.mem_write(context,struct.pack('<6I',mode,target,1,0,0,0));calls=[]
 def hook(uc,pc,size,unused):
  if pc not in (0x3349a4,0x33767c,0x2fc81c,0x2fc85c,0xa9e8):return
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if pc==0x33767c:calls.append({'target':args[1],'mode':args[3],'argument_words':list(struct.unpack('<2I',uc.mem_read(args[2],8)))})
  result=0x1002000 if pc==0x3349a4 else 0
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,stop)
 u.emu_start(0xb030,stop,count=1000);assert u.reg_read(UC_ARM_REG_PC)==stop
 assert len(calls)==(0 if expected is None else 1)
 if calls:assert calls[0]['target']==expected and calls[0]['mode']==1
 rows.append({'context_mode':mode,'supplied_context_target':target,'switch_calls':calls})
report={'netfront_sha256':sha,'entry':'0xb030','cases':rows,'all_passed':True,'physical_device_access':False,'limits':['Original context getter and selection execute; manager handle, changeApp, diagnostics and sleep are virtual.','Mode2 uses a supplied nonzero numeric target; its producer and reachability from a web page are not proven.','This tests no URI parsing, executable registration, installation or real app switch.']}
(ROOT/'sources/native-browser-return-target.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
