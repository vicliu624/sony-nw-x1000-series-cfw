"""Stock operation5 UI construction prefix/body with virtual constructors and attachment."""
import runpy,json,argparse,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native-config',action='store_true');parser.add_argument('--native-destroy',action='store_true');parser.add_argument('--upper-delete',action='store_true');parser.add_argument('--native-base',action='store_true');parser.add_argument('--native-pool',action='store_true');parser.add_argument('--stop-operation',action='store_true');parser.add_argument('--slot-lifecycle',action='store_true');parser.add_argument('--exit-gui-state',action='store_true');args=parser.parse_args();assert not args.exit_gui_state or args.slot_lifecycle;assert not args.slot_lifecycle or args.stop_operation;assert not args.stop_operation or args.native_pool;assert not args.native_pool or (args.native_base and args.upper_delete);assert not args.native_base or args.native_config;assert not args.upper_delete or args.native_destroy;assert not args.native_destroy or args.native_config
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];control=0x60014000;frames=[];attachments=[];config=[];allocations=[];widget_requests=[];frees=[];base_cleanup=[];pool_returns=[]
if args.exit_gui_state:n['hook'].__globals__['intercept_actions']=False
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];answer=0
 if args.exit_gui_state and pc in (0xe30f8,0x17c42c,0x33b918):pass
 elif pc==0xe87f4:answer=0x60015000
 elif pc==0xe9300:
  assert a[0]==0x60015000
  if args.native_pool:return
  answer=control
 elif pc==0x108dd4:
  frames.append(a[1])
  if args.native_config:return
 elif pc==0x10e8ac:
  assert a[:3]==[control,0,0]
  sp=uc.reg_read(UC_ARM_REG_SP);config.append({'stack_arg0':n['word'](sp),'stack_arg1':n['word'](sp+4),'stack_arg4':n['word'](sp+16)})
  if args.native_config:return
 elif args.native_config and pc==0xdacc:
  assert a[0]==5280;allocations.append(a[0]);answer=0x60016000
 elif args.native_config and pc==0xd85c:
  uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));answer=a[0]
 elif args.native_config and pc==0xedea8:
  assert a[:3]==[control,22,0],a
  widget_requests.append(a)
  if args.native_base:return
  uc.mem_write(control+0xae4,(22).to_bytes(4,'little'))
 elif args.native_config and pc==0x1334f8:pass
 elif args.native_base and pc==0xd574:
  uc.mem_write(a[0],bytes([a[1]&255])*a[2]);answer=a[0]
 elif args.native_base and pc in (0x1090b4,0xef3d8,0x109404,0xf7dfc,0xf7e34,0xedb34,0xede84):pass
 elif args.native_destroy and pc==0xe0e4:
  assert a[0]==0x60016000;frees.append(a[0])
 elif args.native_destroy and pc==0xecfa4:
  assert a[0]==control;base_cleanup.append(a[0])
 elif args.upper_delete and pc==0x104810:
  assert a[:2]==[0x60015000+0x380,0],a;pool_returns.append(a[:2])
  if args.native_pool:return
 elif pc==0xe50a4:attachments.append(a[:2])
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
if args.native_pool:
 u.mem_write(0x60015000+0x370,control.to_bytes(4,'little'))
 assert n['call'](0x104730,(0x60015000+0x380,1,0,0))==0
if args.slot_lifecycle:
 u.mem_write(0x613f00+0x48,(0x6001c000).to_bytes(4,'little'))
 result=n['call'](0x4e388,(0x613f00,1,0,0))
 assert n['word'](0x6001c010)==1 and n['word'](0x6001c00c)==5
else:result=n['call'](0xddeb0,(0x6bae88,5,0,0))
assert frames==list(range(10)) and n['word'](0x6bae88+16)==control
assert config==[{'stack_arg0':30,'stack_arg1':24,'stack_arg4':48}],config
assert attachments==[[0x6baee8,control]],attachments
assert n['word'](control+0x460)&0x410==0x410
r={'SpiderApp_sha256':n['digest'],'scope':'Originalddeb0 operation5 body; UI constructors/frame formatter/attachment mocked','frame_ids':frames,'control':hex(control),'animation_arguments_raw':config,'attachment':[[hex(p) for p in pair] for pair in attachments],'flags_after':hex(n['word'](control+0x460)),'limits':['Frames are numeric constructor inputs; texture identity and animation timing units not established.','No actual control tree construction, rendering or hardware operation.','Do not classify operation5 as display-device initialization.']}
if args.native_config:
 r['scope']='Original operation5 plus native frame descriptor/config functions; base constructors and memory services virtual'
 assert allocations==[5280] and len(widget_requests)==1 and n['word'](control+0xaec)==0x60016000
 descriptors=[]
 for i in range(10):
  p=0x60016000+i*352;entry=[n['word'](p),n['word'](p+16)]
  assert entry==[3,i],entry
  descriptors.append(entry)
 r['native_descriptor_records']=descriptors;r['virtual_allocated_bytes']=5280
 r['limits'].append('Native108dd4/108d30 and10e8ac/10e860 execute; malloc/memcpy, generic widget constructoredea8 and1334f8 remain virtual. No drawing or texture identity qualified.')
