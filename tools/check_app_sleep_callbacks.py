"""Pinned APF slot3/slot2 callbacks through Root selection; offline, not wake proof."""
from pathlib import Path
import runpy,contextlib,io,struct,json,hashlib
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(ROOT/'tools/check_spider_restore_dispatch.py'))
u=m['u'];g=m['hook'].__globals__;g['intercept_actions']=False;g['deactivate_probe']=False
ctx=0x820f68;root=0x60010000;state={'packet':None,'received':False,'next_receive':False};commands=[];command_sites=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
def hook(uc,pc,size,data):
 a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]];ret=0
 if pc==0x268d48:
  if state['received']:state['next_receive']=True;uc.emu_stop();return
  uc.mem_write(a[1],state['packet']);put(a[3],len(state['packet']));state['received']=True
 elif pc==0x268c9c:pass
 elif pc in [0xe5ac,0x33b748,0x33b918,0x337a80,0x337ae8,0x117f0,0x140c8,0xb17c4,0xe684,0xe600,0x13bf8]:pass
 elif pc==0x48b40:put(a[1],0)
 elif pc==0xe678:put(a[1],0)
 elif pc==0xffa4:ret=0x613e60
 elif pc==0xe5f4:ret=0x6001e000
 elif pc==0x61310:ret=0x6001e100
 elif pc==0xb0bdc:put(a[0],0);put(a[0]+4,0)
 elif pc==0xf680:ret=0
 elif pc==0x112fc:commands.append(a[1]);command_sites.append(hex(uc.reg_read(UC_ARM_REG_LR)-4));put(a[2],0)
 else:return
 uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_R7,0x60010000);u.emu_start(0xfcb4,0xfd68,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0xfd68
assert word(ctx+0x2c+3*4)==0xecb8 and word(ctx+0x2c+2*4)==0xf090
put(ctx+4,2);put(ctx+0x24,1);put(ctx+0x1c,501);put(ctx,1);put(ctx+0x10,500);put(ctx+0xc,55)
c=bytearray(32);c[0]=2;c[1]=1;c[13]=10;struct.pack_into('<I',c,4,0x3f4f18);u.mem_write(root,bytes(c))
rows=[]
for opcode,expected_event,expected_command,reason in [(3,0x420013,1,0),(2,0x420014,11,0),(0,0x420017,5,0),(2,0x42001f,15,1)]:
 if opcode==0:
  put(0x6001e100,0x603)
  put(0x613e60+0x88,0)
  c[1]=3;u.mem_write(root,bytes(c))
 if reason:
  producer=json.loads((ROOT/'work/remote-manager-notification-wire-latest.json').read_text())
  assert producer['passed'] and producer['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
  produced=[item['wire'] for item in producer['cases'] if item['internal_notice']==[2,1,0]]
  assert produced==[[20,0,2,1,0]]
  packet_words=produced[0]
 else:packet_words=[20,0,opcode,0,0]
 state.update(packet=struct.pack('<5I',*packet_words),received=False,next_receive=False);g['queued'].clear();commands.clear();command_sites.clear()
 u.reg_write(UC_ARM_REG_R0,ctx);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000);
 try:u.emu_start(0x26551c,0x50000000,count=100000)
 except Exception:
  print('RX_FAIL',opcode,hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),g['queued']);raise
 assert state['next_receive'] and g['queued']==[[expected_event,0,0,0]],g['queued']
 before=list(u.mem_read(root,2))
 try:m['call'](0x17c608,(root,expected_event,0,0))
 except Exception:
  print('FAIL_PC',hex(u.reg_read(UC_ARM_REG_PC)),'LR',hex(u.reg_read(UC_ARM_REG_LR)),'R0',hex(u.reg_read(UC_ARM_REG_R0)),before,commands);raise
 after=list(u.mem_read(root,2));assert commands==[expected_command],commands
 rows.append({'apf_wire_words':packet_words,'application_event':hex(expected_event),'root_before':before,'root_after':after,'coordinator_command':commands.copy(),'coordinator_callsites':command_sites.copy()})
put(0x6001e100,0x403)
state.update(packet=struct.pack('<5I',20,0,3,0,0),received=False,next_receive=False)
g['queued'].clear();commands.clear()
u.reg_write(UC_ARM_REG_R0,ctx);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
u.emu_start(0x26551c,0x50000000,count=100000)
assert state['next_receive'] and g['queued']==[[0x410006,0,0,0]] and not commands
r={'passed':True,'SpiderApp_sha256':m['digest'],'cases':rows,'active_main_direct_prepare':{'main_fixture':'3/4','notification':3,'queued':g['queued'].copy(),'root_coordinator_calls':commands.copy()},'scope':'Original registration, APF receive dispatch, slot3/slot2 callbacks and Root actions execute; receive loop stops at the next IPC receive boundary (which may be a nested request/reply), command coordinator boundary intercepted, input wire/Root state/mode helpers/locks virtual. Does not execute hardware sleep, full GUI recovery or prove the user hang cause.','physical_device_access':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
r['slot0_limit']='Original slot0 and Root action execute with supplied Main3/6, Root2/3, zero flags and tracker/helper responses; no real wake producer or recovery qualification.'
(ROOT/'work/external-language-bridge-8-ram-snapshot/app-sleep-callbacks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
