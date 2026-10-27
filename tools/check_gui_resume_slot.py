"""Native4e388 slot transition; downstream manager operations virtual."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];obj=0x60014000;calls=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
def hook(uc,pc,size,data):
 if pc not in (0xdde70,0xddeb0,0xde3c0):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
 if pc==0xdde70:answer=0x60015000
 else:
  assert a[0]==0x60015000
  calls.append({'service':hex(pc),'code':a[1]});answer=0
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);put(0x613f00+0x48,obj);rows=[]
for initial in (0,1):
 for request in (0,1):
  u.mem_write(obj,bytes(24));put(obj+12,4);put(obj+16,initial);calls.clear()
  n['call'](0x4e388,(0x613f00,request,0,0))
  assert n['word'](obj+16)==request
  expected=([{'service':'0xde3c0','code':1}] if initial else [])+([{'service':'0xddeb0','code':5}] if request else [])
  assert calls==expected,calls
  rows.append({'slot1_active_before':initial,'request':request,'slot1_active_after':n['word'](obj+16),'slot1_code_after':hex(n['word'](obj+12)),'manager_calls':calls.copy()})
r={'SpiderApp_sha256':n['digest'],'scope':'Native4e388/2a4e0/2a5bc/2a334/2a420/2a3dc; downstream manager virtual','cases':rows,'limits':['owner+48 pointer and slot state supplied.','Service codes1/5 not assigned display/input/hardware identities.','No actual manager scheduling, page drawing or hardware operation.']}
Path(n['ROOT'],'sources/native-gui-resume-slot.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
