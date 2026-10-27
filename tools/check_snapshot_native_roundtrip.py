"""Original snapshot client -> original manager/native pool -> original client."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR
from evidence_checks import verify_report
from native_alarm_fixture import reply,create
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'sources/native-stop-event-consumer.json'
up=verify_report(ROOT,str(source.relative_to(ROOT)));payload=bytes.fromhex(up['snapshot_present_path']['payload_hex'])
base=ROOT/'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
u=m['u'];call=m['call'];g=call.__globals__;g['intercept_actions']=False;g['deactivate_probe']=False
packets=[];replies=[];pending_replies=[];details=[];state=1;calendar=200;manager_session=None
cleanup_probe=False;cleanup_gate=0;cleanup_count=1;cleanup_queries=[];cleanup_native_query=False;cleanup_native_gate=False;native_gate_calls=[]
def hook(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
    if cleanup_probe and cleanup_native_gate and pc==0x265800:
        native_gate_calls.append(struct.unpack('<I',uc.mem_read(a[0]+4,4))[0]);return
    if cleanup_probe and not cleanup_native_gate and pc==0xb06e0:
        uc.mem_write(a[0],struct.pack('<I',cleanup_gate));cleanup_queries.append({'service':'b06e0','value_fixture':cleanup_gate})
    elif cleanup_probe and not cleanup_native_query and pc==0xb0fb0:
        assert a[1]==1
        uc.mem_write(a[0],struct.pack('<I',10017));uc.mem_write(a[2],struct.pack('<I',cleanup_count))
        cleanup_queries.append({'service':'b0fb0','count_fixture':cleanup_count,'id_fixture':10017})
    elif cleanup_probe and pc in (0xb00bc,0xe5ac,0x33b918,0x33b83c):pass
    elif pc==0xd574:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);value=a[0]
    elif pc==0xd85c:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));value=a[0]
    elif pc==0x268c9c:
        packet=bytes(uc.mem_read(a[2],a[3]));operation=struct.unpack_from('<I',packet,12)[0]
        if operation==20:assert packet[20:]==payload
        else:assert (operation,len(packet)) in ((22,24),(27,20))
        packets.append(packet)
        response,detail=manager_session(packet,state,calendar) if manager_session else reply(ROOT,packet,state,calendar)
        replies.append(response);pending_replies.append(response);details.append(detail)
    elif pc==0x268d48:
        assert len(pending_replies)==1
        response=pending_replies.pop(0);assert a[2]==len(response)
        uc.mem_write(a[1],response);uc.mem_write(a[3],struct.pack('<I',len(response)))
    elif pc not in (0x337a80,0x337ae8):return
    uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[]
for state,calendar,expected in ((1,200,0),(1,50,0x102),(4,200,0x1d03)):
    client,buffer,output=0x60012000,0x60012200,0x60012300
    data=bytearray(44)
    for offset,value in ((0,1),(4,2),(12,55),(16,500),(20,10),(40,88)):struct.pack_into('<I',data,offset,value)
    u.mem_write(client,bytes(data));u.mem_write(buffer,payload);u.mem_write(output,struct.pack('<I',0xdeadbeef))
    packets.clear();replies.clear();details.clear()
    returned=call(0x266fd0,(client,buffer,output,0));assert returned==expected
    assert struct.unpack_from('<I',packets[0],4)[0]==10 and struct.unpack('<5I',replies[0])[:4]==(20,10,20,expected)
    assert struct.unpack('<I',u.mem_read(client+20,4))[0]==11
    result=struct.unpack('<I',u.mem_read(output,4))[0]
    assert result==(10001 if expected==0 else 0xdeadbeef)
    assert details[0]['used_slots']==int(expected==0)
    assert details[0]['persistence_captured']==(['/var/apfalarm.db'] if expected==0 else [])
    rows.append({'return':returned,'client_result':result,'request_hex':packets[0].hex(),
                 'reply_hex':replies[0].hex(),'manager':details[0]})
manager_session=create(ROOT);state=1;calendar=200;capacity_rows=[]
u.mem_write(client+20,struct.pack('<I',100))
for index in range(17):
    u.mem_write(output,struct.pack('<I',0xdeadbeef));packets.clear();replies.clear();details.clear()
    expected=0 if index<16 else 0x1d01
    assert call(0x266fd0,(client,buffer,output,0))==expected
    words=list(struct.unpack('<5I',replies[0]));assert words[:4]==[20,100+index,20,expected]
    assert struct.unpack('<I',u.mem_read(client+20,4))[0]==101+index
    result=struct.unpack('<I',u.mem_read(output,4))[0]
    assert result==(10001+index if index<16 else 0xdeadbeef)
    assert details[0]['used_slots']==min(index+1,16)
    assert len(details[0]['persistence_captured'])==int(index<16)
    capacity_rows.append({'request_sequence':100+index,'return':expected,'result':result,'manager':details[0]})
packets.clear();replies.clear();details.clear()
assert call(0x266cb4,(client,10008,0,0))==0
assert list(struct.unpack('<6I',packets[0]))==[24,117,1,22,55,10008]
assert list(struct.unpack('<4I',replies[0]))==[16,117,22,0]
assert details[0]['used_slots']==15 and details[0]['persistence_captured']==['/var/apfalarm.db']
cancel={'request_hex':packets[0].hex(),'reply_hex':replies[0].hex(),'manager':details[0]}
packets.clear();replies.clear();details.clear()
assert call(0x266fd0,(client,buffer,output,0))==0
assert struct.unpack('<I',u.mem_read(output,4))[0]==10017 and details[0]['used_slots']==16
after_cancel={'new_record_id':10017,'manager':details[0]}
u.mem_write(0x820f68,bytes(u.mem_read(client,44)));client=0x820f68
cleanup_probe=True;cleanup_rows=[];cleanup_object=0x60014000
for cleanup_gate,cleanup_count in ((0,1),(0,0),(1,1)):
    packets.clear();replies.clear();details.clear();cleanup_queries.clear()
    u.mem_write(cleanup_object+28,struct.pack('<I',10017))
    call(0xeea0,(cleanup_object,1,0,0))
    cancelled=cleanup_gate==0 and cleanup_count==1
    assert len(packets)==int(cancelled)
    remaining_marker=struct.unpack('<I',u.mem_read(cleanup_object+28,4))[0]
    assert remaining_marker==(0 if cancelled else 10017)
    if cancelled:
        assert list(struct.unpack('<6I',packets[0]))==[24,119,1,22,55,10017]
        assert details[0]['used_slots']==15
    cleanup_rows.append({'gate_fixture':cleanup_gate,'query_count_fixture':cleanup_count,
                         'queries':cleanup_queries.copy(),'request_hex':packets[0].hex() if packets else None,
                         'marker_after':remaining_marker,'manager':details[0] if details else None})
cleanup_native_query=True;cleanup_native_gate=True;cleanup_gate=0
packets.clear();replies.clear();details.clear();cleanup_queries.clear()
u.mem_write(cleanup_object+28,struct.pack('<I',10016))
call(0xeea0,(cleanup_object,1,0,0))
assert [struct.unpack_from('<I',p,12)[0] for p in packets]==[27,22]
query_words=list(struct.unpack('<21I',replies[0]));assert query_words[:6]==[84,120,27,0,15,10016]
assert list(struct.unpack('<6I',packets[1]))==[24,121,1,22,55,10016]
assert details[0]['used_slots']==15 and details[1]['used_slots']==14
assert struct.unpack('<I',u.mem_read(cleanup_object+28,4))[0]==0
assert native_gate_calls==[2]
native_query_cleanup={'query_reply_words':query_words,'cancel_request_hex':packets[1].hex(),
                       'manager_before_cancel':details[0],'manager_after_cancel':details[1],
                       'native_gate_client_states':native_gate_calls.copy(),'record_id_selected_by_original_query':10016}
u.mem_write(client+4,struct.pack('<I',1));u.mem_write(cleanup_object+28,struct.pack('<I',10016))
packets.clear();replies.clear();details.clear();native_gate_calls.clear()
call(0xeea0,(cleanup_object,1,0,0))
assert native_gate_calls==[1] and not packets
assert struct.unpack('<I',u.mem_read(cleanup_object+28,4))[0]==10016
inactive_gate={'client_state_fixture':1,'native_gate_client_states':native_gate_calls.copy(),
               'requests':len(packets),'marker_after':10016}
u.mem_write(client+4,struct.pack('<I',2))
main_context,notification=0x60015000,0x60016000
u.mem_write(0x682cd8,struct.pack('<I',main_context))
u.mem_write(main_context,bytes([3,4])+bytes(30))
u.mem_write(notification,struct.pack('<3I',10,10015,0))
packets.clear();replies.clear();details.clear();g['queued'].clear();native_gate_calls.clear()
call(0xf004,(notification,0,0,0))
assert [struct.unpack_from('<I',p,12)[0] for p in packets]==[27,22]
assert list(struct.unpack('<6I',packets[1]))==[24,123,1,22,55,10015]
assert details[1]['used_slots']==13 and native_gate_calls==[2]
assert g['queued']==[[0x420027,0,0,0]]
assert struct.unpack('<I',u.mem_read(0x613e2c+28,4))[0]==0
notification_cleanup={'callback':'0xf004','notification_words_fixture':[10,10015,0],
                      'main_mode_fixture':3,'query_reply_hex':replies[0].hex(),
                      'cancel_request_hex':packets[1].hex(),'manager_after':details[1],
                      'queued':[p.copy() for p in g['queued']],
                      'callback_invoked_by_harness':True}
u.mem_write(main_context,bytes([2,2])+bytes(30))
packets.clear();replies.clear();details.clear();g['queued'].clear()
call(0xf004,(notification,0,0,0));assert not packets and not g['queued']
notification_cleanup['mode2_negative_no_requests']=True
inputs=[Path(__file__),base,ROOT/'tools/native_alarm_fixture.py',source,ROOT/'work/targets-jp/SpiderApp',ROOT/'work/targets-jp/sysmgrd']
report={'all_bounded_checks_passed':True,'cases':rows,'same_manager_capacity_sequence':capacity_rows,
        'native_cancel_roundtrip':cancel,'allocation_after_cancel':after_cancel,
        'original_cleanup_eea0':cleanup_rows,
        'original_query_and_cleanup':native_query_cleanup,
        'original_inactive_gate':inactive_gate,
        'original_notification10_cleanup':notification_cleanup,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'limits':['Separate original-instruction emulators; request and reply bytes copied through virtual transport.',
                  'Native manager constructor/allocation/insertion execute; clocks/calendar/locks/persistence virtual.',
                  'Three gate/query fixture cases retained; final query+cleanup uses original local-state getter and remote query.',
                  'APF client states and caller event/scheduling still provided; no full automatic restore claim.',
                  'No real IPC, disk/device writes, Home-instance integration or hardware qualification.']}
(ROOT/'sources/native-snapshot-native-roundtrip.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original eea0 ->native op27 query selects record ->native op22 cancel; same-manager pool15 ->14')
