"""Replay complete stock page/module registry setup, including both layout tables."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];u.mem_map(0xe60000,0x4000);registry=0xe601e0;memory=[]
def hook(uc,pc,size,data):
 if pc not in (0xd574,0xd85c):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
 memory.append({'service':'memset' if pc==0xd574 else 'memcpy','bytes':a[2]})
 u.mem_write(a[0],bytes([a[1]&255])*a[2] if pc==0xd574 else bytes(u.mem_read(a[1],a[2])))
 uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
result=n['call'](0x14d0c,(0,0,0,0))
print('result',result,'registered modules',n['word'](registry),'pages',n['word'](registry+0x2e8),'entries44',n['word'](registry+0x44))
assert n['word'](registry)==16 and n['word'](registry+0x2e8)==45 and n['word'](registry+0x44)==81
r={'SpiderApp_sha256':n['digest'],'scope':'Original14d0c complete registry setup; memory services virtual','module_count':16,'page_selection_bound_at2e8':45,'other_table_count_at44':81,'page_registration_data':'0x4dff44','other_registration_data':'0x4de9c0','memory_operations':memory,'limits':['No page creation, current page switch or module handlers run.','Counts describe native tables, not visible menu items.','No hardware or complete UI startup qualification.']}
Path(n['ROOT'],'sources/native-complete-page-registry.json').write_text(json.dumps(r,indent=2)+'\n')

