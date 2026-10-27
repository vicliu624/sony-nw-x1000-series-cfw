"""Replay stock file-URI dispatch with native policy lookup and prefix comparison."""
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
from unicorn.arm_const import UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R8
e=ELFFile(io.BytesIO(b));rows=[]
for url,gate in [('file:///contents/HOMEBREW/launcher/app',1),('FILE:///contents/test.html',1),('https://example.invalid/',1),('file:///contents/test.html',0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);context=0x1001000;uri=0x1003000;vtable=0x1004000;callback=0x1000200;stack=0x101e000;actions=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 
 for i in range(8):put(context+i*8,0xffffffff);put(context+i*8+4,0)
 u.mem_write(uri,url.encode()+b'\0');put(stack+8,uri);put(context+0x264,vtable);put(vtable+12,callback)
 def hook(uc,pc,size,unused):
  if pc not in (0x37f68,callback):return
  result=0
  if pc==0x37f68:actions.append({'operation':'local-handler','argument':uc.reg_read(UC_ARM_REG_R1)})
  else:actions.append({'operation':'forward-to-browser-callback'})
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 engine=context-0x58;config=0x1005000;stop=0x1000100
 # Install key2 using the native setter, then execute original configuration's set/remove branch.
 for reg,value in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,2),(UC_ARM_REG_R2,engine+0x3c7c),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(0xaef00,stop,count=100)
 put(config+0x35c,1);put(engine+0x11128,0 if gate else 1)
 u.reg_write(UC_ARM_REG_R5,engine);u.reg_write(UC_ARM_REG_R6,config)
 u.emu_start(0x16c734,0x16c778,count=200)
 for reg,value in ((UC_ARM_REG_R4,context),(UC_ARM_REG_R5,len(url)),(UC_ARM_REG_R8,context),(UC_ARM_REG_SP,stack)):u.reg_write(reg,value)
 u.emu_start(0x37384,0x373dc,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x373dc
 expected=bool(gate and url.lower().startswith('file:'))
 assert actions==([{'operation':'local-handler','argument':0}] if expected else [{'operation':'forward-to-browser-callback'}]), (url,gate,actions,bytes(u.mem_read(context,64)).hex())
 rows.append({'url':url,'supplied_internal_gate':gate,'actions':actions})
report={'netfront_sha256':sha,'entry_slice':'0x37384..0x373dc','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original key2 setter, configuration set/remove branch, lookup and file-scheme prefix comparison execute.','Configuration enable and selector fields are fixtures; key2 receives an internal engine pointer or is removed by original instructions. Actual device settings remain unknown.','Local handler and downstream browser callback are virtual, so no loading, rendering or local-ELF execution is established.','URLs are host test strings only; no request or navigation is performed.']}
(ROOT/'sources/native-browser-file-uri-gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))





