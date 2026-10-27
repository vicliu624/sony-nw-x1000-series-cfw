"""Stock cancel acknowledgement while a connect request remains pending; no IPC.
Proves only these command handlers, not daemon-loop or application exit policy.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/qqmusic-wifi/cnmgr_daemon').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
elf=ELFFile(io.BytesIO(raw));symbols=elf.get_section_by_name('.symtab')
drivers={s['st_value']:s.name for s in symbols.iter_symbols() if s.name.startswith(('cnmgr_wlan_','cnmgr_ip_')) and s['st_value']}
rows=[]
for state,expected in ((3,11),(6,12),(7,14)):
 for kind,count in ((27,1),):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x2000000,0x50000);obj=0x2001000;end=0x2000100;replies=[];state_writes=[]
  def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,n):u.mem_write(a,struct.pack('<I',n))
  put(obj,90);put(obj+4,91);put(obj+8,92);put(obj+12,93);put(obj+20,7);put(obj+0xa09c,state);put(obj+0x13254,count);driver_calls=[]
  request=struct.pack('<I',kind)+bytes(1016);phase='cancel'
  def hook(uc,pc,size,unused):
   r0,r1,r2=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
   if pc==end:uc.emu_stop();return
   elif pc==0x12cfc:
    driver_calls.append('cnmgr_ip_cancel_start');return  # execute original IP cancellation/status mutation
   elif pc in drivers:
    assert drivers[pc] in ('cnmgr_wlan_cancel','cnmgr_ip_dhcp_stop','cnmgr_ip_stop','cnmgr_wlan_disconnect')
    driver_calls.append(drivers[pc])
   elif pc==0x9fac:
    if phase=='cancel':assert r0==91 and r2==1020;uc.mem_write(r1,request);result=1020
    elif phase=='ip_stopped':assert r0==94 and r2==4;put(r1,2);result=4
    else:
     assert r0==95 and r2==256;message=b'DISCONNECTED\n' if phase=='disconnected' else b'SUCCESS cancel\n';uc.mem_write(r1,message);result=len(message)
   elif pc==0x9ae4:
    assert r0==(93 if phase=='cancel' else 92) and r2==1012;replies.append(word(r1));result=1012
   elif pc==0x9b14:
    a=bytes(uc.mem_read(r0,r2)).split(b'\0')[0];b=bytes(uc.mem_read(r1,r2)).split(b'\0')[0];result=0 if a==b else 1
   elif pc==0x9a6c:uc.mem_write(r0,bytes([r1&255])*r2);result=r0
   elif pc in (0xa14c,0xa760,0x2327c):pass
   else:return
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  def write(uc,access,address,size,value,unused):
   if address<obj+0xa0a0 and address+size>obj+0xa09c:state_writes.append(value)
  def reject(*args):raise AssertionError('Unexpected system instruction')
  u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write);u.hook_add(UC_HOOK_INTR,reject)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,1),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(0xba18,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==end and replies==[0]
  assert word(obj+0xa09c)==expected and state_writes==[expected]
  assert word(obj+20)==7 and word(obj+24)==0
  assert driver_calls=={3:[],6:['cnmgr_wlan_cancel'],7:['cnmgr_ip_cancel_start','cnmgr_ip_dhcp_stop','cnmgr_ip_stop']}[state]
  row={'command':kind,'initial_internal_state':state,'state_after_cancel_ack':expected,'cancel_reply_status':replies[0],'original_connect_pending_at_ack':word(obj+20),'cancel_pending_after':word(obj+24),'modeled_driver_calls':list(driver_calls)}
  def event_call(entry):
   for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
   u.emu_start(entry,end,count=30000);assert u.reg_read(UC_ARM_REG_PC)==end
  if state==6:
   phase='completion';put(obj+0x428,95)
   event_call(0xd8b0)
   assert u.reg_read(UC_ARM_REG_PC)==end and replies==[0,4]
   assert word(obj+0xa09c)==2 and word(obj+20)==0
   row['completion']={'supplied_event':'SUCCESS cancel','original_connect_reply':4,'final_internal_state':2,'pending_connect_after':0}
  elif state==7:
   phase='ip_stopped';put(obj+0xa080,94);event_call(0xb538)
   assert word(obj+0xa09c)==13 and word(obj+20)==7 and replies==[0]
   phase='disconnected';put(obj+0x428,95);event_call(0xd8b0)
   assert word(obj+0xa09c)==2 and word(obj+20)==0 and replies==[0,15], (word(obj+0xa09c),word(obj+20),replies,state_writes,driver_calls)
   row['completion']={'supplied_events':['IP stop completed','DISCONNECTED'],'supplied_ip_mode':0,'driver_boundary_trace':list(driver_calls),'original_connect_reply':15,'intermediate_internal_state':13,'final_internal_state':2,'pending_connect_after':0}
  rows.append(row)
report={'passed':True,'daemon_sha256':digest,'cases':rows,'physical_device_or_ipc':False,
 'limits':['Initial inflight connect and cancel on channel1 supplied synthetically.',
           'Original command handler/reply executes; driver calls return modeled success.',
           'State6 case additionally delivers synthetic SUCCESS cancel through original WLAN event handler; connect reply4/pending clear/state2 execute.',
           'State7 additionally executes original IP cancellation with supplied IP mode0; DHCP stop modeled, original sets status15; event handlers reach13 then2 and reply15.',
           'State3 completion and physical driver timing are not proven.']}
(ROOT/'sources/stock-cnmgr-cancel-ack.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
