"""Original GUI command6 path, with virtual managers/backend storage and queue transport."""
from pathlib import Path
import argparse,hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--consume',action='store_true',help='Execute native57d50/12fd4 with subsystem-cleanup boundaries mocked.')
parser.add_argument('--complete',action='store_true',help='Register native pending tokens and consume420034 through71ee4/11250; PCS is virtual.')
parser.add_argument('--ack',action='store_true',help='Feed actual41000a into native main state/APF ack; reply/transport virtual.')
parser.add_argument('--reject-ack',action='store_true',help='Virtual APF reply rejects deactivation acknowledgement; requires --ack.')
parser.add_argument('--page-cleanup-loop',action='store_true',help='Execute original page cleanup coordinator and module-stop wrappers; individual subsystem cleanup remains virtual.')
parser.add_argument('--native-module-dispatch',action='store_true',help='Run native registry dispatcher and command adapter with one registered descriptor fixture.')
parser.add_argument('--skip-flagged-module',action='store_true',help='Use native registry mode1 and descriptor flag1 to exercise skip branch.')
parser.add_argument('--stock-module-registry',action='store_true',help='Run original registration and stock getters/converters, stopping each actual handler at a spy boundary.')
parser.add_argument('--stock-inactive-handlers',action='store_true',help='Execute stock handler state checks on initial inactive objects; assert inactive before cleanup branches.')
parser.add_argument('--active-parent-module0',action='store_true',help='Use one active stock UI module with parent/child fixture; execute its actual parent removal before APF ack.')
parser.add_argument('--resume-input',action='store_true',help='After native stop/ack, manually invoke original GUI resume callback; page rebuild stays virtual.')
args=parser.parse_args()
assert not args.complete or args.consume
assert not args.ack or args.complete
assert not args.reject_ack or args.ack
assert not args.page_cleanup_loop or args.consume
assert not args.native_module_dispatch or args.page_cleanup_loop
assert not args.skip_flagged_module or args.native_module_dispatch
assert not args.stock_module_registry or args.native_module_dispatch
assert not args.stock_inactive_handlers or args.stock_module_registry
assert not args.active_parent_module0 or (args.stock_inactive_handlers and not args.skip_flagged_module)
assert not args.resume_input or (args.consume and not args.reject_ack)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for gui_state,old_mode in ((0,0),(1,0),(1,1),(1,2)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x40000);u.mem_map(0x61000000,0x10000);u.mem_map(0x62000000,4096)
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 manager=0x60000000;module=0x613f00;result=0x61008000
 for p,v in ((module+0x5eb0,gui_state),(manager+0x29b98,old_mode),(manager+0x29b94,1),(0x4f7820,0x62000000),(0x62000298,777),(0x7dca00,17),(0x7dca04,0x63000000),(0x761120,29)):
  put(p,v)
 before_fb=bytes(u.mem_read(0x7dca00,0x78));before_touch=bytes(u.mem_read(0x76111c,16))
 queues=[];ioctls=[];forbidden=[];cleanup_boundaries=[];consuming=False;pcs_commands=[];ack_packets=[];page_stops=[];page_services=[];page_objects=[];module_calls=[];stock_handlers={};stock_dispatches=[];stock_gate_returns={};stock_gate_results=[];parent_remove_calls=[];parent_remove_results=[];resume_services=[]
 if args.native_module_dispatch and not args.stock_module_registry:
  registry=0xe601e0
  for mid in range(16):put(registry+4+mid*4,0)
  put(registry+4,0x61001000);put(registry+0x12f8,1);put(registry+0x1300,1 if args.skip_flagged_module else 0)
  for off,value in ((0,1 if args.skip_flagged_module else 0),(4,0x61002000),(0x10,0x61002004),(0x18,0x61002008)):put(0x61001000+off,value)
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  answer=0
  if consuming and args.active_parent_module0 and pc==0x112cc0:
   assert a[:3]==[0x61004000,0x61005000,0]
   parent_remove_calls.append({'count_before':word(0x61004044),'slot_before':hex(word(0x61004004))});return
  if consuming and args.active_parent_module0 and pc==0xbe5d0:
   parent_remove_results.append(a[0]);return
  if pc in (0x14a3f0,0x14b070,0xa6364):forbidden.append(hex(pc))
  if consuming and args.resume_input and pc==0x12ef8:
   assert a[0]==module and word(0x6bafb8)==0 and word(module+0x5f18)==7
   resume_services.append('page_rebuild_before_input_restore')
  elif args.stock_module_registry and pc==symbols['memset']:
   assert a[1:3]==[0,76] and 0xe601e0<=a[0] and a[0]+76<=0xe601e0+0x130c
   uc.mem_write(a[0],bytes(76));answer=a[0]
  elif consuming and args.stock_module_registry and pc in stock_handlers:
   mid,obj,converted=stock_handlers[pc]
   request=list(struct.unpack('<3I',uc.mem_read(a[1],12)))
   assert a[0]==obj and request==[mid,converted,0] and a[2:]==[0,0x61004000 if args.active_parent_module0 else 1]
   stock_dispatches.append({'module_id':mid,'object':hex(obj),'handler':hex(pc),'request_words':request})
   if args.stock_inactive_handlers:return
  elif consuming and args.stock_inactive_handlers and pc in stock_gate_returns:
   assert a[0]==int(args.active_parent_module0 and stock_gate_returns[pc]==0),(stock_gate_returns[pc],hex(pc),a[0])
   stock_gate_results.append({'module_id':stock_gate_returns[pc],'state_query_result':a[0]});return
  elif args.ack and pc==0x268c9c:
   if args.active_parent_module0:
    assert parent_remove_results==[0,10] and word(0x61004044)==0 and word(0x61004004)==0
   packet=list(struct.unpack('<6I',uc.mem_read(a[2],24)))
   assert a[:2]==[500,55] and a[3]==24 and packet==[24,0,1,1,55,1]
   ack_packets.append(packet)
  elif args.ack and pc==0x268d48:
   assert a[0]==500 and a[2]==16
   uc.mem_write(a[1],struct.pack('<4I',16,0,1,0x1d04 if args.reject_ack else 0));put(a[3],16)
  elif args.ack and pc in (0x337a80,0x337ae8,0xb00bc,0x265298,0x17c42c,0x33b918):pass
  elif consuming and args.page_cleanup_loop and pc==0x4c73c:
   cleanup_boundaries.append(hex(pc));page_objects.append(hex(a[0]));return
  elif consuming and args.page_cleanup_loop and pc in (0x2d938,0x12e74,0x14e94,0x4be78,0x4be9c,0x4bec0,0x4bee8,0x4bef0,0x4bf14,0x4bf44):
   page_services.append(hex(pc))
  elif consuming and args.page_cleanup_loop and pc==0xdeedc:
   assert a[0]==0xe601e0 and a[2:]==[0,0]
   page_stops.append(a[1])
   if args.native_module_dispatch:return
  elif consuming and args.native_module_dispatch and pc in (0x61002000,0x61002004,0x61002008):
   if pc==0x61002000:answer=0x61003000;module_calls.append('getter')
   elif pc==0x61002004:assert a[0]==0;module_calls.append('convert')
   else:
    assert a[0]==0x61003000 and list(struct.unpack('<3I',uc.mem_read(a[1],12)))==[0,0,0]
    assert a[2:]==[0,1];module_calls.append('handler')
  elif consuming and pc in (0x4c73c,0x48fe8,0x4a634,0xb4a34,0x14da0,0x119a0,0xb4b9c):
   cleanup_boundaries.append(hex(pc))
  elif args.complete and pc==0x1fd30:
   assert a[1]==6
   pcs_commands.append(a[1]);put(a[2],0)
  elif pc==0xe87f4:answer=manager
  elif pc==0xa57f0:queues.append(a)
  elif pc==symbols['ioctl']:
   assert a[:2]==[17,0x40044e0c]
   payload_words=list(struct.unpack('<2I',uc.mem_read(a[2],8)));assert payload_words==[1,0];ioctls.append({'request':hex(a[1]),'words':payload_words})
  elif pc in (0x116d4,0xff5c,0x33b83c,0x33c528,0x33d8c0):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 def invoke(pc,values):
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,0x6100e000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(pc,0x50000000,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000
  return u.reg_read(UC_ARM_REG_R0)
 if args.stock_module_registry:
  u.reg_write(UC_ARM_REG_SP,0x6100e000);u.emu_start(0x14d0c,0x14d40,count=100000)
  assert u.reg_read(UC_ARM_REG_PC)==0x14d40 and word(0xe601e0)==16
  for mid in range(16):
   descriptor=word(0xe601e0+4+mid*4);assert descriptor==0x4de800+mid*28
   obj=invoke(word(descriptor+4),(0,));converted=invoke(word(descriptor+0x10),(0,))
   handler=word(descriptor+0x18);stock_handlers[handler]=(mid,obj,converted)
   if args.stock_inactive_handlers:
    found=False
    for off in range(0,64,4):
     instruction=word(handler+off)
     if (instruction>>24)&15==11:
      stock_gate_returns[handler+off+4]=mid;found=True;break
    assert found
  put(0xe601e0+0x12f8,0x61004000 if args.active_parent_module0 else 1);put(0xe601e0+0x1300,1 if args.skip_flagged_module else 0)
  if args.active_parent_module0:
   obj0=stock_handlers[word(0x4de800+0x18)][1];put(obj0,1)
   for p,v in ((0x69c7cc+0x24,0x61005000),(0x61004000,0x61007000),(0x61004004,0x61005000),(0x61004044,1),
               (0x61005000+0x460,0x08000008),(0x61007000+0x460,0x10),(0x61005000+0x4c8,0x61006000),(0x61006000+0xae4,14)):put(p,v)
 for r,v in ((UC_ARM_REG_R0,module),(UC_ARM_REG_R1,6),(UC_ARM_REG_R2,result),(UC_ARM_REG_SP,0x6100e000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
 u.emu_start(0x143c0,0x50000000,count=30000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
 active=gui_state!=0
 assert queues==([[0x20111,0,0,0]] if active else [])
 assert word(result)==(0x206 if active else 0)
 assert word(manager+0x29b98)==(1 if active else old_mode)
 assert word(0x62000298)==(200000 if active and old_mode==0 else 777)
 assert bool(word(manager+4)&8)==bool(active and old_mode==0)
 assert word(0x671c40+0x1c)==(0x100 if active else 0)
 assert not forbidden and bytes(u.mem_read(0x7dca00,0x78))==before_fb and bytes(u.mem_read(0x76111c,16))==before_touch
 initial_queues=queues.copy()
 completion=[];pending_trace=[];main_after=None;client_after=None
 if args.complete and active:
  core=0x613e60;tracker=0x61009000
  put(core+4,6);put(core+8,0);put(core+0x2c,tracker);put(core+0x14,0x6100a000)
  assert invoke(0x48a14,(tracker,word(result)))==0
  if old_mode==1:assert invoke(0x48a14,(tracker,0x999))==0
  pending_trace.append(word(tracker))
 if args.consume and active:
  consuming=True;put(0x6bafb8,7)
  for r,v in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0x20111),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x6100e000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
  u.emu_start(0x57d50,0x50000000,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==2
  assert word(module+0x5eb0)==0 and word(module+0x5f18)==7 and word(0x6bafb8)==0
  assert cleanup_boundaries==['0x4c73c','0x4c73c','0x48fe8','0x4a634','0xb4a34','0x14da0','0x119a0','0xb4b9c']
  assert word(manager)==1 and word(manager+0x378)==20
  completion=queues[1:];assert completion==[[0x420034,0,0x206,0]]
  if args.complete:
   assert invoke(0x71ee4,(0,completion[0][0],completion[0][2],0))==0
   pending_trace.append(word(tracker))
   if old_mode==1:
    assert queues[2:]==[] and pcs_commands==[] and word(tracker)==1
    assert invoke(0x71ee4,(0,0x420034,0x999,0))==0
    pending_trace.append(word(tracker))
   assert word(tracker)==0 and pcs_commands==[6] and queues[2:]==[[0x41000a,0,0,0]]
   if args.ack:
    client=0x820f68;main_context=0x62000800
    for offset,value in ((0,1),(4,2),(12,55),(16,500)):put(client+offset,value)
    context=bytearray(32);context[0],context[1],context[13]=3,4,6
    struct.pack_into('<I',context,4,0x3ef680);u.mem_write(main_context,bytes(context))
    event=queues[-1]
    assert invoke(0x17c608,(main_context,event[0],event[2],event[3]))==0
    main_after=list(bytes(u.mem_read(main_context,2)));client_after=word(client+4)
    assert main_after==[2,2] and client_after==(2 if args.reject_ack else 1) and len(ack_packets)==1
 resume_result=None
 if args.resume_input and active:
  assert word(0x6bafb8)==0 and word(module+0x5f18)==7
  assert invoke(0x5cfb4,(0,))==0
  assert resume_services==['page_rebuild_before_input_restore']
  assert word(0x6bafb8)==7 and word(module+0x5f18)==7 and word(module+0x5eb0)==1
  resume_result={'entry':'0x5cfb4','restore_helper':'0x13e04','input_after_stop':0,'saved_value':7,'input_after_resume':7,'saved_value_after':7,'virtual_page_rebuild':resume_services}
 rows.append({'gui_state_fixture':gui_state,'old_manager_mode':old_mode,'manager_mode_after':word(manager+0x29b98),'backend_interval_raw_after':word(0x62000298),'manager_flag8_after':bool(word(manager+4)&8),'queued':initial_queues,'async_token':word(result),'ioctls':ioctls,'resource_cleanup_calls':forbidden,'fb_and_touch_records_unchanged_before_consumer':True,'mocked_consumer_cleanup_boundaries':cleanup_boundaries,'native_consumer_completion_events':completion,'native_pending_count_trace':pending_trace,'pcs_command_calls':pcs_commands,'coordinator_completion_events':queues[2:] if args.complete and active else [],'native_apf_ack_requests':ack_packets,'main_mode_state_after':main_after,'apf_client_state_after':client_after})
 rows[-1]['native_input_resume']=resume_result
 if args.page_cleanup_loop:
  assert len(page_objects)==(2 if active else 0)
  assert page_stops==([0,1,2,3,4,6,7,8,11,5,13,15,9]*2 if active else []),(gui_state,old_mode,page_stops,cleanup_boundaries)
  rows[-1].update({'native_page_module_stop_order':page_stops,'native_page_cleanup_object_args':page_objects,'mocked_page_resource_helpers':page_services})
  if args.native_module_dispatch:
   assert module_calls==([] if args.stock_module_registry else ['convert','getter','handler']*2 if active and not args.skip_flagged_module else [])
   rows[-1]['virtual_registered_module_services']=module_calls
  if args.stock_module_registry:
   order=[0,1,2,3,4,6,7,8,11,5,13,15,9]
   if args.skip_flagged_module:order.remove(1)
   assert [r['module_id'] for r in stock_dispatches]==(order*2 if active else [])
   rows[-1]['stock_descriptor_handler_boundaries']=stock_dispatches
   if args.stock_inactive_handlers:
    assert [r['module_id'] for r in stock_gate_results]==(order*2 if active else [])
    rows[-1]['native_handler_state_checks' if args.active_parent_module0 else 'native_inactive_handler_checks']=stock_gate_results
   if args.active_parent_module0:
    assert parent_remove_results==([0,10] if active else [])
    if active:assert word(0x61004044)==0 and word(0x61005000+0x460)==8 and word(0x61006000+0x460)==0x8000
    rows[-1].update({'active_parent_remove_calls':parent_remove_calls,'native_parent_remove_results':parent_remove_results,'parent_count_after':word(0x61004044),'parent_slot_after':hex(word(0x61004004))})
report={'input_sha256':digest,'entry':'0x143c0 command6','cases':rows,'limits':['GUI state, manager/backend pointer, old mode and resource records are fixtures; queue/logging/auxiliary service and ioctl are virtual.','Native module state getter, b586c/eae0c/e3854/e44a4 and input-mask497b4 execute. No cleanup occurs in these cases; not a global claim for every state.','Queued20111 consumer, async completion, APF acknowledgement and real display/touch ownership remain unresolved.']}
if args.consume:
 report['limits'].append('Native57d50/12fd4 execute with page/subsystem/manager cleanup boundaries mocked; input enable saved/cleared, completion420034 token206 emitted. Actual manager teardown and display release not executed in this variant.')
if args.complete:
 report['limits'].append('Pending tokens registered with native48a14 from command6 output; original71ee4/11250 remove them and command6 completion emits41000a only after tracker empties. Other-token completion is injected; PCS command response mocked. APF ack not executed here.')
if args.ack:
 report['limits']=[line.replace('APF ack not executed here.','APF ack is covered by the additional mode below.') for line in report['limits']]
 report['limits'].append('Actual native-produced41000a feeds original main dispatcher/ack and APF client state update. Initial main3/4 and client2 are fixtures; transport/reply and transition helpers are virtual. No real manager acknowledgement or hardware release proof.')
report['virtual_ack_reply_status']=(0x1d04 if args.reject_ack else 0) if args.ack else None
if args.page_cleanup_loop:
 report['limits'].append('Original4c73c page cleanup coordinator and14dfc/def44/df8c8 wrappers execute; module dispatch deedc and page resource helpers mocked. No actual module/video cleanup or hardware release proven.')
if args.native_module_dispatch:
 report['limits'][-1]='Original page coordinator/wrappers and registry dispatcher deedc/e0078 execute; only module0 descriptor registered as fixture, getter/parameter conversion/handler services virtual. Other unregistered ids skipped natively. Mode1+flag1 skips fixture. No actual module identity/video cleanup or hardware release proven.'
if args.stock_module_registry:
 report['limits'][-1]='Original16 descriptor registration, page coordinator, registry dispatch and stock getters/converters execute. Each original handler entry is a spy boundary; runtime gate/mode and GUI state supplied. No actual handler/object initialization or video/display cleanup qualification; mode1 skips stock flagged id1.'
if args.stock_inactive_handlers:
 report['limits'][-1]='Original stock handlers and first state-query calls execute on untouched initial module object storage; each query is asserted0 before further native inactive-return path. This proves inactive handling only; no active module initialization/cleanup, video/display ownership or hardware qualification. Other page helpers/IPC remain virtual.'
if args.active_parent_module0:
 report['limits'][-1]='Stock module0 activity and parent/child/root/descendant records supplied, other objects inactive. Native command6/page coordinator/registry/active handler/tree traversal remove parent record before native APF ack. Duplicate second helper removal returns10, no count underflow. Other page helpers/IPC/PCS/replies remain virtual; no actual object initialization/rendering/audio/video or hardware release qualification.'
report_name='native-gui-command6-ack-rejected.json' if args.reject_ack else 'native-gui-command6-ack.json' if args.ack else 'native-gui-command6-completion.json' if args.complete else 'native-gui-command6-consumer.json' if args.consume else 'native-gui-command6.json'
if args.page_cleanup_loop:report_name='native-gui-command6-page-coordinator-rejected.json' if args.reject_ack else 'native-gui-command6-page-coordinator.json'
if args.native_module_dispatch:report_name=('native-gui-command6-module-skip' if args.skip_flagged_module else 'native-gui-command6-module-dispatch')+('-rejected' if args.reject_ack else '')+'.json'
if args.stock_module_registry:report_name=('native-gui-command6-stock-module-skip' if args.skip_flagged_module else 'native-gui-command6-stock-modules')+('-rejected' if args.reject_ack else '')+'.json'
if args.stock_inactive_handlers:report_name=('native-gui-command6-stock-inactive-skip' if args.skip_flagged_module else 'native-gui-command6-stock-inactive')+('-rejected' if args.reject_ack else '')+'.json'
if args.active_parent_module0:report_name='native-gui-command6-active-parent'+('-rejected' if args.reject_ack else '')+'.json'
if args.resume_input:
 report_name='native-gui-command6-input-resume.json'
 report['limits'].append('After original stop/ack, resume callback5cfb4 is manually invoked, page rebuild12ef8 virtual. Native13e04 restores saved input value7 after rebuild boundary. This verifies software enable state, not activation-event origin or physical key/touch ownership.')
(ROOT/'sources'/report_name).write_text(json.dumps(report,indent=2)+'\n')
print('Four native GUI command6 cases verified' + ('; native completion -> main/APF ack, virtual reply rejected' if args.reject_ack else '; native completion -> main/APF ack, virtual reply accepted' if args.ack else '; native consumer calls cleanup boundaries then emits completion206 (cleanup mocked)' if args.consume else '; initial branch only, before queued consumer'))
