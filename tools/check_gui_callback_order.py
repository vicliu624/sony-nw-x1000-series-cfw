"""Validate generic GUI transition callback order with an explicit action-return fixture."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];n['hook'].__globals__['intercept_actions']=False
trace=[];context=0x60010000
assert n['word'](0x3ea1dc+24)==0x3ea1fc
assert n['word'](0x3ea1fc+3*4)==0x5ce30
assert n['word'](0x3ea1dc+20)==0x3ea298
assert n['word'](0x3ea298+4*4)==0

def hook(uc,pc,size,data):
 if pc in (0x17c42c,0x33b918):
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if pc not in (0x5800c,0x5ce30):return
 state=list(uc.mem_read(context,2));trace.append({'pc':hex(pc),'mode_state_at_call':state})
 answer=5 if pc==0x5800c else 0
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
c=bytearray(32);c[0]=1;c[1]=4;c[13]=10;struct.pack_into('<I',c,4,0x3ea150);u.mem_write(context,bytes(c))
assert n['call'](0x17c608,(context,0x20307,0,0))==0
assert trace==[{'pc':'0x5800c','mode_state_at_call':[1,4]},{'pc':'0x5ce30','mode_state_at_call':[1,4]}]
assert list(u.mem_read(context,2))==[1,5]
r={'SpiderApp_sha256':n['digest'],'scope':'Generic dispatcher callback order with selected action return5 fixture','trace':trace,'after':[1,5],'descriptor_exit_table':'0x3ea1fc','descriptor_entry_table':'0x3ea298','limits':['Real5800c returns0; test replaces it with5 only to exercise a state change.','Does not establish real state4 departure event or GUI restoration completion.','5ce30 body intercepted; no page or hardware operations.']}
Path(n['ROOT'],'sources/native-gui-transition-callback-order.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

