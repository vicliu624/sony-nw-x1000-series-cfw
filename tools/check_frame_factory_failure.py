"""Native frame-factory failure with child-control allocation returning null."""
import runpy,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];frames=[];allocations=[];base=0x75cf44
u.mem_write(base,bytes(0x13c))
def hook(uc,pc,size,data):
 if pc==0x112878:frames.append(uc.reg_read(UC_ARM_REG_R0));return
 if pc!=0xe9300:return
 allocations.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[]
for attempt in range(4):
 result=n['call'](0xb5f88,(9,0,0,0))
 assert result==0 and n['word'](base+0x138)==0
 occupied=[n['word'](base+i*104+0x4c) for i in range(3)]
 assert occupied==[1]*min(attempt+1,3)+[0]*max(2-attempt,0),occupied
 rows.append({'attempt':attempt+1,'returned_handle':0,'manager_count':0,'occupied_slot_flags':occupied})
assert frames==[base,base+104,base+208] and len(allocations)==3
r={'SpiderApp_sha256':n['digest'],'scope':'Nativeb5f88/112050/112878; child-control allocator e9300 returns null virtually','cases':rows,'limits':['Empty initial frame manager supplied; actual allocation failure not induced on device.', 'Native initializer marks slot occupied before allocation, factory returnsnull without count increment; no caller-level recovery/cleanup included.', 'Not a claim that normal app return hits this failure, nor a firmware modification.']}
Path(n['ROOT'],'sources/native-frame-factory-child-failure.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
