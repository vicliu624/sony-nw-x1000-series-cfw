"""Execute original GUI receiver envelope conversion; no hardware or queue pump."""
import runpy,struct,json,argparse
parser=argparse.ArgumentParser();parser.add_argument("--native-bookkeeping",action="store_true");parser.add_argument("--native-insertion",action="store_true");parser.add_argument("--native-gui-callback",action="store_true");parser.add_argument("--native-default-handler",action="store_true");parser.add_argument("--native-child-delegate",action="store_true");args=parser.parse_args();assert not args.native_child_delegate or args.native_default_handler;assert not args.native_default_handler or args.native_gui_callback;assert not args.native_insertion or args.native_bookkeeping
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')))
u=n['u'];receiver=0x732d3c;packet=0x60010000;context=0x6dfa18;seen=[];services=[];control_calls=[];default_handler_calls=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v))
def hook(uc,pc,size,data):
 if pc not in (0xd574,0xd85c,0x106c40,0xe9690,0xe1e0,0xfa0f8,0x115f58,0xef1a0,0xecd6c,0xef5dc):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
 if pc in (0xecd6c,0xef5dc):
  default_handler_calls.append(hex(pc));return
 if pc==0xef1a0:
  if args.native_gui_callback:control_calls.append(hex(a[0]))
  return
 if pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2])
 elif pc==0xd85c:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])))
 elif pc in (0xfa0f8,0x115f58):
  services.append({"pc":hex(pc),"virtual":True});uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 elif pc==0xe1e0:
  left=bytes(u.mem_read(a[0],a[2]));right=bytes(u.mem_read(a[1],a[2]));uc.reg_write(UC_ARM_REG_R0,0 if left==right else 1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 elif pc==0x106c40:
  if args.native_bookkeeping:return
  services.append({'pc':hex(pc),'virtual':True})
 else:
  assert a[0]==context
  raw=bytes(u.mem_read(a[1],676));seen.append(raw)
  if args.native_gui_callback:return
 uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
put(receiver+0x46c,0xe9690);put(receiver+0x478,context)
raw=bytearray(424);raw[:60]=bytes(range(60));struct.pack_into('<I',raw,60,0x1234);struct.pack_into('<I',raw,72,3)
if args.native_gui_callback:
 control=0x60012000
 n['call'](0xeba18,(context+8,0,0,0));n['call'](0xeba80,(context+8,0,0,0))
 put(context+0x370,control);put(context+0x378,2);put(context+0x37c,1)
 put(control+0x460,9);put(control+0x4a0,0xecd6c if args.native_default_handler else 0)
 struct.pack_into('<I',raw,60,control)
 if args.native_child_delegate:
  child=0x60014000;put(child+0x460,9);put(child+0x4a0,0xecd6c)
  n['call'](0xed130,(control,child,0,0))
  assert n['word'](control+0x4c8)==child and n['word'](child+0x4c4)==control
  assert n['word'](child+0x460)&8==0
u.mem_write(packet,bytes(raw))
assert n['call'](0x104c20,(receiver,packet,0,0))==0
assert len(seen)==1 and struct.unpack_from('<I',seen[0],4)[0]==4
assert seen[0][88:148]==raw[:60]
if args.native_bookkeeping:
 queue=0x733208
 put(0x60008000,0x200000)
 n['call'](0x105fb8,(queue,228,28,0x700000))
 struct.pack_into('<I',raw,56,0x100);u.mem_write(packet,bytes(raw))
 record=queue+228*424
 if args.native_insertion:
  payload=0x60011000;u.mem_write(payload,bytes(352));put(payload,1)
  assert n['call'](0x106544,(queue,packet,payload,0))==0
  assert n['word'](record+412)&1 and n['word'](queue+0x1b010)==1
  assert bytes(u.mem_read(record,60))==raw[:60]
 else:
  u.mem_write(record,bytes(raw));put(record+412,1);put(record+420,64)
  put(queue+0x1b010,1);put(queue+0x1b020,64)
 assert n['call'](0x104c20,(receiver,packet,0,0))==0
 assert n['word'](record+412)&1==0 and n['word'](record+420)==0
 assert n['word'](queue+0x1b010)==0 and n['word'](queue+0x1b020)==0
 assert n['call'](0x104c20,(receiver,packet,0,0))==0
 assert n['word'](queue+0x1b010)==0 and n['word'](queue+0x1b020)==0
 assert len(seen)==3
r={'native_bookkeeping':args.native_bookkeeping,'SpiderApp_sha256' :n['digest'],'scope':'Original receiver104c20 type3 envelope conversion and indirect callback; callback body/queue bookkeeping virtual','receiver_event_type':3,'gui_packet_type':4,'payload_prefix_preserved_bytes':60,'services':services,'limits':['Envelope supplied by harness, not received from an OS queue.','106c40 bookkeeping and e9690 body virtual.','This is a different path from template direct GUI packet types3/2; do not wrap those packets in this envelope.','No physical rendering, event loop or hardware qualification.']}
if args.native_bookkeeping:
 r['scope']='Original receiver conversion, queue match/removal and indirect callback; callback body virtual'
 r['checks']=['supplied class1 record228 matches','valid bit cleared','record bytes64 reset','class1 count/bytes return0','duplicate delivery does not underflow']
 r['limits']=['Queue initialized by original105fb8; occupied record and counters supplied, not enqueued.', 'Class1 flag0x100 path only; payload release for class0 unqualified.', 'memcmp/memcpy services and GUI callback body virtual; no OS queue pump or physical rendering.']
if args.native_insertion:
 r['scope']='Original queue insertion106544 followed by receiver match/removal; payload type1'
 r['checks']=['native initialization','native insertion sets valid bit and count1','receiver removes matching native record','duplicate does not underflow']
 r['limits']=['Header/payload supplied to insertion function; no OS thread/queue pumping.', 'Payload type1 only, no image allocation/free coverage.', 'Hash/time services fa0f8/115f58 virtual, memory services virtual, GUI callback body intercepted.']
if args.native_gui_callback:
 assert control_calls==(['0x60012000','0x60014000'] if args.native_child_delegate else ['0x60012000'])*len(seen),control_calls
 r['scope']='Original receiver invokes e9690, which selects supplied target control and native ef1a0 null-handler fallback'
 r['control_calls']=control_calls
 r['limits']=['Control backing/flags and null handler supplied; no populated widget callback or rendering.', 'Queue insertion mode runs separately in same harness when requested.', 'Memory/hash/time services virtual; no real OS queue/thread execution.']
if args.native_default_handler:
 assert default_handler_calls==['0xecd6c','0xef5dc']*len(seen)*(2 if args.native_child_delegate else 1),default_handler_calls
 r['scope']='Original receiver/control dispatch executes stock default handler ecd6c and delegation ef5dc'
 r['default_handler_calls']=default_handler_calls
 r['limits']=['Default callback pointer supplied from edea8 fallback literal ee34c; original full control construction not executed here.', 'Delegate child and procedure fields are zero; no widget business handler or painting executed.', 'Memory/hash/time services virtual, no OS event loop or hardware qualification.']
if args.native_child_delegate:
 n['call'](0xed180,(control,child,0,0))
 assert n['word'](control+0x4c8)==0 and n['word'](child+0x460)&8
 r['native_detach_verified']=True
 r['scope']='Original ed130 child attachment followed by receiver/default-handler delegation to child'
 r['control_calls']=control_calls
 r['limits']=['Parent/child backing and default callback pointers supplied; full widget constructors not executed.', 'Original attachment writes child/backlink and clears direct-dispatch bit8; receiver reaches both original default handlers.', 'Leaf delegate empty; no application-specific handler, rendering or OS event loop. Memory/hash/time services virtual.']
Path(n['ROOT'],'sources/native-gui-receiver-child-delegate.json' if args.native_child_delegate else 'sources/native-gui-receiver-default-handler.json' if args.native_default_handler else 'sources/native-gui-receiver-control.json' if args.native_gui_callback else 'sources/native-gui-receiver-insertion.json' if args.native_insertion else 'sources/native-gui-receiver-bookkeeping.json' if args.native_bookkeeping else 'sources/native-gui-receiver-envelope.json').write_text(json.dumps(r,indent=2)+'\n')
print('Original receiver converts envelope3 to GUI4 and invokes registered callback')