if args.native_destroy:
 if args.native_base:assert n['word'](control+0x4b0)==0x10e9d0 and n['word'](control+0xae4)==22
 if args.upper_delete and not args.native_pool:
  fields=[(control+0x460,n['word'](control+0x460)|1),(0x60015000+0x37c,1),(0x60015000+0x370,control)]
  if not args.native_base:fields.append((control+0x4b0,0x10e9d0))
  for p,v in fields:
   u.mem_write(p,v.to_bytes(4,'little'))
 delete_entry=0xde3c0 if args.stop_operation else 0xecb5c if args.upper_delete else 0x10e9d0
 delete_args=(0x6bae88,1,0,0) if args.stop_operation else (control,0,0,0)
 if args.slot_lifecycle:delete_entry=0x4e388;delete_args=(0x613f00,0,0,0)
 if args.exit_gui_state:
  c=bytearray(32);c[0]=1;c[1]=4;c[13]=10;struct.pack_into('<I',c,4,0x3ea150);u.mem_write(0x6001d000,bytes(c))
  delete_entry=0x17c608;delete_args=(0x6001d000,0x20620,0,0)
 delete_result=n['call'](delete_entry,delete_args)
 assert args.stop_operation or delete_result==0
 assert n['word'](control+0xaec)==0 and frees==[0x60016000]
 delete_result=n['call'](delete_entry,delete_args)
 assert args.stop_operation or delete_result==0
 assert frees==[0x60016000] and len(base_cleanup)==(1 if args.upper_delete else 2)
 r['native_descriptor_cleanup']={'calls':2,'free_calls':len(frees),'descriptor_pointer_after':0,'base_cleanup_calls':len(base_cleanup)}
 r['limits'].append('Native10e9d0 destructor executed directly; type22 supplied by mocked base constructor; free/ecfa4 virtual, upper deletion route not yet verified.')
if args.upper_delete:
 r['limits']=[x for x in r['limits'] if 'destructor executed directly' not in x]
 assert n['word'](0x60015000+0x37c)==0 and n['word'](control+0x460)==0 and len(pool_returns)==1
 r['native_upper_delete']={'entry':'0xecb5c','callback':'0x10e9d0','manager_count_after':0,'control_flags_after':0,'pool_returns':len(pool_returns)}
 r['limits'].append('Nativeecb5c/ef6e4/e950c choose supplied4b0 destructor; callback pointer, manager base/count and active flag supplied. Pool return104810 virtual; callback installation by original constructor not yet proved.')
if args.native_base:
 r['scope']='Native operation5 frame/config/base constructor and optional upper deletion; auxiliary services virtual'
 r['limits']=[x for x in r['limits'] if 'constructoredea8' not in x and 'choose supplied4b0' not in x]
 r['native_callback_installation']={'constructor':'0xedea8','callback_offset':'0x4b0','callback':'0x10e9d0','type':22}
 r['limits'].append('Nativeedea8 installs callbacks/type from real10e8ac configuration; auxiliary field initializers mocked. For upper delete, active flag and manager records still supplied.')
if args.native_pool:
 assert n['word'](0x60015000+0x788)==0
 assert int.from_bytes(u.mem_read(0x60015000+0x380,2),'little')==0
 r['native_control_pool']={'capacity_fixture':1,'native_allocate':'0xe9300','native_return':'0x104810','count_after_delete':0,'active_or_pool_flags_manually_set':False}
 r['limits']=[x for x in r['limits'] if 'active flag and manager records still supplied' not in x]
 r['limits']=['Capacity1 and backing memory supplied; real startup pool capacity/backing allocation not established.', 'Native pool init/allocate/return, frame/config/base constructor and deletion dispatcher/destructor execute.', 'Manager getter, malloc/free/memcpy/memset, auxiliary field initializers,1334f8,base cleanupecfa4 and tree attachment remain virtual.', 'No manual active flags/counters/callbacks/types set for deletion in this mode; no physical drawing or device lifecycle qualification.']
if args.stop_operation:
 assert n['word'](0x6bae88+16)==0 and n['word'](0x6bae78)==0
 r['native_operation_stop']={'entry':'0xde3c0','operation':1,'owner_control_pointer_after':0,'operation_flag_after':0,'manual_delete_dispatch':False}
 r['limits'].append('Stop requested explicitly via native manager operation1; manager chooses existing operation5 object and deletes it. Actual recovery event triggering stop not established.')
if args.slot_lifecycle:
 r['limits']=[x for x in r['limits'] if 'Stop requested explicitly via native manager' not in x]
 assert n['word'](0x6001c010)==0
 r['native_slot_lifecycle']={'entry':'0x4e388','requests':[1,0,0],'slot_active_after':0,'native_create_to_stop':True}
 r['limits'].append('Original4e388 starts and stops native manager object through real slot helpers; owner+48 and initial zero slot object supplied. Caller requests still manually supplied, not actual GUI events.')
if args.exit_gui_state:
 assert list(u.mem_read(0x6001d000,2))==[1,23]
 r['native_state_exit']={'event':'0x20620','selected_action':'0x58ca0','actual_action_return':23,'before':[1,4],'after':[1,23],'exit_callback':'0x5ce30','stop_request_generated_natively':True}
 r['limits'].append('20620 event supplied; original action returns23, native exit5ce30 naturally invokes4e388(0) and releases control; event producer/meaning not yet established. Other queued events not consumed.')
Path(n['ROOT'],'sources/native-gui-state4-exit-lifecycle.json' if args.exit_gui_state else 'sources/native-gui-slot-lifecycle.json' if args.slot_lifecycle else 'sources/native-gui-operation5-stop.json' if args.stop_operation else 'sources/native-gui-operation5-pool.json' if args.native_pool else 'sources/native-gui-operation5-base.json' if args.native_base else 'sources/native-gui-operation5-upper-delete.json' if args.upper_delete else 'sources/native-gui-operation5-destroy.json' if args.native_destroy else 'sources/native-gui-operation5-config.json' if args.native_config else 'sources/native-gui-operation5.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))



