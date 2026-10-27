"""Replay stock browser alarm registration and dispatch with virtual surrounding services."""
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
source_path=ROOT/'sources/native-browser-notification-producer.json'
source_bytes=source_path.read_bytes();source=json.loads(source_bytes)
assert source['all_passed'] and source['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
packet=bytes.fromhex(source['cases'][0]['events'][0]['packet_hex'])
assert struct.unpack('<3I',packet)==(10,9,0x30001)
e=ELFFile(io.BytesIO(b));rows=[]
for flags in (0,1,2,4,0x80,0x81,0x82,0x84):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   start=s['p_vaddr']&~4095;end=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(start,end-start);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);context=0x1001000;obj=0x1002000;event=0x1003000;stop=0x1000100
 u.mem_write(0x7de9f0,struct.pack('<I',context));u.mem_write(context,bytes(24));u.mem_write(event,packet);seen=[]
 def hook(uc,pc,size,unused):
  if pc in (0x30615c,0x306184,0x3061ac,0x3061d4,0x306208,0x30623c,0x304c14):seen.append(hex(pc))
  if pc not in (0x3072d4,0x307438,0x2fc4d8,0x3015d4,0x301af0,0x3047c8,0x302144,0x300b20,0x3349a4,0x3e2250,0x3e22b8):return
  result=0
  if pc in (0x3015d4,0x3349a4):result=obj
  if pc==0x301af0:result=flags
  if pc==0x307438:uc.mem_write(uc.reg_read(UC_ARM_REG_R0),struct.pack('<I',0))
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x101e000);u.reg_write(UC_ARM_REG_LR,stop);u.reg_write(UC_ARM_REG_R0,event)
  # Execute original notification10 registration through the real registration function.
 u.reg_write(UC_ARM_REG_PC,0xb35c)
 u.emu_start(0xb35c,0xb370,count=200)
 callback=struct.unpack('<I',u.mem_read(obj+0x2c+10*4,4))[0]
 userdata=struct.unpack('<I',u.mem_read(obj+0x58+10*4,4))[0]
 assert callback==0x3078ac and userdata==0, (hex(callback),userdata,hex(u.reg_read(UC_ARM_REG_PC)))
 u.reg_write(UC_ARM_REG_SP,0x101e000);u.reg_write(UC_ARM_REG_LR,stop);u.reg_write(UC_ARM_REG_R0,event)
 u.emu_start(callback,stop,count=2000);assert u.reg_read(UC_ARM_REG_PC)==stop
 state=list(struct.unpack('<2I',u.mem_read(context,8)));expected=(flags&0x7f)!=4
 assert state==([2,0x30001] if expected else [0,0]), (hex(flags),state,seen)
 assert len(seen)==1
 rows.append({'supplied_flags':hex(flags),'registered_callback':hex(callback),'registered_userdata':userdata,'selected_handler':seen[0],'context_mode_and_target':state})
report={'producer_report_sha256':hashlib.sha256(source_bytes).hexdigest(),'netfront_sha256':sha,'entry':'0x3078ac','dispatch':'0x3073c0','table':'0x664764','cases':rows,'all_passed':True,'physical_device_access':False,'limits':['Original notification10 registration, event callback, state decoder, table dispatch and target setter execute; registration mutex operations are virtual.','State flags, object and ancillary services are fixtures; event bytes come from the native manager producer report with its supplied input arguments.','Application manager registers this callback for notification10 at 0xb360..0xb36c; upstream trigger and actual IPC delivery/web reachability are not replayed.','No URL handler, app installation, executable registration or device execution is established.']}
(ROOT/'sources/native-browser-alarm-dispatch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))








