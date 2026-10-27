"""Replay stock coordinator participant command1 into radio release handling.
Synthetic context/eligibility and imported API returns; no manager/radio IPC.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
rows=[]
for mode,browser_mode in ((1,1),(2,1),(3,1),(3,3)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x20000);end=0x2000100;radio=0x2001000;connection=0x2001100;parent=0x2001200;out=0x2001300
 def put(a,n):u.mem_write(a,struct.pack('<I',n))
 context=bytearray(32);context[0]=mode;context[1]=1;context[13]=14;struct.pack_into('<I',context,4,0x3efb3c)
 u.mem_write(radio,bytes(context));u.mem_write(connection,b'\x01\x01')
 put(0x682cfc,radio);put(0x682d20,connection);put(0x65e90c,1)
 browser=0x2001400;rootctx=0x2001500;coordinator=0x2001600
 u.mem_write(browser,bytes([browser_mode,1]));put(0x682cd8,browser)
 rootdata=bytearray(32);rootdata[0:2]=bytes([2,1]);rootdata[13]=10;struct.pack_into('<I',rootdata,4,0x3f4f18)
 u.mem_write(rootctx,bytes(rootdata))
 events=[];calls=[];commands=[]
 def hook(uc,pc,size,unused):
  result=0
  if pc==end:uc.emu_stop();return
  elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
  elif pc in (0xd958,0xd4fc):calls.append('cnmgr_disconnect' if pc==0xd958 else 'cnmgr_power_off')
  elif pc==0xffa4:result=coordinator
  elif pc==0x112fc:commands.append(uc.reg_read(UC_ARM_REG_R1));put(uc.reg_read(UC_ARM_REG_R2),0)
  elif pc==0x10dec:result=0  # modeled pending-operation query
  elif pc==0xd574:
   a=uc.reg_read(UC_ARM_REG_R0);n=uc.reg_read(UC_ARM_REG_R2)
   uc.mem_write(a,bytes([uc.reg_read(UC_ARM_REG_R1)&255])*n);result=a
  elif pc in (0x117f0,0x140c8,0xe5ac):pass
  elif pc in (0xb3248,0x33b918,0x33b83c,0x17c42c):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def reject(*args):raise AssertionError('Unexpected system instruction')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject)
 def call(pc,r0,r1,r2=0,r3=0):
  for r,v in ((UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_R2,r2),(UC_ARM_REG_R3,r3),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):u.reg_write(r,v)
  u.emu_start(pc,end,count=20000);assert u.reg_read(UC_ARM_REG_PC)==end
 # Registered Spider APF slot3 callback; its transport/registration are covered
 # separately by check_app_sleep_callbacks.py. No actual sleep is requested.
 call(0xecb8,0,0)
 assert events==[[0x420013,0,0,0]]
 sleep_event=events.pop();call(0x17c608,rootctx,*sleep_event[:3])
 if browser_mode==3:
  assert commands==[] and calls==[] and events==[[0x430113,0,1,0]]
  assert list(u.mem_read(radio,2))==[3,1]
  rows.append({'supplied_radio_mode':mode,'supplied_browser_mode':browser_mode,'supplied_pending_operation':0,'stock_slot3_event':hex(sleep_event[0]),'root_coordinator_commands':commands,'imported_calls':calls,'final_radio_context':[3,1],'alternative_events':list(events)})
  continue
 assert commands==[1]
 call(0x3b498,parent,commands[0],out)
 # Parent is already idle in radio mode1; eligibility is only consulted there.
 assert events==[[0x4c0008,0,0,0]]
 request=events.pop();call(0x17c608,radio,*request[:3])
 wanted={1:[],2:['cnmgr_power_off'],3:['cnmgr_disconnect','cnmgr_power_off']}[mode]
 assert calls==wanted and list(u.mem_read(radio,2))==[1,1]
 rows.append({'supplied_radio_mode':mode,'supplied_browser_mode':browser_mode,'supplied_radio_state':1,'stock_slot3_event':hex(sleep_event[0]),'root_coordinator_commands':commands,'parent_command':1,'posted_request':hex(request[0]),'imported_calls':calls,'final_radio_context':[1,1],'completion_events':list(events)})
events.clear();calls.clear();commands.clear()
u.mem_write(rootctx,bytes(rootdata));u.mem_write(browser,bytes([3,1]))
put(0x613e2c+32,2)  # explicit branch bypassing snapshot persistence
consumer=0x2001800;data=bytearray(32);data[0:2]=bytes([1,1]);data[13]=11;struct.pack_into('<I',data,4,0x3f4388);u.mem_write(consumer,bytes(data))
call(0xeb9c,0,0)
assert events==[[0x420024,0,0,0]]
first=events.pop();call(0x17c608,rootctx,*first[:3])
assert events==[[0x430113,0,6,0]] and not commands
second=events.pop();call(0x17c608,consumer,second[0],second[2],second[3])
assert events==[[0x420032,0,0x683348,0]] and not commands
third=events.pop();call(0x17c608,rootctx,third[0],third[2],third[3])
assert commands==[6]
call(0x3b498,parent,commands[0],out)
assert struct.unpack('<I',u.mem_read(0x65e8f8+32,4))[0]==1 and not calls
deactivation={'events':[first,second,third],'coordinator_commands':list(commands),'radio_field_20_after':1,'network_calls':list(calls),'snapshot_mode_field_fixture':2}
ownership=[]
for lifecycle in (6,7):
 events.clear();calls.clear();commands.clear()
 # Use the original radio participant for deactivation/reactivation command.
 # Reset only the supplied initial radio state, then let original code mutate.
 u.mem_write(radio,bytes([3,1]));put(0x65e8f8+32,0)
 call(0x3b498,parent,lifecycle,out)
 flag=struct.unpack('<I',u.mem_read(0x65e8f8+32,4))[0]
 assert flag==(1 if lifecycle==6 else 0) and not events
 call(0x3b498,parent,3,out)
 if lifecycle==6:
  assert events==[[0x4c000f,0,0,0]]
  header=events.pop();call(0x17c608,radio,*header[:3])
  assert calls==['cnmgr_disconnect','cnmgr_power_off']
 else:assert not events and not calls
 ownership.append({'supplied_lifecycle_command':lifecycle,'original_field_20':flag,'following_command':3,'imported_calls':list(calls)})
report={'passed':True,'SpiderApp_sha256':digest,'cases':rows,'continuous_deactivation':deactivation,'deactivate_reactivate_then_quit':ownership,'physical_device_or_ipc':False,
 'limits':['Initial radio/connection/browser/root contexts and eligibility supplied; actual app-switch reachability not established.',
           'Registered slot3 callback and root action execute, coordinator captured then its radio participant called explicitly; other coordinator participants not executed.',
           'Original parent, dispatcher and API wrappers execute; imported network calls return modeled success.',
           'Commands6/7 then3 supplied directly to original radio participant; full manager/deactivation Main chain not executed.',
           'Additional slot6->Root->snapshot consumer->Root->command6 chain executes with snapshot mode2 bypass; coordinator captured then participant called explicitly.',
           'Daemon disconnect/power-off processing not executed; this does not establish cause of user-reported IP loss.']}
(ROOT/'sources/stock-wifi-release.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
