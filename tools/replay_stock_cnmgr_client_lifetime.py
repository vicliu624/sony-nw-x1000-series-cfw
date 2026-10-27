"""Full stock daemon INIT/FIN request handling; synthetic pipes, no driver/IPC.
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
for state in (0,2,8):
 for kind,count,expected in ((29,0,1),(30,1,0)):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x2000000,0x50000);obj=0x2001000;end=0x2000100;replies=[];state_writes=[]
  def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  def put(a,n):u.mem_write(a,struct.pack('<I',n))
  put(obj,91);put(obj+8,92);put(obj+0xa09c,state);put(obj+0x13254,count)
  request=struct.pack('<I',kind)+bytes(1016)
  def hook(uc,pc,size,unused):
   r0,r1,r2=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
   if pc==end:uc.emu_stop();return
   elif pc in drivers:raise AssertionError('Unexpected driver operation: '+drivers[pc])
   elif pc==0x9fac:
    assert r0==91 and r2==1020;uc.mem_write(r1,request);result=1020
   elif pc==0x9ae4:
    assert r0==92 and r2==1012;replies.append(word(r1));result=1012
   elif pc==0x9a6c:uc.mem_write(r0,bytes([r1&255])*r2);result=r0
   elif pc in (0xa14c,0xa760,0x2327c):pass
   else:return
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  def write(uc,access,address,size,value,unused):
   if address<obj+0xa0a0 and address+size>obj+0xa09c:state_writes.append(value)
  def reject(*args):raise AssertionError('Unexpected system instruction')
  u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,write);u.hook_add(UC_HOOK_INTR,reject)
  for reg,value in ((UC_ARM_REG_R0,obj),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
  u.emu_start(0xba18,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==end and replies==[0] and word(obj+0x13254)==expected
  assert word(obj+0xa09c)==state and state_writes==[] and word(obj+20)==0
  rows.append({'command':kind,'initial_internal_state':state,'counter_before':count,'counter_after':expected,'reply_status':replies[0],'state_write_count':0,'driver_call_count':0})
report={'passed':True,'daemon_sha256':digest,'cases':rows,'physical_device_or_ipc':False,
 'limits':['Synthetic command pipe and daemon context; original full command handler and reply cleanup execute.',
           'No state writes or WLAN/IP calls in these INIT/FIN requests, including FIN1->0 at supplied CONNECT state8.',
           'Daemon main loop, other events, client-library local cleanup and Spider exit policy not executed.']}
(ROOT/'sources/stock-cnmgr-client-lifetime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(rows),'driver_calls':0,'state_writes':0}))
