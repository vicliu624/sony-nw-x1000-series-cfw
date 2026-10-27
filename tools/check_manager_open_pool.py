"""Original mode0 manager-open pool prefix, success and allocation-failure cases."""
import runpy,struct,json,argparse
p=argparse.ArgumentParser();p.add_argument("--reserved-root",action="store_true");args=p.parse_args()
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
rows=[]
for fail in (False,True):
 n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];manager=0x6dfa18;backing=0x61000000;requests=[];services=[]
 u.mem_map(backing,0x200000);u.mem_write(backing,bytes([0xa5])*0x200000)
 def hook(uc,pc,size,data):
  if args.reserved_root and pc in (0xd574,0xd85c):
   a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
   u.mem_write(a[0],bytes([a[1]&255])*a[2] if pc==0xd574 else bytes(u.mem_read(a[1],a[2])))
   uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc not in (0x11649c,0x132a78):return
  arg=uc.reg_read(UC_ARM_REG_R0);services.append(hex(pc))
  if pc==0x132a78:requests.append(arg)
  uc.reg_write(UC_ARM_REG_R0,0 if pc==0x11649c or fail else backing)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 assert n['call'](0xe8b64,(manager,383,0,0))==0
 assert n['word'](manager+0x378)==383
 if fail:
  assert n['call'](0xe9388,(manager,0,0,0))==3
  assert n['word'](manager+0x370)==0 and n['word'](manager+0x374)==0
 else:
  for reg,v in ((UC_ARM_REG_R0,manager),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x60008000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,v)
  stop=0xe948c if args.reserved_root else 0xe9414
  u.emu_start(0xe9388,stop,count=100000)
  assert u.reg_read(UC_ARM_REG_PC)==stop
  assert n['word'](manager+0x370)==backing and n['word'](manager+0x374)==383*4936
  assert all(n['word'](backing+i*4936+0x460)==0 for i in range(1 if args.reserved_root else 0,383))
  assert struct.unpack('<2H',u.mem_read(manager+0x380,4))==((1 if args.reserved_root else 0),383)
  if args.reserved_root:
   assert n['word'](manager+0x29b68)==backing
   assert n['word'](manager+0x788)==1
   assert n['word'](backing+0xae4)==1
   assert struct.unpack('<3i',u.mem_read(backing+0x2f4,12))==(120,216,0)
   assert struct.unpack('<2I',u.mem_read(backing+0x3a8,8))==(240,432)
  else:assert u.mem_read(backing,4)==bytes([0xa5])*4
 assert requests==[383*4936],requests
 rows.append({'allocation_failure':fail,'requested_bytes':requests[0],'native_capacity':383,'control_stride':4936,'stop_before':None if fail else ('0xe948c' if args.reserved_root else '0xe9414'),'return':3 if fail else None,'virtual_services':services})
r={'SpiderApp_sha256':n['digest'],'scope':'Native mode0 open pool allocation/flag clearing/index-pool init, not full open','cases':rows,'limits':['Display setup11649c and allocator132a78 virtual; no physical display or mmap.', 'Success stops before reserved-root descriptor creation at e9414; full function return/startup not proved.', 'Capacity383 comes from original setter; byte count is runtime object storage, not firmware partition usage.']}
if args.reserved_root:
 r['scope']='Native mode0 pool and reserved-root construction, then stop before module startup'
 r['reserved_root']={'type':1,'position':[120,216,0],'size':[240,432],'index_pool_used':1,'pending_controls':1,'constructor_chain':['0xe9300','0xf01f8','0xedea8']}
 r['limits']=['Display setup11649c and allocator132a78 virtual; memory services virtual.', 'Success stops at e948c before module startup; full open return, physical display and Home construction not proved.', 'Runtime object RAM is not firmware partition capacity.']
Path(n['ROOT'],'sources/native-manager-open-root.json' if args.reserved_root else 'sources/native-manager-open-pool.json').write_text(json.dumps(r,indent=2)+'\n')
print('Native manager mode0 pool prefix and allocation failure verified')
