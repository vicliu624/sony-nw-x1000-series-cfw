"""Execute original daemon POWER_OFF handler with modeled pipes/driver calls."""
import hashlib
import io
import json
import struct
import itertools
from collections import deque
from pathlib import Path
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

raw=(ROOT/'work/qqmusic-wifi/cnmgr_daemon').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
elf=ELFFile(io.BytesIO(raw))
drivers={s['st_value']:s.name for s in elf.get_section_by_name('.symtab').iter_symbols()
         if s.name.startswith(('cnmgr_wlan_','cnmgr_ip_')) and s['st_value']}
rows=[]
for state in (0,2,3,6,7,8):
 for count,driver_result in itertools.product((1,2),(0,16)):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x2000000,0x50000);obj=0x2001000;end=0x2000100
  replies=[];calls=[];trace=deque(maxlen=24)
  def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,n):u.mem_write(a,struct.pack('<I',n))
  for at,value in ((0,90),(4,91),(8,92),(12,93),(20,0),(0xa09c,state),(0x13254,count)):put(obj+at,value)
  request=struct.pack('<I',4)+bytes(1016)
  def hook(uc,pc,size,unused):
   trace.append(hex(pc))
   a,b,c=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
   if pc==end:uc.emu_stop();return
   if pc in drivers:calls.append(drivers[pc]);result=driver_result
   elif pc==0x9fac:assert a==90 and c==1020;uc.mem_write(b,request);result=1020
   elif pc==0x9ae4:assert a==92 and c==1012;replies.append(word(b));result=1012
   elif pc==0x9a6c:assert c<=16384;uc.mem_write(a,bytes([b&255])*c);result=a
   elif pc==0x251d4:result=a # Logging-only source basename helper.
   elif pc in (0xa14c,0xa760,0x2327c):pass
   else:return
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  def reject(*args):raise AssertionError('Unexpected actual syscall')
  u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  try:u.emu_start(0xba18,end,count=50000)
  except Exception as error:
   raise AssertionError((state,count,hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),calls,replies,list(trace))) from error
  assert u.reg_read(UC_ARM_REG_PC)==end,'Unfinished handler'
  row=dict(initial_state=state,initial_clients=count,driver_result=driver_result,final_state=word(obj+0xa09c),
                   final_clients=word(obj+0x13254),pending_kind=word(obj+20),driver_calls=calls,replies=replies)
  if state in (2,3):
   assert calls==['cnmgr_wlan_power_off'] and row['final_state']==(state if driver_result else 0) and replies==[driver_result],row
  else:
   assert calls==[] and row['final_state']==state and replies==[1]
  assert row['final_clients']==count
  rows.append(row)
commands={hex(at):bytes(u.mem_read(at,256)).split(b'\0',1)[0].decode('ascii') for at in (0x27e84,0x27ea4)}
low_level=[]
for shell_results in ((0,0),(256,0),(0,256),(0xffffffff,0)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x10000);object_address=0x2001000;end=0x2000100;closed=[];invoked=[]
 u.mem_write(object_address,struct.pack('<II',91,92))
 def lower_hook(uc,pc,size,unused):
  a=uc.reg_read(UC_ARM_REG_R0);result=0
  if pc==end:uc.emu_stop();return
  if pc==0x9b20:closed.append(a)
  elif pc==0x9bf8:
   invoked.append(bytes(uc.mem_read(a,256)).split(b'\0',1)[0].decode('ascii'))
   assert len(invoked)<=2;result=shell_results[len(invoked)-1]
  elif pc==0x251d4:result=a
  elif pc==0x9bb0:result=0x2002000
  elif pc in (0xa14c,0xa760,0x2327c):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,lower_hook);u.hook_add(UC_HOOK_INTR,reject)
 u.reg_write(UC_ARM_REG_R0,object_address);u.reg_write(UC_ARM_REG_SP,0x200f000);u.reg_write(UC_ARM_REG_LR,end)
 u.emu_start(0xfd20,end,count=10000)
 expected=0 if shell_results==(0,0) else 16
 assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==expected
 assert closed==[91,92] and bytes(u.mem_read(object_address,8))==b'\xff'*8
 assert invoked==['/usr/local/bin/wlanapi.sh stop','/usr/local/bin/wlanapi.sh unload']
 low_level.append(dict(system_results=list(shell_results),commands=invoked,returned=expected,pipe_descriptors_closed=True))
chained=[]
for state,shell_results in itertools.product((2,3),((0,0),(256,0),(0,256),(0xffffffff,0))):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x50000);obj=0x2001000;end=0x2000100
 replies=[];invoked=[];closed=[];entered=[]
 for at,value in ((0,90),(4,91),(8,92),(12,93),(20,0),(0xa09c,state),(0x13254,1)):put(obj+at,value)
 def chain_hook(uc,pc,size,unused):
  a,b,c=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if pc==end:uc.emu_stop();return
  if pc==0xfd20:
   # Execute the actual low-level wrapper, using distinct modeled open pipes.
   entered.append(a);put(a,191);put(a+4,192);return
  if pc==0x9fac:assert a==90 and c==1020;uc.mem_write(b,struct.pack('<I',4)+bytes(1016));result=1020
  elif pc==0x9ae4:assert a==92 and c==1012;replies.append(word(b));result=1012
  elif pc==0x9a6c:assert c<=16384;uc.mem_write(a,bytes([b&255])*c);result=a
  elif pc==0x9b20:closed.append(a)
  elif pc==0x9bf8:
   invoked.append(bytes(uc.mem_read(a,256)).split(b'\0',1)[0].decode('ascii'))
   assert len(invoked)<=2;result=shell_results[len(invoked)-1]
  elif pc==0x9bb0:result=0x204e000
  elif pc==0x251d4:result=a
  elif pc in (0xa14c,0xa760,0x2327c):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,chain_hook);u.hook_add(UC_HOOK_INTR,reject)
 u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x204f000);u.reg_write(UC_ARM_REG_LR,end)
 u.emu_start(0xba18,end,count=50000)
 expected=0 if shell_results==(0,0) else 16
 assert u.reg_read(UC_ARM_REG_PC)==end and len(entered)==1 and replies==[expected]
 assert word(obj+0xa09c)==(state if expected else 0) and closed==[191,192]
 assert invoked==['/usr/local/bin/wlanapi.sh stop','/usr/local/bin/wlanapi.sh unload']
 chained.append(dict(initial_state=state,system_results=list(shell_results),reply=expected,
                     final_state=word(obj+0xa09c),actual_daemon_and_wrapper=True))
report=dict(passed=True,original_daemon_handler_executed=True,device_accessed=False,
            daemon_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,
            low_level_command_literals=commands,
            original_low_level_wrapper_cases=low_level,
            chained_daemon_and_wrapper_cases=chained,
            reference_count_does_not_block_power_off=True,
            driver_failure_propagated=True,
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limits=['Initial daemon context and driver success/failure returns are supplied.',
                    'Pending operations require later daemon events not executed here.',
                    'No actual system command, driver unload, RF power or current measurement.'])
out=ROOT/'work/remote-settings-native';out.mkdir(exist_ok=True)
(out/'power-off-daemon-replay.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
