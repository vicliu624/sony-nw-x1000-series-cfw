"""Stock resource-group cache gate; stop before load, no physical resource operations."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];u.mem_map(0x70000000,0x30000);loads=[]
def hook(uc,pc,size,data):
 if pc==0xd574:
  p=uc.reg_read(UC_ARM_REG_R0);length=uc.reg_read(UC_ARM_REG_R2);uc.mem_write(p,bytes(length));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if pc==0x11482c:
  loads.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)])
  uc.reg_write(UC_ARM_REG_PC,0x50000000)
u.hook_add(UC_HOOK_CODE,hook);rows=[]
for group in (0,8,17):
 for active,stored,requested in ((1,0,0),(1,1,0),(0,0,0)):
  base=0x70000000;record=base+group*1956;slot=base+0xa074+group*4
  for at,value in ((record+16,active),(record+0x114,stored),(slot,0x12345678)):
   u.mem_write(at,struct.pack('<I',value))
  u.mem_write(0x60008000,struct.pack('<I',0));loads.clear();result=n['call'](0xf6a58,(base,0x117fc,group,requested))
  hit=bool(active and stored==requested)
  assert bool(loads)==(not hit)
  if hit:assert result==0 and n['word'](slot)==0
  else:assert loads==[[record,0x117fc,group]]
  rows.append({'group':group,'active_fixture':active,'stored_variant':stored,'requested_variant':requested,'cache_hit':hit,'load_boundary_reached':bool(loads),'status_slot':hex(n['word'](slot))})
r={'SpiderApp_sha256':n['digest'],'scope':'Nativef6a58/1147f8 cache gate; stops before11482c loading','cases':rows,'limits':['Group objects supplied; no actual allocation, resources or repeated-run memory leak qualification.','Miss branch uses existing virtual memset transport and stops before loading.']}
Path(n['ROOT'],'sources/native-gui-resource-cache.json').write_text(json.dumps(r,indent=2)+'\n');print('9 stock cache-gate cases passed')

