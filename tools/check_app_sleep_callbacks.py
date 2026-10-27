"""Pinned original APF sleep/awake callbacks through Root command selection; offline."""
from pathlib import Path
import runpy,contextlib,io,struct,json,hashlib
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(ROOT/'tools/check_spider_restore_dispatch.py'))
u=m['u'];g=m['hook'].__globals__;g['intercept_actions']=False;g['deactivate_probe']=False
ctx=0x820f68;root=0x60010000;state={'packet':None,'received':False,'next_receive':False};commands=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
def hook(uc,pc,size,data):
 a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]];ret=0
 if pc==0x268d48:
  if state['received']:state['next_receive']=True;uc.emu_stop();return
  uc.mem_write(a[1],state['packet']);put(a[3],len(state['packet']));state['received']=True
 elif pc==0x268c9c:pass
 elif pc in [0xe5ac,0x33b748,0x33b918,0x337a80,0x337ae8,0x117f0,0x140c8,0xb17c4]:pass
 elif pc==0xffa4:ret=0x613e60
 elif pc==0xe5f4:ret=0x6001e000
 elif pc==0x61310:ret=0x6001e100
 elif pc==0xb0bdc:put(a[0],0);put(a[0]+4,0)
 elif pc==0xf680:ret=0
 elif pc==0x112fc:commands.append(a[1]);put(a[2],0)
 else:return
 uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_R7,0x60010000);u.emu_start(0xfcb4,0xfd68,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0xfd68
assert word(ctx+0x2c+3*4)==0xecb8 and word(ctx+0x2c+2*4)==0xf090
put(ctx+4,2);put(ctx+0x24,1);put(ctx+0x1c,501);put(ctx,1);put(ctx+0x10,500);put(ctx+0xc,55)
c=bytearray(32);c[0]=2;c[1]=1;c[13]=10;struct.pack_into('<I',c,4,0x3f4f18);u.mem_write(root,bytes(c))
rows=[]
for opcode,expected_event,expected_command in [(3,0x420013,1),(2,0x420014,11)]:
 state.update(packet=struct.pack('<5I',20,0,opcode,0,0),received=False,next_receive=False);g['queued'].clear();commands.clear()
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
 rows.append({'apf_wire_words':[20,0,opcode,0,0],'application_event':hex(expected_event),'root_before':before,'root_after':after,'coordinator_command':commands.copy()})
r={'passed':True,'SpiderApp_sha256':m['digest'],'cases':rows,'scope':'Original registration, APF receive dispatch, slot3/slot2 callbacks and Root actions execute; receive loop stops at the next IPC receive boundary (which may be a nested request/reply), command coordinator boundary intercepted, input wire/Root state/mode helpers/locks virtual. Does not execute hardware sleep, full GUI recovery or prove the user hang cause.','physical_device_access':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'work/external-language-bridge-8-ram-snapshot/app-sleep-callbacks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
