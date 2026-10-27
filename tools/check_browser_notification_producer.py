"""Capture stock manager notification10 producer; host-only virtual listener."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/sysmgrd').read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
e=ELFFile(io.BytesIO(b));rows=[]
for state,listener in ((1,True),(5,True),(1,False)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);core=0x1001000;stop=0x1000100;callback=0x1000200;events=[];local=[]
 for off,value in ((0x503c,state),(0x51b4,callback if listener else 0),(0x51b8,0x12345678)):
  u.mem_write(core+off,struct.pack('<I',value))
 def hook(uc,pc,size,unused):
  if pc==callback:
   event=bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0),12));events.append({'words':list(struct.unpack('<3I',event)),'packet_hex':event.hex(),'userdata':uc.reg_read(UC_ARM_REG_R1)})
  elif pc==0xb00c:local.append(list(struct.unpack('<3I',uc.mem_read(uc.reg_read(UC_ARM_REG_R1),12))))
  else:return
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM_REG_R0,9),(UC_ARM_REG_R1,0x30001),(UC_ARM_REG_R2,core),(UC_ARM_REG_SP,0x101e000),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(0xbcac,stop,count=500);assert u.reg_read(UC_ARM_REG_PC)==stop
 assert len(events)==int(listener)
 if events:assert events[0]['words']==[10,9,0x30001] and events[0]['userdata']==0x12345678
 assert local==([[10,9,0x30001]] if state==5 else [])
 rows.append({'core_state':state,'listener_present':listener,'events':events,'local_handler_calls':local})
report={'sysmgrd_sha256':sha,'entry':'0xbcac','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Producer receives two supplied integer arguments and core context; its upstream alarm source is not executed.','Listener and special-state local handler are virtual; no real IPC transport or browser delivery.','No app registration or external executable loading occurs in the inspected producer.','This does not establish whether upstream paths validate an app ID, nor web reachability.']}
(ROOT/'sources/native-browser-notification-producer.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
