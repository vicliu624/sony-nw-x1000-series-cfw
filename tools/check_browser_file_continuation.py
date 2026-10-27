"""Replay stock current browser request continuation with virtual downstream services."""
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
for name,token,present,flags,kind in [('token-mismatch',0,True,0,0),('no-current-request',1014,False,0,0),('request-flag1',1014,True,1,0),('request-kind5',1014,True,0,5),('request-kind0',1014,True,0,0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x30000);context=0x1001000;request=0x1004000;content=0x1005000;vtable=0x1008000;callback=0x1000200;stop=0x1000100;events=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 for a,v in ((context+0x2dc,token),(context+0x2b8,request if present else 0),(request,kind),(request+8,flags),(request+16,content),(content+0x18bc,42),(context+0x570,vtable),(vtable+56,callback),(context+0x2d0,0x1009000)):put(a,v)
 def hook(uc,pc,size,unused):
  if pc not in (callback,0x38e94,0x36348,0x37b5c):return
  args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  events.append({'boundary':hex(pc),'arguments':args})
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x102e000),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(0x37f68,stop,count=2000);assert u.reg_read(UC_ARM_REG_PC)==stop
 result=u.reg_read(UC_ARM_REG_R0)
 if name in ('token-mismatch','no-current-request'):assert result==0xffffffff and not events
 elif name=='request-flag1':assert result==0 and not events and struct.unpack('<I',u.mem_read(context+0x2e0,4))[0]==3
 elif name=='request-kind5':assert result==0 and [x['boundary'] for x in events]==['0x37b5c']
 else:assert result==0 and [x['boundary'] for x in events]==['0x1000200','0x38e94','0x36348']
 rows.append({'case':name,'return':hex(result),'boundaries':events})
report={'netfront_sha256':sha,'entry':'0x37f68','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original request token check, current-request checks and direct dispatch execute.','Request structures, token and internal fields are fixtures, not a fully initialized browser.','Content callback, continuation helpers and one state setter are virtual; their downstream behavior is not covered.','Observed direct path handles current browser request/content; no external executable launch is established.']}
(ROOT/'sources/native-browser-file-continuation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

