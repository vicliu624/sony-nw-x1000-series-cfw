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
for command,config_flag,eligible in ((1,0,0),(1,0,1),(2,0,0),(13,0,0),(18,0,0),(13,1,0)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x800000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x10000);stop=0x1000100;events=[]
 assert struct.unpack('<I',u.mem_read(0x383e4,4))[0]==0x65e8cc
 u.mem_write(0x65e8cc,bytes([config_flag]));u.mem_write(0x613e30,struct.pack('<I',0))
 u.mem_write(0x682d20,struct.pack('<I',0x1001000));u.mem_write(0x682cfc,struct.pack('<I',0x1001100));u.mem_write(0x1001100,b'\x01')
 u.mem_write(0x65e90c,struct.pack('<I',eligible))
 def hook(uc,pc,size,unused):
  if pc!=0xa57f0:return
  events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)])
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x100f000);u.reg_write(UC_ARM_REG_LR,stop)
 u.reg_write(UC_ARM_REG_R0,0x1001200);u.reg_write(UC_ARM_REG_R1,command);u.reg_write(UC_ARM_REG_R2,0x1001300)
 u.emu_start(0x3b498,stop,count=3000);assert u.reg_read(UC_ARM_REG_PC)==stop
 expected=[[0x420012,0,1],[0x4c0005,0,0]] if command in (13,18) and config_flag==0 else [[0x4c0008,0,0]] if command==1 and eligible else []
 assert events==expected
 rows.append({'supplied_config_6_600':config_flag,'input_number':command,'supplied_eligibility_field':eligible,'posted_event_headers':events})
report={'SpiderApp_sha256':sha,'entry':'0x3b498','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original parent jump-table dispatch, setting/current-object getters and event construction execute.','Input number, configuration, current-object and eligibility fields are fixtures; actual startup values and input meanings remain unknown.','Event posting is virtual; network state-machine delivery and boot reachability are not tested.','No network driver, file access, device program or configuration payload is executed.']}
(ROOT/'sources/native-spider-network-parent-dispatch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


