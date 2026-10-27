"""Stock masked service dispatcher; per-item operations remain virtual."""
import runpy,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];reply=0;items=[]
def hook(uc,pc,size,data):
 if pc not in (0xf647c,0xf6a58):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==0xf647c:answer=0x60013000
 else:
  assert a[0]==0x60013000 and a[1]==0x117fc and a[3]==0,a
  items.append(a[2]);answer=reply
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[];baseline=None
for reply in (0,7,0x106):
 items.clear();result=n['call'](0xea6fc,(0,0x407f,0x117fc,0))
 if reply==0:baseline=items.copy();assert len(baseline)>1
 assert items==(baseline[:1] if reply==0x106 else baseline)
 assert result==reply
 rows.append({'per_item_reply_fixture':hex(reply),'item_ids':items.copy(),'dispatcher_return':hex(result)})
r={'SpiderApp_sha256':n['digest'],'scope':'Nativeea6fc/ea200 with mask407f; f647c and f6a58 mocked','cases':rows,'limits':['Mask407f supplied; b4964 mode mapping not integrated here.','Item routines and callback execution remain virtual; no service or hardware success proof.']}
Path(n['ROOT'],'sources/native-gui-resume-mask.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows))
