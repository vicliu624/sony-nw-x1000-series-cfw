"""Locate stock430113 consumer without claiming selected actions executed."""
from pathlib import Path
import contextlib, hashlib, io, json, runpy, struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
if not __debug__: raise RuntimeError('Run without Python optimization')
ROOT = Path(__file__).resolve().parents[1]
base = ROOT/'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()): m=runpy.run_path(str(base))
call=m['call'];g=call.__globals__;u=g['u']
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
d=0x3f438c
count=struct.unpack('<H',u.mem_read(d+4,2))[0]
g['handlers'].update(word(word(d+12)+4*i) for i in range(count))
g['intercept_actions']=True
rows=[]
for state in range(1,8):
    x=bytearray(32);x[0]=1;x[1]=state;x[13]=5
    struct.pack_into('<I',x,4,0x3f4388)
    u.mem_write(0x60010000,bytes(x));g['hits'].clear()
    result=call(0x17c608,(0x60010000,0x430113,6,0))
    assert result==0 and len(g['hits'])==1
    rows.append({'state_fixture':state,'action':hex(g['hits'][0])})
def libc(uc,pc,size,data):
    if pc!=0xd574:return
    address=uc.reg_read(UC_ARM_REG_R0);value=uc.reg_read(UC_ARM_REG_R1)&255
    uc.mem_write(address,bytes([value])*uc.reg_read(UC_ARM_REG_R2))
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
handle=u.hook_add(UC_HOOK_CODE,libc)
g['intercept_actions']=False;g['deactivate_probe']=False
# Original e5f4/f6c0 read this supplied mode field. Mode2 avoids the
# unimplemented snapshot service; do not interpret it as a named power mode.
u.mem_write(0x613e2c+32,struct.pack('<I',2));g['queued'].clear()
x=bytearray(32);x[0]=1;x[1]=1;x[13]=11
struct.pack_into('<I',x,4,0x3f4388);u.mem_write(0x60010000,bytes(x))
assert call(0x17c608,(0x60010000,0x430113,6,0))==0
assert g['queued']==[[0x420032,0,0x683348,0]]
snapshot=bytes(u.mem_read(0x683348,108));assert snapshot==bytes(108)
forwarded=g['queued'][0].copy()
g['intercept_actions']=True;g['hits'].clear()
x=bytearray(32);x[0]=2;x[1]=1;x[13]=5
struct.pack_into('<I',x,4,0x3f4f18);u.mem_write(0x60011000,bytes(x))
assert call(0x17c608,(0x60011000,forwarded[0],forwarded[2],forwarded[3]))==0
assert len(g['hits'])==1
body={'state_field_plus32_fixture':2,'consumer_action':'0x6ed0c',
      'queued':forwarded,'payload_bytes':108,'payload_hex':snapshot.hex(),
      'next_root_action_selected_not_executed':hex(g['hits'][0]),
      'memset_virtual':True,'snapshot_service_bypassed_by_original_branch':True}
# Actual queued bytes connect the three original dispatches. Root is not
# re-created between its stop event and the returned420032 notification.
g['intercept_actions']=False;g['deactivate_probe']=False
root=bytearray(32);root[0]=2;root[1]=1;root[13]=5
struct.pack_into('<I',root,4,0x3f4f18);u.mem_write(0x60011000,bytes(root))
consumer=bytearray(32);consumer[0]=1;consumer[1]=1;consumer[13]=11
struct.pack_into('<I',consumer,4,0x3f4388);u.mem_write(0x60010000,bytes(consumer))
g['queued'].clear()
assert call(0x17c608,(0x60011000,0x420024,0,0))==0
stop_packet=g['queued'].copy();assert stop_packet==[[0x430113,0,6,0]]
assert word(0x613e60+4)==6
g['queued'].clear();p=stop_packet[0]
assert call(0x17c608,(0x60010000,p[0],p[2],p[3]))==0
return_packet=g['queued'].copy();assert return_packet==[[0x420032,0,0x683348,0]]
g['deactivate_probe']=True;g['deactivate_commands'].clear();p=return_packet[0]
assert call(0x17c608,(0x60011000,p[0],p[2],p[3]))==0
assert g['deactivate_commands']==[[0x613e60,6]]
assert list(u.mem_read(0x60011000,2))==[2,1]
continuous={'root_context':'0x60011000','root_not_recreated':True,
            'stop_packet':stop_packet,'return_packet':return_packet,
            'coordinator_calls':g['deactivate_commands'].copy(),
            'coordinator_intercepted':True,'snapshot_service_bypassed':True}
snapshot_calls=[];converted_times=[];saved_payloads=[]
def snapshot_services(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    if pc==0x17e28c:
        record=bytearray(384);struct.pack_into('<4I',record,104,1000,0,123,456)
        uc.mem_write(a[0],bytes(record))
    elif pc==0x33c528:uc.mem_write(a[0],struct.pack('<2I',1100,0))
    elif pc==0x33c610:
        converted_times.append(list(struct.unpack('<2I',uc.mem_read(a[0],8))))
        uc.mem_write(a[1],struct.pack('<7I',11,22,3,4,5,106,6))
    elif pc==0xb06e0:uc.mem_write(a[0],bytes(4))
    elif pc==0xb0850:saved_payloads.append(bytes(uc.mem_read(a[0],108)).hex())
    else:return
    snapshot_calls.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
snapshot_handle=u.hook_add(UC_HOOK_CODE,snapshot_services)
g['deactivate_probe']=False;g['queued'].clear()
u.mem_write(0x613e2c+32,bytes(4))
assert call(0x17c608,(0x60010000,0x430113,6,0))==0
assert g['queued']==[[0x420032,0,0x683348,0]]
assert converted_times==[[985,0]]
present_payload=bytes(u.mem_read(0x683348,108))
assert struct.unpack_from('<I',present_payload,36)[0]==1
g['deactivate_probe']=True;g['deactivate_commands'].clear()
p=g['queued'][0]
assert call(0x17c608,(0x60011000,p[0],p[2],p[3]))==0
assert saved_payloads==[present_payload.hex()]
assert g['deactivate_commands']==[[0x613e60,6]]
snapshot_case={'state_field_plus32_fixture':0,'original_snapshot_serializer_executed':True,
               'source_timestamp_fixture':[1000,0],'converted_timestamp':converted_times,
               'payload_hex':present_payload.hex(),'virtual_service_calls':snapshot_calls,
               'backend_payload_captured_not_written':saved_payloads,
               'coordinator_calls':g['deactivate_commands'].copy()}
u.hook_del(snapshot_handle)
u.hook_del(handle)
inputs=[Path(__file__),base,ROOT/'work/targets-jp/SpiderApp']
report={'all_bounded_checks_passed':True,'event':'0x430113',
        'descriptor_table':'0x3f4388','mode_fixture':1,'cases':rows,
        'bounded_action_body':body,
        'continuous_stop_path':continuous,
        'snapshot_present_path':snapshot_case,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits':['Seven contexts supplied; matrix actions intercepted. One state1/mode-field2 body executes.',
                  'Independent next-action selection intercepted; continuous case executes71f00 to intercepted coordinator6.',
                  'Mode-field0 snapshot serializer executes with virtual record/time/calendar/backend services; no real state write.',
                  'Main table3ef680 is not this consumer.',
                  'No full event routing, IPC or hardware qualification.']}
(ROOT/'sources/native-stop-event-consumer.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'cases':rows,'next_root_action':body['next_root_action_selected_not_executed']}))
