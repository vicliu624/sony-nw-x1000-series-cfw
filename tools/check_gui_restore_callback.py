"""Stock restoration callback117fc ->109e4; ticket query executes native field read."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u']
value=0;queries=[]
def hook(uc,pc,size,data):
 if pc!=0x336640:return
 assert uc.reg_read(UC_ARM_REG_R0)==0x60013000
 queries.append(hex(pc));return
u.hook_add(UC_HOOK_CODE,hook);u.mem_write(0x613f00+0x4c,struct.pack('<I',0x60013000));rows=[]
for value in (0,1,7):
 u.mem_write(0x60013000+12,struct.pack('<I',value));queries.clear();result=n['call'](0x117fc,(0,0,0,0))
 assert result==(0x106 if value else 0) and len(queries)==1
 rows.append({'ticket_query_result_fixture':value,'callback_return':hex(result)})
r={'SpiderApp_sha256':n['digest'],'scope':'Original117fc and109e4 execute;336640 executes native field read','cases':rows,'limits':['Query object supplied; no concurrent cancellation, GUI service or hardware operations.','Nonzero callback106 is not automatically a hardware error code.']}
Path(n['ROOT'],'sources/native-gui-restore-callback.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows))
