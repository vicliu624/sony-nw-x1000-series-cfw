"""Replay stock SpiderApp WLAN request callback; virtual network/log/event services."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/SpiderApp').read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
source_path=ROOT/'sources/native-spider-network-parent-dispatch.json';source_bytes=source_path.read_bytes();source=json.loads(source_bytes)
assert source['all_passed'] and source['SpiderApp_sha256']==sha
parent_case=next(row for row in source['cases'] if row['input_number']==13 and row['supplied_config_6_600']==0)
header=parent_case['posted_event_headers'][1];assert header==[0x4c0005,0,0]
e=ELFFile(io.BytesIO(b));rows=[]
for state,power_result in ((0,0),(1,0),(2,0),(3,0),(4,0),(2,5)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x800000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x10000);stop=0x1000100;power=[];events=[]
 def hook(uc,pc,size,unused):
  if pc not in (0xda18,0xda9c,0xb3248,0x33b918,0x33b83c,0xa57f0,0x17c42c):return
  result=0
  if pc==0xda18:result=state
  elif pc==0xda9c:power.append('cnmgr_power_on');result=power_result
  elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)])
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x100f000);u.reg_write(UC_ARM_REG_LR,stop)
 u.emu_start(0x61d48,stop,count=5000);assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_R0)==0
 assert bytes(u.mem_read(0x682d00,2))==bytes([1,1])
 event=0x1000200;u.mem_write(event,struct.pack('<4I',0,*header))
 u.reg_write(UC_ARM_REG_R0,event);u.reg_write(UC_ARM_REG_SP,0x100f000);u.reg_write(UC_ARM_REG_LR,stop)
 u.emu_start(0x61db4,stop,count=10000);assert u.reg_read(UC_ARM_REG_PC)==stop
 assert len(power)==int(state==2)
 result=list(u.mem_read(0x682d00,2));expected=[2,1] if state in (3,4) or (state==2 and power_result==0) else [1,1]
 assert result==expected,(result,expected)
 rows.append({'supplied_network_state':state,'supplied_power_result':power_result,'power_requests':power,'posted_event_headers':events,'final_group_state':result})
report={'source_report_sha256':hashlib.sha256(source_bytes).hexdigest(),'SpiderApp_sha256':sha,'initialization':'0x61d48','event_wrapper':'0x61db4','event':'0x4c0005','power_wrapper':'0xb3458','all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Original initializer, state dispatch, callback and power wrapper execute; network imports, diagnostics and event posting are virtual.','Network state and power result are supplied; no driver or network library request is executed here.','No startup state-machine event source or boot timing is established.','This cannot establish eth0 presence before S70netstart.']}
(ROOT/'sources/native-spider-network-event-dispatch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))




