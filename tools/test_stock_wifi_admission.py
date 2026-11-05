"""Replay pinned stock Wi-Fi power/scan paths; native manager calls modeled."""
import hashlib,io,json,struct,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for entry in (0x6205c,0x61e10):
 for network in (0,1,2,3,4,5):
  for power_result in (0,1):
   for search_result in (0,1):
    for off_result in (0,1):
     u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
     for segment in elf.iter_segments():
      if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
     u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
     calls=[];events=[];destination=0x60001000
     u.mem_write(destination,struct.pack('<I',0xfeedface))
     def hook(uc,pc,size,unused):
      a,b,c,d=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
      if pc==0xb3300:answer=network;calls.append('state')
      elif pc==0xb3458:answer=power_result;calls.append('power_on')
      elif pc==0xb3784:answer=search_result;calls.append('search')
      elif pc==0xb37f4:answer=1;calls.append('results_end')
      elif pc==0xb34c8:answer=off_result;calls.append('power_off')
      elif pc==symbols['memset']:
       assert c<=256;uc.mem_write(a,bytes([b&255])*c);answer=a
      elif pc==0xa57f0:events.append([a,b,c,d]);answer=1
      else:return
      uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
     def syscall(*args):raise AssertionError('Unexpected real syscall')
     u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,syscall)
     for reg,value in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,destination),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
     u.emu_start(entry,0x50000000,count=20000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
     admitted=network in (2,3,4) and (network!=2 or power_result==0)
     expected=['state']+(['power_on'] if network==2 else [])
     if entry==0x6205c:
      assert u.reg_read(UC_ARM_REG_R0)==(0x201 if admitted else 1)
      if network==2 and power_result:expected_events=[[0x420012,0,0,0],[0x4c800f,0,0,0]]
      elif admitted:expected_events=[[0x4c800f,0,0,0],[0x420012,0,1,0]]
      else:expected_events=[[0x4c800f,0,0,0]]
     else:
      assert u.reg_read(UC_ARM_REG_R0)==1
      if admitted:
       expected+=['search']
       if search_result==0:expected+=['results_end','power_off']
      assert struct.unpack('<I',u.mem_read(destination,4))[0]==(0 if admitted and search_result==0 else 0xfeedface)
      expected_events=[[0x4c8009,0,0,0]]
     assert calls==expected and events==expected_events,(hex(entry),network,calls,events)
     rows.append(dict(entry=hex(entry),network=network,power_result=power_result,search_result=search_result,
                      off_result=off_result,calls=calls,events=events))
wps_rows=[]
for entry,register in ((0xb3ee4,0xd640),(0xb3f70,0xd880),(0xb3ffc,0xdf4c)):
 for prepare_result in (0,16):
  for register_result in (0,1,16):
   u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
   for segment in elf.iter_segments():
    if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
   u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
   calls=[];logs=[]
   def wps_hook(uc,pc,size,unused):
    args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    if pc==0xb3248:answer=7
    elif pc in (0x33b918,0x33b83c):logs.append(pc);answer=0
    elif pc==0xe030:calls.append(dict(kind='prepare'));answer=prepare_result
    elif pc==register:calls.append(dict(kind='register',arguments=args));answer=register_result
    else:return
    uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
   u.hook_add(UC_HOOK_CODE,wps_hook);u.hook_add(UC_HOOK_INTR,syscall)
   for reg,value in ((UC_ARM_REG_R0,0x12345678),(UC_ARM_REG_R1,0x23456789),(UC_ARM_REG_R2,0x3456789a),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
   u.emu_start(entry,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==register_result
   assert len(calls)==2 and calls[0]['kind']=='prepare' and calls[1]['kind']=='register'
   preserved=1 if entry==0xb3ffc else 3
   assert calls[1]['arguments'][:preserved]==[0x12345678,0x23456789,0x3456789a][:preserved]
   assert logs==[0x33b918]+([0x33b83c] if register_result else [])
   wps_rows.append(dict(entry=hex(entry),prepare_result=prepare_result,register_result=register_result,calls=calls))
report=dict(passed=True,device_accessed=False,firmware_created=False,arm_cases=len(rows)+len(wps_rows),
 stock_sha256=hashlib.sha256(raw).hexdigest(),cases=rows,wps_cases=wps_rows,
 source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
 findings=['Only state2 invokes power_on; states3/4 can proceed without a fresh power_on call.',
 'Successful scan invokes power_off even when it entered in state3/4.',
 'Scan does not propagate power_off failure; completion event and return stay unchanged.',
 'All three WPS wrappers call registration after prepare even when prepare returns16; gate preparation alone is insufficient.'],
 limits=['Manager state, power, search/results, memory helper and event queue are fixture boundaries.',
 'This covers two pinned paths, not all stock Wi-Fi users or external processes.',
 'No interception, policy binding, native worker-thread qualification or physical RF evidence.'])
out=ROOT/'work/stock-wifi-admission'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,arm_cases=len(rows)+len(wps_rows),wps_cases=len(wps_rows),device_accessed=False,report=(out/'report.json').relative_to(ROOT).as_posix(),findings=report['findings']),indent=2))
