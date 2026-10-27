"""Stock saved-profile connection selection; synthetic profiles, no driver/IPC.
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
for priorities in ((10,20),(30,5),(7,7)):
 for state,kind in ((2,12),):
  count=0;expected=4
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x2000000,0x50000);obj=0x2001000;end=0x2000100;replies=[];state_writes=[]
  def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,n):u.mem_write(a,struct.pack('<I',n))
  put(obj,91);put(obj+8,92);put(obj+0xa09c,state);put(obj+0x13254,count)
  put(obj+0xa0b4,2)
  for i,priority in enumerate(priorities):
   record=obj+0xa138+i*1004;u.mem_write(record,bytes([65+i])+bytes(1003));put(record+0x2a0,priority)
  chosen=[];driver_calls=[];event=None;request_fd=91;reply_fd=92
  request=struct.pack('<I',16)+bytes(1016)
  def hook(uc,pc,size,unused):
   r0,r1,r2=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
   if pc==end:uc.emu_stop();return
   elif pc in drivers:
    assert drivers[pc] in ('cnmgr_ip_prepare','cnmgr_wlan_config','cnmgr_ip_set_connect_info','cnmgr_wlan_connect','cnmgr_ip_start')
    driver_calls.append(drivers[pc])
    if drivers[pc]=='cnmgr_wlan_config':chosen.append(bytes(uc.mem_read(r1,1)).decode())
   elif pc==0xa1a0:pass  # synthetic profile validation boundary
   elif pc==0x9fac:
    if event is None:assert r0==request_fd and r2==1020;uc.mem_write(r1,request);result=1020
    elif isinstance(event,bytes):assert r0==95 and r2==256;uc.mem_write(r1,event);result=len(event)
    else:assert r0==94 and r2==4;put(r1,event);result=4
   elif pc==0x9ae4:
    assert r0==reply_fd and r2==1012;replies.append(word(r1));result=1012
   elif pc==0x9a6c:uc.mem_write(r0,bytes([r1&255])*r2);result=r0
   elif pc==0x9b80:uc.mem_write(r0,bytes(uc.mem_read(r1,r2)));result=r0
   elif pc==0x9b14:
    a=bytes(uc.mem_read(r0,r2)).split(b'\0')[0];b=bytes(uc.mem_read(r1,r2)).split(b'\0')[0];result=0 if a==b else 1
   elif pc==0x14698:pass  # timer scheduling modeled, not a real timer
   elif pc in (0xa14c,0xa760,0x2327c):pass
   else:return
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  def write(uc,access,address,size,value,unused):
   if address<obj+0xa0a0 and address+size>obj+0xa09c:state_writes.append(value)
  def reject(*args):raise AssertionError('Unexpected system instruction')
  u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write);u.hook_add(UC_HOOK_INTR,reject)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(0xba18,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==end and word(obj+0xa09c)==3 and replies==[0] and word(obj+20)==0
  replies.clear();request=struct.pack('<I',kind)+bytes(1016)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(0xba18,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==end and replies==[]
  assert word(obj+0xa09c)==4 and state_writes==[3,4] and word(obj+20)==7
  assert chosen==['A' if priorities[0]>=priorities[1] else 'B']
  assert driver_calls==['cnmgr_ip_prepare','cnmgr_wlan_config','cnmgr_ip_set_connect_info']
  steps=[];put(obj+0x428,95);put(obj+0xa080,94)
  for event,entry,wanted in ((b'SUCCESS set\n',0xd8b0,5),(b'SUCCESS set\n',0xd8b0,6),(b'CONNECTED\n',0xd8b0,7),(0,0xb538,8)):
   for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
   u.emu_start(entry,end,count=30000)
   assert u.reg_read(UC_ARM_REG_PC)==end and word(obj+0xa09c)==wanted
   assert replies==([0] if wanted==8 else [])
   steps.append({'supplied_event':event.decode().strip() if isinstance(event,bytes) else 'IP start success','internal_state_after':wanted,'reply_count':len(replies)})
  assert word(obj+20)==0 and state_writes==[3,4,5,6,7,8]
  before=len(driver_calls);event=None;request=struct.pack('<I',27)+bytes(1016)
  request_fd=96;reply_fd=97;put(obj+4,96);put(obj+12,97)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,1),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(0xba18,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==end and replies==[0,0]
  assert word(obj+0xa09c)==8 and word(obj+20)==word(obj+24)==0
  assert len(driver_calls)==before and state_writes==[3,4,5,6,7,8]
  rows.append({'prepare_command':16,'prepare_reply':0,'command':kind,'initial_internal_state':state,'profile_field_2a0_values':priorities,'selected_profile_marker':chosen[0],'state_after_selection':4,'pending_kind_after_selection':7,'completion_steps':steps,'final_internal_state':8,'api_reply':0,'modeled_driver_calls':driver_calls,'cancel_after_connect_success':{'reply':0,'internal_state_after':8,'new_driver_calls':0,'new_state_writes':0}})
report={'passed':True,'daemon_sha256':digest,'cases':rows,'physical_device_or_ipc':False,
 'limits':['Saved profiles, field0x2a0 values and initial internal state2 supplied synthetically; prepare command executes before connect.',
           'Original selection loop, pending-kind rewrite and state transition execute.',
           'Profile validation and WLAN/IP configuration boundaries modeled success; no actual SSID/credentials/configuration used.',
           'Original WLAN/IP handlers consume synthetic acknowledgements and connected/IP-success events; actual drivers and timer scheduling modeled.',
           'Cancel27 is also executed after successful completion on the same object: reply0 without disconnect or state change.',
           'Does not prove field semantics, actual profile validity, driver-command production or default-network choice on hardware.']}
(ROOT/'sources/stock-cnmgr-saved-selection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
