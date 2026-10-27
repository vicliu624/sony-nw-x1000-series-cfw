"""Native resource handle pool init/allocation/exhaustion; only memset is virtual."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];manager=0x7a0660;pool=manager+0x18284;out=0x60014000

def hook(uc,pc,size,data):
 if pc==0x126af8:
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if pc!=0xd574:return
 p=uc.reg_read(UC_ARM_REG_R0);v=uc.reg_read(UC_ARM_REG_R1)&255;size=uc.reg_read(UC_ARM_REG_R2)
 uc.mem_write(p,bytes([v])*size);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
assert n['call'](0x132938,(pool,1,0,0))==0
u.mem_write(out,struct.pack('<I',0xdeadbeef));assert n['call'](0x133060,(out,2,0,0))==0
assert n['word'](out)==0 and n['word'](manager)==1
first={'return':0,'handle':0,'manager_count':n['word'](manager)}
u.mem_write(out,struct.pack('<I',0xdeadbeef));result=n['call'](0x133060,(out,2,0,0))
assert result==0x1003 and n['word'](out)==0xdeadbeef and n['word'](manager)==1
r={'SpiderApp_sha256':n['digest'],'scope':'Native132938/133060/11e98c/11eb20/1329c0 allocation; memset virtual','pool_capacity_fixture':1,'first':first,'exhausted':{'return':hex(result),'output_handle_unchanged':True,'manager_count':n['word'](manager)},'limits':['Pool initialized with supplied capacity1; actual startup pool capacity not established.','No DAT reads, real allocation or physical resource operation.']}
assert n['call'](0x133088,(0,0,0,0))==0 and n['word'](manager)==0
assert n['call'](0x133088,(0,0,0,0))==0x1001 and n['word'](manager)==0
for cycle in range(100):
 assert n['call'](0x133060,(out,2,0,0))==0 and n['word'](out)==0 and n['word'](manager)==1
 assert n['call'](0x133088,(0,0,0,0))==0 and n['word'](manager)==0
r['empty_group_roundtrip']={'cycles':100,'manager_count_after':n['word'](manager),'reused_handle':0,'double_release_return':'0x1001'}
r['limits'].append('Empty group release executes native133088/11ed9c/132a20; packed-container cleanup126af8 mocked. No loaded textures or allocator leak coverage.')
Path(n['ROOT'],'sources/native-gui-resource-pool.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
