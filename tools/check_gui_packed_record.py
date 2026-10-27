"""Replay stock packed-group record commit with virtual resource creation/loading."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];record=0x60014000;path=0x60015000;status=0x60016000;services=[];stage='';error=0
def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];answer=0
 if pc==0x133060:
  assert a[:2]==[record+0x118,2],a
  services.append('create');put(a[0],17);answer=error if stage=='create' else 0
 elif pc==0x132f40:
  assert a[:2]==[path,17],a
  services.append('load');answer=error if stage=='load' else 0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.mem_write(path,b'/usr/local/share/GUI/skinRom/TEXGRP00.DAT\0');put(0x613f4c,0x60017000)
rows=[]
for stage,error in (('success',0),('create',7),('load',7),('cancel',0x106)):
 u.mem_write(record,bytes(1956));put(record,1);put(0x6001700c,1 if stage=='cancel' else 0)
 put(0x60008000,0);put(0x60008004,status);services.clear()
 result=n['call'](0x11482c,(record,0x117fc,0,path))
 assert result==error,(stage,result)
 assert n['word'](record+16)==1 and n['word'](record+0x114)==0
 assert services==(['create'] if stage=='create' else ['create','load'])
 put(status,0x1234);assert n['call'](0x1147f8,(record,0,status,0))==0 and n['word'](status)==0
 rows.append({'stage_fixture':stage,'returned':hex(result),'services':services.copy(),'active_field_after':1,'same_variant_cache_gate_after':'hit'})
r={'SpiderApp_sha256':n['digest'],'scope':'Native11482c/1146b8/117fc/336640 and1147f8; resource services virtual','cases':rows,'limits':['Supplied record and resource-service responses, not actual file failure or confirmed runtime bug.','Does not establish all callers or cleanup on error.','No firmware behavior changed.']}
Path(n['ROOT'],'sources/native-gui-packed-record.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
