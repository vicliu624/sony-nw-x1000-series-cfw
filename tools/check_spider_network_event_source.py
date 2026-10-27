"""Replay stock SpiderApp WLAN request callback; virtual network/log/event services."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/SpiderApp').read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
e=ELFFile(io.BytesIO(b));rows=[]
for config_flag,current_field in ((0,0),(1,0),(0,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x800000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x10000);stop=0x1000100;events=[]
 assert struct.unpack('<I',u.mem_read(0x383e4,4))[0]==0x65e8cc
 u.mem_write(0x65e8cc,bytes([config_flag]));u.mem_write(0x613e30,struct.pack('<I',current_field))
 def hook(uc,pc,size,unused):
  if pc!=0xa57f0:return
  events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)])
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x100f000);u.reg_write(UC_ARM_REG_LR,stop)
 u.emu_start(0x3b41c,stop,count=2000);assert u.reg_read(UC_ARM_REG_PC)==stop
 expected=[[0x420012,0,1],[0x4c0005,0,0]] if config_flag==current_field==0 else []
 assert events==expected
 rows.append({'supplied_config_6_600':config_flag,'supplied_current_field':current_field,'posted_event_headers':events})
report={'SpiderApp_sha256':sha,'entry':'0x3b41c','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original setting getter, current-object getter/field read and event construction execute.','Configuration byte and current-object field are fixtures; actual startup values and meanings remain unknown.','Event posting is virtual; network state-machine delivery and boot reachability are not tested.','No network driver, file access, device program or configuration payload is executed.']}
(ROOT/'sources/native-spider-network-event-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
