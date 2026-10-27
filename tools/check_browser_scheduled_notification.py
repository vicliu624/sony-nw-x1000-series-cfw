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
from unicorn.arm_const import UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R7,UC_ARM_REG_R8
for due,listener in ((100,True),(101,True),(100,False)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);core=0x1001000;module=core+0x4214;callback=0x1000200;stack=0x101e000;node=0x1008000;events=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 for off,value in ((0x503c,1),(0x51b4,callback if listener else 0),(0x51b8,0x12345678)):put(core+off,value)
 def hook(uc,pc,size,unused):
  if pc!=callback:return
  event=bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0),12));events.append(list(struct.unpack('<3I',event)))
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R5,module);u.reg_write(UC_ARM_REG_R8,core)
 u.emu_start(0xc024,0xc034,count=100)
 assert struct.unpack('<2I',u.mem_read(module+0x960,8))==(0xbcac,core)
 for off,value in ((4,9),(8,0x30001),(16,due)):put(node+off,value)
 for off,value in ((0x10,1),(0x14,100),(0x68,node)):put(stack+off,value)
 for reg,value in ((UC_ARM_REG_R7,module),(UC_ARM_REG_R4,0),(UC_ARM_REG_SP,stack)):u.reg_write(reg,value)
 u.emu_start(0x14250,0x1429c,count=500)
 assert u.reg_read(UC_ARM_REG_PC)==0x1429c
 assert events==([[10,9,0x30001]] if due<=100 and listener else [])
 rows.append({'supplied_now':100,'scheduled_time':due,'listener_present':listener,'notifications':events})
report={'sysmgrd_sha256':sha,'registration_slice':'0xc024..0xc034','due_dispatch_slice':'0x14250..0x1429c','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original module callback registration, due-time comparison, node argument extraction and notification producer execute.','Clock, one scheduler node, selected node array, module and core are supplied fixtures; scheduler creation/loading and real time are not executed.','No app-ID validation conclusion about node insertion, no real IPC or webpage interface is established.']}
(ROOT/'sources/native-browser-scheduled-notification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
