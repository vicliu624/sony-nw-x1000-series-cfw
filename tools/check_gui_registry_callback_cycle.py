"""Original registry phase callbacks and module request ordering; handlers remain virtual."""
import runpy,struct,json,argparse
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stock-descriptors',action='store_true');parser.add_argument('--inactive-handlers',action='store_true');parser.add_argument('--active-parent0',action='store_true');args=parser.parse_args();assert not args.active_parent0 or args.inactive_handlers;assert not args.inactive_handlers or args.stock_descriptors
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];u.mem_map(0xe60000,0x2000);registry=0xe601e0;calls=[];bridges=[];handlers={};handler_hits=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if args.active_parent0 and pc==0xe87f4:
  uc.reg_write(UC_ARM_REG_R0,0x6001b000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if args.active_parent0 and pc in (0xe9690,0x1124b4):pass
 elif args.stock_descriptors and pc==0xd574:
  assert a[1:3]==[0,76];uc.mem_write(a[0],bytes(76))
 elif args.stock_descriptors and pc in handlers:
  mid,operation,obj=handlers[pc]
  request=list(struct.unpack('<3I',uc.mem_read(a[1],12)))
  assert a[0]==obj and request[0]==mid and request[2]==0 and a[2:]==[0,0x60014000],(mid,a,request)
  handler_hits.append({'id':mid,'operation':operation,'handler':hex(pc),'object':hex(obj),'converted_parameter':hex(request[1])})
  if args.inactive_handlers:
   assert n['word'](obj)==int(args.active_parent0 and mid==0),(mid,hex(obj))
   return
 elif pc in (0xdf8a4,0xdf8c8):
  assert a[0]==registry and a[2:]==[0,0],a
  calls.append({'operation':'attach' if pc==0xdf8a4 else 'detach','id':a[1]})
  if args.stock_descriptors:return
 elif pc in (0x2d8f0,0x2d938):
  assert a[1]==0x60014000;bridges.append(hex(pc))
 elif pc in (0xa7a0c,0x28bc0,0x112ddc):pass
 else:return
 uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);put(0x613f00+0x5eb8,0x60014000);put(registry+0x12f4,0xffffffff)
if args.stock_descriptors:
 u.reg_write(UC_ARM_REG_SP,0x60018000);u.emu_start(0x14d0c,0x14d40,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x14d40 and n['word'](registry)==16
 for mid in range(16):
  descriptor=n['word'](registry+4+mid*4);assert descriptor==0x4de800+mid*28
  values=list(struct.unpack('<7I',u.mem_read(descriptor,28)))
  obj=n['call'](values[1],(0,0,0,0))
  for offset,operation in ((5,'attach'),(6,'detach')):handlers[values[offset]]=(mid,operation,obj)
 put(registry+0x12f4,0xffffffff);put(registry+0x12f8,0x60014000)
assert n['call'](0x14d74,(0,0,0,0))==0
assert n['word'](registry+0x1304)==0x14a14 and n['word'](registry+0x1308)==0x14b74
if args.active_parent0:
 put(0x62324c,1);put(0x69c7cc+0x24,0x60015000)
 put(0x60014000,0x60016000);put(0x60014044,0)
 put(0x60015000+0x460,8);put(0x60015000+0x4c8,0x60017000);put(0x60015000+0x4f4,1)
 put(0x60017000+0xae4,14);put(0x60017000+0x460,0x8000);put(0x60017000+0x4f4,1)
order=[0,2,3,4,5,6,7,8,9,10,11,13,15]
assert n['call'](0xdf9f4,(registry,0,0,0))==0 and n['word'](registry+0x1300)==1
assert calls==[{'operation':'attach','id':i} for i in order],calls
if args.active_parent0:assert n['word'](0x60014044)==1 and n['word'](0x60014004)==0x60015000 and n['word'](0x60017000+0x460)==0
before=calls.copy();assert n['call'](0xdf9f4,(registry,0,0,0))==11 and calls==before
assert n['call'](0xdfb00,(registry,0,0,0))==0 and n['word'](registry+0x1300)==0
assert calls==before+[{'operation':'detach','id':i} for i in order],calls
before=calls.copy();assert n['call'](0xdfb00,(registry,0,0,0))==11 and calls==before
assert bridges==['0x2d8f0','0x2d938']
if args.active_parent0:assert n['word'](0x60014044)==0 and n['word'](0x60014004)==0 and n['word'](0x60017000+0x460)==0x8000
r={'SpiderApp_sha256':n['digest'],'scope':'Original registration14d74 and registrydf9f4/dfb00 invoke native14a14/14b74; module handlers/bridges virtual','current_module_fixture':-1,'module_operations':calls,'bridge_operations':bridges,'duplicate_start_return':11,'duplicate_stop_return':11,'phase_after':0,'limits':['Module handlers intercepted at df8a4/df8c8; no actual module UI tree operations.','Current module -1 and frame handle supplied; other contexts may take different branches.','No display/touch driver initialization or physical UI restoration proved.']}
if args.stock_descriptors:
 assert [(h['operation'],h['id']) for h in handler_hits]==[(operation,i) for operation in ('attach','detach') for i in order],handler_hits
 r['stock_descriptor_handlers']=handler_hits
 r['scope']='Original phase callbacks and native descriptor/getter/converter dispatch; actual handler bodies intercepted'
 r['limits']=['Original14d0c initializes/registers16 descriptors; no supplied descriptor pointers. Native getters/converters execute.', 'Original callback loops dispatch through df8a4/df8c8 to actual stock handler addresses, where bodies are intercepted.', 'Current module-1, parent context and frame handle supplied; actual module UI tree and hardware operations unqualified.']
if args.inactive_handlers:
 r['scope']='Original registry phase callbacks and stock handler bodies on inactive object fixtures; bridges virtual'
 r['limits']=['Module first state fields observed0 before each actual handler body; this does not initialize active runtime objects.', 'Native26 attach/detach handlers return in supplied inactive state; no active control-tree operation qualified.', 'Current module-1 and parent/frame context supplied; bridge services remain virtual; no hardware operations.']
if args.active_parent0:
 r['scope']='Native registered phase callbacks and stock module0 attach/detach perform real parent-record/tree-flag roundtrip'
 r['active_module0']={'count_field':{'offset':'0x44','meaning':'managed-control count, not update boolean','insert_function':'0x112a8c','insert_count_write':'0x112b8c','slots':16},'parent_count_after_attach':1,'parent_count_after_detach':0,'child_pointer_after_detach':0,'descendant_flag_after_detach':'0x8000'}
 r['limits']=['Module0 activity, parent/root/child/type14 descendant and initialized-child markers supplied; other modules inactive.', 'Original phase callbacks, descriptor/getter/converter/handler and insertion/removal/tree traversal execute.', 'Manager getter/frame dispatch/parent invalidation and callback bridges virtual; no actual rendering or runtime module initialization.']
Path(n['ROOT'],'sources/native-gui-registry-active-parent-cycle.json' if args.active_parent0 else 'sources/native-gui-registry-inactive-cycle.json' if args.inactive_handlers else 'sources/native-gui-registry-stock-cycle.json' if args.stock_descriptors else 'sources/native-gui-registry-callback-cycle.json').write_text(json.dumps(r,indent=2)+'\n');print('Original callback registration/start/stop and duplicate gates passed')
