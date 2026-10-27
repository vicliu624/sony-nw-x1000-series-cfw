"""Capture original SpiderApp APF registration request; stop at transport send."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,runpy,struct,sys
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'tools/check_spider_restore_dispatch.py'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reply-report');parser.add_argument('--receive-registration-events',action='store_true');parser.add_argument('--native-event-lookup',action='store_true');parser.add_argument('--registered-manager-lookup',action='store_true');parser.add_argument('--native-event-services',action='store_true');parser.add_argument('--dispatch-root-events',action='store_true');parser.add_argument('--execute-coordinator',action='store_true');parser.add_argument('--native-gui-submit',action='store_true');parser.add_argument('--consume-gui-queue',action='store_true');parser.add_argument('--run-gui-worker',action='store_true');parser.add_argument('--complete-gui-token',action='store_true');parser.add_argument('--acknowledge-activation',action='store_true');parser.add_argument('--first-start-queries',action='store_true');parser.add_argument('--first-start-usb-state',type=int,choices=range(5),default=0);options=parser.parse_args()
if options.first_start_queries:options.acknowledge_activation=True
if options.acknowledge_activation:options.complete_gui_token=True
if options.complete_gui_token:options.run_gui_worker=True
if options.run_gui_worker:options.consume_gui_queue=True
if options.consume_gui_queue:options.native_gui_submit=True
if options.native_gui_submit:options.execute_coordinator=True
if options.execute_coordinator:options.dispatch_root_events=True
if options.dispatch_root_events:options.native_event_services=True
if options.native_event_services:options.registered_manager_lookup=True
if options.registered_manager_lookup:options.native_event_lookup=True
if options.native_event_lookup:options.receive_registration_events=True
if options.receive_registration_events:assert options.reply_report
reply_source=None
if options.reply_report:
    from evidence_checks import verify_report
    reply_source=(ROOT/options.reply_report).resolve();assert reply_source.is_relative_to(ROOT/'sources')
    reply_report=verify_report(ROOT,options.reply_report)
    reply=struct.pack('<5I',*reply_report['registration_reply'])
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
u=m['u'];call=m['call'];ctx=0x820f68;opened=[];requests=[];threads=[];received=[];event_phase=False;event_received=[];event_callbacks=[];event_finished=False;recent=[];name_queries=[];lookup_requests=[];lookup_reply=None;query_trace=[];lookup_session={};service_requests=[];root_initializing=False;root_dispatching=False;root_commands=[];module_calls=[];gui_submit_events=[];gui_service_calls=[];gui_result_slot=None;gui_token_results=[];gui_dispatch=[];gui_restore_trace=[];gui_worker_threads=[];gui_worker_services=[];gui_worker_native=[];coordinator_completion_calls=[];pcs_calls=[];activation_acks=[]

coordinator_modules=[(0x16b74,0xc),(0x143c0,0x10),(0xf32c,0x18),(0x3b498,0x1c),(0x37f08,0x20),(0x49d6c,0x38),(0x4492c,0x28),(0x499f8,0x34),(0x4f3dc,0x40)]

registration_model=None
if options.registered_manager_lookup:
    assert options.reply_report=='sources/native-home-ipc-client-registration.json'
    previous_argv=sys.argv
    try:
        sys.argv=['tools/check_home_ipc_registration.py','--client-request-report','sources/native-home-client-registration-request.json']
        with contextlib.redirect_stdout(io.StringIO()):registration_model=runpy.run_path(str(ROOT/'tools/check_home_ipc_registration.py'))
    finally:sys.argv=previous_argv
    manager=registration_model['u'];manager.hook_del(registration_model['manager_hook_id'])
    table=struct.unpack('<I',manager.mem_read(0x60000004,4))[0]
    config_bytes=(ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf').read_bytes()
    lookup_session.update({'emulator':manager,'core':0x60000000,'table':table,'queries':0,'config_sha256':hashlib.sha256(config_bytes).hexdigest(),'request_address':0x6001b000})
    registration_preserved={address:bytes(manager.mem_read(address,length)) for address,length in ((0x60006000,0x1b4),(0x60010000,256))}

def hook(uc,pc,size,data):
    global event_finished,lookup_reply,gui_result_slot
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    recent.append(hex(pc))
    if len(recent)>30:recent.pop(0)
    if event_phase and pc in (0xb0800,0x2664d0,0x268c9c,0xd574,0x339720):query_trace.append([hex(pc),[hex(v) for v in a]])
    result=0
    if options.dispatch_root_events and root_dispatching and pc==0x112fc:
        root_commands.append(a)
        if not options.execute_coordinator:uc.emu_stop()
        return
    if options.execute_coordinator and root_dispatching and pc in {entry for entry,offset in coordinator_modules}:
        assert a[1]==7
        if options.native_gui_submit and pc==0x143c0:
            assert a[0]==0x613f00;gui_result_slot=a[2]
            module_calls.append({'entry':hex(pc),'context':hex(a[0]),'command':a[1],'native_body_executed':True});return
        token=0x207 if pc==0x143c0 else 0
        module_calls.append({'entry':hex(pc),'context':hex(a[0]),'command':a[1],'token_fixture':token})
        uc.mem_write(a[2],struct.pack('<I',token));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.native_gui_submit and root_dispatching and pc==0x113a4:
        assert gui_result_slot is not None;gui_token_results.append(struct.unpack('<I',uc.mem_read(gui_result_slot,4))[0]);return
    if options.native_gui_submit and root_dispatching and pc==0x11f68:
        assert a[0]==0x613f00
        gui_submit_events.append(list(struct.unpack('<4I',uc.mem_read(a[1],16))))
        if options.consume_gui_queue:return
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.consume_gui_queue and root_dispatching and pc==0x17c608 and a[0]==0x60017000:
        assert a[1] in ((0x20110,0x20303,0x20670,0x20671) if options.run_gui_worker else (0x20110,));gui_dispatch.append(a);return
    if options.complete_gui_token and root_dispatching and pc==0x1fd30:
        assert a[:2]==[0x60015140,7];pcs_calls.append(a)
        uc.mem_write(a[2],struct.pack('<I',0));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.complete_gui_token and root_dispatching and pc in (0x10e68,0x140b4):
        coordinator_completion_calls.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.run_gui_worker and root_dispatching and pc==0x337534:
        assert a==[0x13f38,0x613efc,8,0x18000]
        assert struct.unpack('<I',uc.mem_read(a[1],4))[0]==0x207
        from unicorn.arm_const import UC_ARM_REG_SP
        output=struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0]
        uc.mem_write(output,struct.pack('<I',5678));gui_worker_threads.append(a)
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.run_gui_worker and root_dispatching and pc in (0x13f38,0x11a04):gui_worker_native.append(hex(pc));return
    if options.run_gui_worker and root_dispatching and pc in (0x4e388,0x3ce08,0x3d6dc,0xb4964,0xb4a54,0xb52dc):
        gui_worker_services.append({'entry':hex(pc),'args':a})
        if pc==0xb4964:assert a[1]==0x117fc
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.consume_gui_queue and root_dispatching and pc in (0x5cfb4,0x13e04):
        gui_restore_trace.append({'entry':hex(pc),'original_body_executed':True});return
    if options.consume_gui_queue and root_dispatching and pc==0x12ef8:
        assert struct.unpack('<I',uc.mem_read(0x613f00+0x5eb0,4))[0]==1
        gui_restore_trace.append({'entry':'0x12ef8','original_body_executed':False,'page_rebuild_deferred':True})
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.native_gui_submit and root_dispatching and pc in (0xb586c,0x51828,0x496b8,0x49984,0x497b4,0xb4a10):
        gui_service_calls.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.execute_coordinator and root_dispatching and pc in (0xff5c,0x116d4,0x33b83c,0x17c42c):
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if options.dispatch_root_events and root_initializing:
        if pc not in (0x17c42c,0x33b918):return
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if event_phase and pc==0xeaa0:event_callbacks.append('0xeaa0');return
    if event_phase and not options.native_event_lookup and pc==0xb0800:
        name=bytes(uc.mem_read(a[0],64)).split(b'\0',1)[0].decode()
        config=(ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf').read_text()
        entry=next(line.split() for line in config.splitlines() if line.strip() and not line.lstrip().startswith('#') and line.split()[-1]==name)
        app_id=int(entry[0],16);name_queries.append({'name':name,'id_fixture':app_id})
        uc.mem_write(a[1],struct.pack('<I',app_id));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if event_phase and options.native_event_lookup and pc==0xd574:
        assert a[2]<=0x10000;uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
    elif event_phase and options.native_event_lookup and pc==0x339720:
        value=bytes(uc.mem_read(a[2],256)).split(b'\0',1)[0];assert len(value)<a[1]
        uc.mem_write(a[0],value+b'\0');result=0
    elif event_phase and options.native_event_services and pc==0xd85c:
        uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
    elif event_phase and options.acknowledge_activation and pc==0x268c9c and a[3]==24:
        assert a[:2]==[500,55]
        packet=bytes(uc.mem_read(a[2],24));assert list(struct.unpack('<6I',packet))==[24,5,1,1,864,2]
        state_at_send=struct.unpack('<I',uc.mem_read(ctx+4,4))[0]
        from native_lookup_fixture import request_in_session
        details={};lookup_reply,comparisons=request_in_session(lookup_session,packet,details=details)
        activation_acks.append({'request_words':list(struct.unpack('<6I',packet)),'reply_words':list(struct.unpack('<4I',lookup_reply)),'client_state_at_send':state_at_send,'manager':details})
    elif event_phase and options.native_event_services and pc==0x268c9c and a[3]==20:
        assert a[:2]==[500,55]
        packet=bytes(uc.mem_read(a[2],20));header=list(struct.unpack('<5I',packet));operation=header[3]
        assert operation in ((35,7,8) if options.first_start_queries else (35,7)) and header==[20,3+len(service_requests)+len(activation_acks),1,operation,864]
        from native_lookup_fixture import request_in_session
        details={};lookup_reply,comparisons=request_in_session(lookup_session,packet,details=details)
        service_requests.append({'operation':operation,'request_hex':packet.hex(),'reply_hex':lookup_reply.hex(),'manager':details})
    elif event_phase and options.native_event_lookup and pc==0x268c9c:
        assert a[:2]==[500,55] and a[3]==276
        packet=bytes(uc.mem_read(a[2],276));header=list(struct.unpack('<5I',packet[:20]))
        assert header==[276,1+len(lookup_requests),1,36,864]
        from native_lookup_fixture import lookup,lookup_in_session
        details={}
        if lookup_session:lookup_reply,comparisons=lookup_in_session(lookup_session,packet,details=details)
        else:lookup_reply,comparisons=lookup(ROOT,packet,session=lookup_session,config_bytes=(ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf').read_bytes(),details=details)
        lookup_requests.append({'packet_hex':packet.hex(),'reply_hex':lookup_reply.hex(),'name':packet[20:].split(b'\0',1)[0].decode(),'parser':details,'comparisons':comparisons})
    elif event_phase and options.native_event_lookup and pc==0x268d48 and a[0]==500:
        assert lookup_reply is not None and a[2]==len(lookup_reply)
        uc.mem_write(a[1],lookup_reply);uc.mem_write(a[3],struct.pack('<I',len(lookup_reply)));lookup_reply=None
    elif event_phase and not options.native_event_services and pc in (0xb07e8,0xb0bdc):uc.mem_write(a[0],bytes(0x488 if pc==0xb07e8 else 4))
    elif event_phase and not options.dispatch_root_events and pc==0xe5f4:result=0x60014000
    elif event_phase and pc in (0xe5ac,0x3b2b8,0x33b918,0xb00bc,0x265298):pass
    elif event_phase and not options.dispatch_root_events and pc==0xe600:pass
    elif event_phase and pc==0x268d48:
        assert a[0]==501 and a[2]==256
        if not pending_frames:event_finished=True;uc.emu_stop();return
        frame=pending_frames.pop(0);uc.mem_write(a[1],frame);uc.mem_write(a[3],struct.pack('<I',len(frame)));event_received.append(frame.hex())
    elif pc==0xda84:result=432
    elif pc==0x337960:uc.mem_write(a[0],struct.pack('<I',88))
    elif pc==0x268c34:
        opened.append(a[1]);uc.mem_write(a[0],struct.pack('<I',499+len(opened)))
    elif pc==0x268c9c:
        assert a[:2]==[500,55] and a[3]==32
        requests.append(bytes(uc.mem_read(a[2],a[3])))
        if not reply_source:uc.emu_stop();return
        assert list(struct.unpack('<8I',requests[-1]))==reply_report['registration_request_fixture']
    elif reply_source and pc==0x268d48:
        assert a[0]==500 and a[2]==20 and not received
        uc.mem_write(a[1],reply);uc.mem_write(a[3],struct.pack('<I',len(reply)));received.append(reply.hex())
    elif reply_source and pc==0x337534:
        assert a[:3]==[0x26551c,ctx,8] and a[3]==0x4000
        from unicorn.arm_const import UC_ARM_REG_SP
        output=struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0]
        uc.mem_write(output,struct.pack('<I',1234));threads.append({'entry':'0x26551c','context':hex(ctx),'priority':a[2],'stack_bytes':a[3]})
    elif pc not in (0x337a80,0x337ae8):return
    uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
original_call=call
def call(entry,arguments):
    try:return original_call(entry,arguments)
    except Exception:
        (ROOT/'work/home-registration-call-gap.json').write_text(json.dumps({'entry':hex(entry),'pc':hex(u.reg_read(UC_ARM_REG_PC)),'r0_r3':[hex(u.reg_read(r)) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)],'recent':recent,'scope':'Offline model failure; no device access'},indent=2)+'\n');raise
if options.dispatch_root_events:
    m['call'].__globals__['intercept_actions']=False;m['call'].__globals__['deactivate_probe']=False
    root_initializing=True;assert call(0x714c4,(0,))==0
    assert list(u.mem_read(0x6833dc,2))==[1,1]
    u.mem_write(0x613e60+0x4c,bytes(24));u.mem_write(0x613e2c+4,struct.pack('<I',1))
    for slot in range(6):assert call(0x17c608,(0x6833dc,0x420102,slot,0))==0
    assert list(u.mem_read(0x6833dc,2))==[2,1]
    root_initializing=False
assert call(0x2652e0,(ctx,))==0
if options.receive_registration_events:
    from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_R7
    u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_R7,0x60010000)
    u.emu_start(0xfcb4,0xfd68,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0xfd68
    assert struct.unpack('<I',u.mem_read(ctx+0x2c+5*4,4))[0]==0xeaa0
# Same call setup, but send intentionally stops before original function return.
from unicorn.arm_const import UC_ARM_REG_SP
u.reg_write(UC_ARM_REG_R0,ctx);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
u.emu_start(0x2687c8,0x50000000,count=30000)
assert u.reg_read(UC_ARM_REG_PC)==(0x50000000 if reply_source else 0x268c9c) and len(requests)==1 and opened==[864,865]
if reply_source:
    assert u.reg_read(UC_ARM_REG_R0)==0 and len(received)==len(threads)==1
    assert list(struct.unpack('<2I',u.mem_read(ctx,8)))==[1,1]
    assert struct.unpack('<I',u.mem_read(ctx+36,4))[0]==1
words=list(struct.unpack('<8I',requests[0]));assert words==[32,0,0,0,864,865,432,0x10010001]
assert struct.unpack('<I',u.mem_read(ctx+20,4))[0]==1
if options.receive_registration_events:
    event_phase=True;pending_frames=[bytes.fromhex(frame) for frame in reply_report['all_frames_hex']]
    assert [list(struct.unpack('<5I',frame)) for frame in pending_frames]==[[20,0,9,1,1],[20,0,5,0,0]]
    expected_frames=[frame.hex() for frame in pending_frames];m['queued'].clear()
    u.reg_write(UC_ARM_REG_R0,ctx);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    try:u.emu_start(0x26551c,0x50000000,count=100000)
    except Exception:
        (ROOT/'work/home-registration-events-gap.json').write_text(json.dumps({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'recent':recent,'frames':event_received,'callbacks':event_callbacks},indent=2)+'\n');raise
    assert event_finished and event_received==expected_frames and event_callbacks==['0xeaa0']
    assert m['queued']==[[0x420011,0,1,0],[0x420023,0,0,0]],(m['queued'],lookup_requests,query_trace)
    assert struct.unpack('<I',u.mem_read(ctx+4,4))[0]==1
if options.native_event_lookup:
    assert [q['name'] for q in lookup_requests]==['netfront','SpiderApp']
    assert [struct.unpack('<5I',bytes.fromhex(q['reply_hex']))[4] for q in lookup_requests]==[0x20001,1]
    assert struct.unpack('<I',u.mem_read(ctx+20,4))[0]==(5 if options.native_event_services else 3)
receiver_root_events=[p.copy() for p in m['queued']] if options.receive_registration_events else []
if options.dispatch_root_events:
    root_input_events=[p.copy() for p in m['queued']];m['queued'].clear();root_dispatching=True
    assert call(0x17c608,(0x6833dc,root_input_events[0][0],root_input_events[0][2],root_input_events[0][3]))==0
    assert m['queued']==[[0x20303,0,1,0],[0x580101,0,1,0]]
    root_child_events=[v.copy() for v in m['queued']]
    if options.execute_coordinator:
        u.mem_write(0x60016000,bytes(128));u.mem_write(0x613e60+0x2c,struct.pack('<I',0x60016000))
        for index,(entry,offset) in enumerate(coordinator_modules):u.mem_write(0x613e60+offset,struct.pack('<I',0x613f00 if options.native_gui_submit and entry==0x143c0 else 0x60015000+index*32))
        if options.complete_gui_token:u.mem_write(0x613e60+0x14,struct.pack('<I',0x60015140))
        if options.native_gui_submit:
            u.mem_write(0x613f00,bytes(0x6000))
            assert struct.unpack('<I',u.mem_read(0x613f00+0x5eb0,4))[0]==0
            if options.consume_gui_queue:
                gui_context=bytearray(32);gui_context[0]=1;gui_context[1]=2;gui_context[13]=10
                struct.pack_into('<I',gui_context,4,0x3ea150)
                u.mem_write(0x60017000,bytes(gui_context));u.mem_write(0x68233c,struct.pack('<I',0x60017000))
    for register,value in ((UC_ARM_REG_R0,0x6833dc),(UC_ARM_REG_R1,root_input_events[1][0]),(UC_ARM_REG_R2,root_input_events[1][2]),(UC_ARM_REG_R3,root_input_events[1][3]),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
    u.emu_start(0x17c608,0x50000000,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==(0x50000000 if options.execute_coordinator else 0x112fc) and len(root_commands)==1 and root_commands[0][:2]==[0x613e60,7]
    if options.execute_coordinator:
        assert [v['entry'] for v in module_calls]==[hex(entry) for entry,offset in coordinator_modules]
        assert list(struct.unpack('<2I',u.mem_read(0x60016000,8)))==[1,0x207]
        assert struct.unpack('<I',u.mem_read(ctx+4,4))[0]==1 and len(requests)==1
        assert list(u.mem_read(0x6833dc,2))==[2,1], {'root_state':list(u.mem_read(0x6833dc,2)),'modules':module_calls,'commands':root_commands}
if options.run_gui_worker:
    assert m['queued'][-1]==[0x20670,0,0x207,0]
    assert call(0x17c608,(0x60017000,0x20303,1,0))==0
    assert struct.unpack('<I',u.mem_read(0x613f00+0x56d8,4))[0]==1
    assert call(0x17c608,(0x60017000,0x20670,0x207,0))==0
    assert list(u.mem_read(0x60017000,2))==[1,3] and len(gui_worker_threads)==1
    assert call(gui_worker_threads[0][0],(gui_worker_threads[0][1],))==0
    assert gui_worker_native==['0x13f38','0x11a04']
    assert m['queued'][-2:]==[[0x20671,0,0,0],[0x420034,0,0x207,0]]
    worker_output_events=[v.copy() for v in m['queued'][-2:]]
    assert call(0x17c608,(0x60017000,0x20671,0,0))==0
    assert list(u.mem_read(0x60017000,2))==[1,4]
    assert list(struct.unpack('<2I',u.mem_read(0x60016000,8)))==[1,0x207]
    assert struct.unpack('<I',u.mem_read(ctx+4,4))[0]==1
if options.complete_gui_token:
    actual_completion=worker_output_events[1]
    before_wrong=bytes(u.mem_read(0x60016000,128));queued_before_wrong=[v.copy() for v in m['queued']]
    assert call(0x17c608,(0x6833dc,actual_completion[0],0x999,actual_completion[3]))==0
    assert bytes(u.mem_read(0x60016000,128))==before_wrong and m['queued']==queued_before_wrong and not coordinator_completion_calls and not pcs_calls
    assert call(0x17c608,(0x6833dc,actual_completion[0],actual_completion[2],actual_completion[3]))==0
    assert struct.unpack('<I',u.mem_read(0x60016000,4))[0]==0
    assert len(pcs_calls)==1 and coordinator_completion_calls==['0x10e68','0x140b4']
    assert m['queued'][-1]==[0x410009,0,0,0]
    assert struct.unpack('<I',u.mem_read(ctx+4,4))[0]==1
if options.registered_manager_lookup:
    registration_queries_preserved=all(bytes(manager.mem_read(address,len(value)))==value for address,value in registration_preserved.items())
    assert registration_queries_preserved
if options.acknowledge_activation:
    main_address=0x60016800
    if options.first_start_queries:
        lookup_session['usb_fd_fixture']=91;lookup_session['usb_raw_state_fixture']=options.first_start_usb_state
        manager.mem_write(0x60000000+0x41c8,struct.pack('<I',91))
        assert call(0x61320,())==0
        main_address=struct.unpack('<I',u.mem_read(0x682cd8,4))[0];assert main_address==0x682cdc
        assert list(u.mem_read(main_address,2))==[3,1]
        assert call(0x17c608,(main_address,0x41000a,0,0))==0
        assert list(u.mem_read(main_address,2))==[2,1] and not activation_acks
    else:
        main_context=bytearray(32);main_context[0]=2;main_context[1]=2;main_context[13]=6
        struct.pack_into('<I',main_context,4,0x3ef680);u.mem_write(main_address,bytes(main_context))
    assert call(0x17c608,(main_address,0x410009,0,0))==0
    assert list(u.mem_read(main_address,2))==([3,1] if options.first_start_queries else [3,4])
    assert struct.unpack('<I',u.mem_read(ctx+4,4))[0]==2 and len(activation_acks)==1
    assert activation_acks[0]['reply_words']==[16,5,1,0] and activation_acks[0]['client_state_at_send']==1
    assert struct.unpack('<I',manager.mem_read(0x60010000+12,4))[0]==2
    assert struct.unpack('<I',manager.mem_read(0x60000000+0x4b8c,4))[0]==1
paths=[Path(__file__),base,ROOT/'work/targets-jp/SpiderApp']+([reply_source] if reply_source else [])+([ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf'] if options.receive_registration_events else [])
if options.native_event_lookup:paths += [ROOT/'tools/native_lookup_fixture.py',ROOT/'work/targets-jp/sysmgrd']
r={'all_bounded_checks_passed':True,'constructor':'0x2652e0','registration_entry':'0x2687c8','stopped_at_send':'0x268c9c','request_words':words,'request_hex':requests[0].hex(),'opened_ports':opened,'client_sequence_after':1,
   'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
   'limits':['Original constructor and registration request generation execute; getpid432, mutex and two port-open handles supplied.',
             'Stops before send; no registration reply, receiver thread, kernel socket or full boot executed. No device access.']}
if reply_source:
    r['stopped_at_send']=None;r['reply_input']=options.reply_report;r['registration_reply_hex']=reply.hex()
    r['client_app_id']=1;r['client_state']=1;r['thread_requests']=threads;r['returned_successfully']=True
    r['limits'][-1]='Actual manager reply captured in separate model; original client reply processing/ID assignment/state1/thread request execute. Thread creation/delivery virtual; no actual receiver thread, kernel socket or full boot.'
if options.receive_registration_events:
    r['native_registration_receiver']={'entry':'0x26551c','callback_registration_range':['0xfcb4','0xfd68'],'frames_received_hex':event_received,'callbacks':event_callbacks,'queued_root_events':receiver_root_events,'returned_to_receive':event_finished,'client_context_preserved':True,'client_state_after':1,'name_queries_virtual':name_queries}
    r['limits'].append('Same registered client consumes both original-manager frames through native receiver/default callback9/registered callback5. Name lookup/argument/battery helpers and Root queue delivery virtual; Root events captured, not consumed. Thread execution scheduled by test, not OS.')
if options.native_event_lookup:
    assert lookup_session['queries']==2+len(service_requests)+len(activation_acks) and lookup_requests[1]['parser']['retained_native_parser_table']
    assert lookup_requests[0]['parser'].get('retained_native_parser_table') if options.registered_manager_lookup else lookup_requests[0]['parser']['native_parser_executed']
    r['native_event_lookup_requests']=lookup_requests;r['client_sequence_after_events']=3;r['lookup_manager_reused']=True
    r['limits']=[line.replace('Name lookup/argument/battery helpers','Argument/battery helpers') for line in r['limits']]
    r['limits'].append('Event name lookup uses original client2664d0 and separate native manager1574c parser/1084c lookup for each request; libc and transport virtual, one retained manager query model; configuration parsed only once, second query preserves table bytes and core mode. No supplied application ID results in this variant.')
if options.registered_manager_lookup:
    assert registration_queries_preserved
    r['registered_manager_lookup']={'same_registration_manager_instance':True,'port_registry_and_pool_unchanged':True,'home_record_unchanged':True,'request_buffer_outside_ipc_pool':'0x6001b000','queries':lookup_session['queries']-len(activation_acks),'requests_including_activation':lookup_session['queries'],'preservation_scope':'before_main_activation_ack'}
    r['source_hashes'].update({str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in registration_model['paths']})
    r['source_hashes']['tools/check_home_ipc_registration.py']=hashlib.sha256((ROOT/'tools/check_home_ipc_registration.py').read_bytes()).hexdigest()
    r['limits']=[line.replace('separate native manager1574c parser/1084c lookup for each request','retained original registration manager1084c lookup').replace('one retained manager query model; configuration parsed only once, second query preserves table bytes and core mode','same registration manager model; imported original parsed table retained, no configuration reparse or mode reset') for line in r['limits']]
    r['limits'].append('Queries continue in the same manager emulator after original Home registration probe. Home state0 prerequisite was supplied upstream; this is not full native boot or the full Home lifecycle instance.')
if options.native_event_services:
    assert [q['operation'] for q in service_requests]==([35,7,8,7] if options.first_start_queries and options.first_start_usb_state==0 else [35,7,8] if options.first_start_queries else [35,7])
    assert list(struct.unpack('<5I',bytes.fromhex(service_requests[0]['reply_hex'])[:20]))==[1044,3,35,0,0]
    assert list(struct.unpack('<6I',bytes.fromhex(service_requests[1]['reply_hex'])))==[24,4,7,0,0,0]
    r['native_event_services']=service_requests;r['client_sequence_after_events']=5
    r['limits']=[line.replace('Argument/battery helpers and Root queue delivery virtual','Root queue delivery virtual') for line in r['limits']]
    r['limits'].append('Original argument/battery client helpers and manager10750/fb1c execute in retained registered manager. Argc0 comes from preserved Home record. Physical12034 refresh skipped; battery reply uses existing cache0, not a measured battery. Root events remain captured only.')
if options.dispatch_root_events:
    r['limits']=[line.replace('Root events remain captured only.','Root events execute up to coordinator command7 entry.').replace('Root events captured, not consumed.','Root events consumed up to coordinator command7 entry.') for line in r['limits']]
    r['registered_client_root_dispatch']={'root_constructor':'0x714c4','root_constructed_before_client':True,'completion_slots_fixture':list(range(6)),'input_events':root_input_events,'queued_child_events':root_child_events,'coordinator_command':root_commands[0],'stopped_at_coordinator_entry':'0x112fc','coordinator_executed':False}
    r['limits'].append('Same client model constructed Root before registration; six startup completion notifications supplied. Actual receiver-generated events consumed by original Root dispatcher, stopping at coordinator command7 entry. Coordinator/GUI/children not executed in this variant.')
if options.execute_coordinator:
    r['registered_client_root_dispatch']['stopped_at_coordinator_entry']=None;r['registered_client_root_dispatch']['coordinator_executed']=True
    r['coordinator_result']={'entry':'0x112fc','command':7,'module_calls':module_calls,'pending_list_fixture_address':'0x60016000','native_pending_insert':'0x48a14','pending_tokens':[0x207],'root_mode_state':[2,1],'completion_delivered':False,'active_ack_sent':False}
    r['limits']=[line.replace('stopping at coordinator command7 entry','continuing through original coordinator command7').replace('Coordinator/GUI/children not executed in this variant.','Coordinator executes; all nine module bodies and contexts supplied. No completion, GUI or child event consumption.') for line in r['limits']]
    r['limits'].append('Original coordinator calls nine module replacements; GUI replacement returns token207, others return0. Original48a14 inserts token in supplied empty collector. Root remains2/1 with pending token; no completion or active acknowledgement injected. No real GUI/hardware recovery.')
if options.native_gui_submit:
    assert gui_token_results==[0x207]
    assert len(gui_submit_events)==1 and gui_submit_events[0][1:]==[0x20110,0,0]
    assert [0x20670,0,0x207,0] in m['queued']
    r['native_gui_submission']={'entry':'0x143c0','resume_entry':'0x120ec','context_fixture':'0x613f00','inactive_field_fixture':0,'submitted_queue_items':gui_submit_events,'native_token':0x207,'root_queue_event':[0x20670,0,0x207,0],'backend_services_virtual':gui_service_calls,'completion_delivered':False}
    r['limits']=[line.replace('all nine module bodies and contexts supplied','eight module bodies supplied; GUI143c0/120ec/120d8 native, GUI context and backend services supplied').replace('GUI replacement returns token207','Original GUI submission produces token207').replace('nine module replacements','eight module replacements and native GUI submission') for line in r['limits']]
    r['limits'].append('GUI context is a supplied zeroed inactive context, not a constructed full GUI. Original command7/resume/queue-item construction/token207 execute; GUI queue backend and display/audio/input service effects virtual. Worker and completion not executed.')
if options.consume_gui_queue:
    assert len([d for d in gui_dispatch if d[1]==0x20110])==1 and gui_dispatch[0][1:]==[0x20110,0,0]
    assert [v['entry'] for v in gui_restore_trace]==['0x5cfb4','0x12ef8','0x13e04']
    assert struct.unpack('<I',u.mem_read(0x613f00+0x5eb0,4))[0]==1
    r['gui_queue_consumption']={'original_route':['0x11f68','0x54fec','0x17c608','0x5cfb4'],'dispatcher_context_fixture':'0x60017000','dispatcher_initial_mode_state_fixture':[1,2],'dispatch_calls':gui_dispatch,'restore_trace':gui_restore_trace,'owner_active_field_after':1,'saved_input_mask_fixture':0,'page_rebuild_executed':False,'worker_executed':False}
    r['limits']=[line.replace('GUI queue backend and display/audio/input service effects virtual','GUI queue routing native; display/audio/input service effects virtual').replace('GUI queue backend','GUI page rebuild') for line in r['limits']]
    r['limits'].append('Original11f68/54fec routes20110 through supplied GUI dispatcher1/2 and original5cfb4/13e04. Owner becomes active1. Page rebuild12ef8 deferred at explicit service boundary; saved input mask0 makes13e04 no-op. Token207 remains pending; no worker/display/completion executed.')
if options.run_gui_worker:
    r['gui_worker']={'native_entries':gui_worker_native,'thread_requests':gui_worker_threads,'backend_services_virtual':gui_worker_services,'emitted_events':worker_output_events,'gui_mode_state_after':[1,4],'pending_token_after':0x207,'coordinator_completion_consumed':False,'active_ack_sent':False}
    r['gui_queue_consumption']['worker_executed']=True
    r['limits']=[line.replace('Worker and completion not executed.','Worker and GUI20671 executed; coordinator420034 completion pending.').replace('Worker and completion not executed','Worker executed, coordinator completion pending').replace('Token207 remains pending; no worker/display/completion executed.','Token207 remains pending; worker and GUI20671 executed, no display or coordinator completion.') for line in r['limits']]
    r['limits'].append('Actual20670 dispatch requests13f38 via1402c. Thread scheduled manually; original13f38/11a04 execute with explicit backend/cancellation-service replacements. Actual20671 consumed by original GUI transition3->4; actual420034 remains unconsumed, token207 pending. No real page rebuild/rendering/OS thread or hardware qualification.')
if options.complete_gui_token:
    r['gui_token_completion']={'actual_worker_event':actual_completion,'root_dispatch':'0x17c608','pending_count_before':1,'pending_count_after':0,'unmatched_token_fixture':0x999,'unmatched_token_preserves_pending':True,'pcs_calls_virtual':pcs_calls,'completion_helpers_virtual':coordinator_completion_calls,'emitted_main_event':[0x410009,0,0,0],'main_event_consumed':False}
    r['gui_worker']['coordinator_completion_consumed']=True;r['gui_worker']['pending_token_after']=None
    r['coordinator_result']['completion_delivered']=True;r['coordinator_result']['pending_tokens']=[]
    r['native_gui_submission']['completion_delivered']=True
    r['limits']=['Same original client model runs registration/reply/receiver/name/argv/cached-battery queries and Root/coordinator/GUI submission/worker completion; registration-manager model retained for queries. Startup completion slots, PID and Home state0 prerequisite supplied.',
                  'GUI context and dispatcher1/2 supplied; eight module bodies replaced. Page rebuild12ef8 deferred. libc/logging/locks/transport and display/audio/input backend effects virtual.',
                  'Worker13f38/11a04 manually scheduled after original thread request; backend/cancellation services replaced. Original GUI consumes20671 and reaches1/4.',
                  'Actual worker420034 dispatched by original Root; native token removal verified with wrong-token999 control. PCS command7 and final10e68/140b4 helpers replaced; original coordinator emits410009.',
                  'Main410009 is not consumed; client remains1 and no active ack. Auxiliary580101 still queued. No full GUI/page, OS scheduling, device execution, storage writes or hardware qualification.']
if options.acknowledge_activation:
    r['main_activation_completion']={'main_initial_mode_state_fixture':[2,2],'main_descriptor':'0x3ef680','consumed_event':[0x410009,0,0,0],'main_after':[3,4],'actual_acks':activation_acks,'client_state_after':2,'manager_home_record_state_after':2,'manager_current_app_after':1,'client_sequence_after':6,'main_constructed_by_original_boot':False}
    r['gui_token_completion']['main_event_consumed']=True;r['gui_worker']['active_ack_sent']=True;r['coordinator_result']['active_ack_sent']=True
    r['limits']=[line.replace('Main410009 is not consumed; client remains1 and no active ack.','Main410009 consumed from supplied Main2/2 context; original client sends active ack, same manager accepts it, client becomes2.') for line in r['limits']]
    r['limits'].append('Main state2/2/descriptor3ef680 is a prerequisite fixture, not native Main startup. Original Main dispatcher/activation acknowledgement and f75c reply execute; actual rendering/page rebuild and physical IPC remain unqualified.')
if options.first_start_queries:
    expected_usb={0:0,1:2,2:4,3:3,4:1}[options.first_start_usb_state]
    usb_reply=list(struct.unpack('<5I',bytes.fromhex(service_requests[2]['reply_hex'])))
    assert usb_reply==[20,6,8,0,expected_usb]
    expected_main_event=0x420017 if expected_usb==0 else 0x42001a
    assert m['queued'][-1]==[expected_main_event,0,0,0]
    r['main_activation_completion']['main_after']=[3,1]
    r['main_activation_completion']['main_initial_mode_state_fixture']=None
    r['main_activation_completion']['main_constructed_by_original_boot']=False
    r['main_activation_completion']['client_sequence_after']=8 if expected_usb==0 else 7
    r['first_start_queries']={'native_main_constructor':'0x61320','main_constructor_state':[3,1],'inactive_completion_event_fixture':'0x41000a','main_state_after_inactive_event':[2,1],'first_start_handler':'0x61414','usb_raw_state_fixture':options.first_start_usb_state,'usb_reply':usb_reply,'battery_queried':expected_usb==0,'queued_event':m['queued'][-1],'main_after':[3,1],'client_state_after':2,'manager_home_state_after':2}
    r['limits']=[line for line in r['limits'] if not line.startswith('Main state2/2/')]
    r['limits'].append('Native Main constructor and first-start61414 execute after supplied inactive-completion event41000a, not a complete cold boot. Original active acknowledgement/query8/conditional battery requests go to retained manager. USB descriptor/raw ioctl and battery cache remain fixtures. Main returns3/1 and queues42001a/420017; these events not consumed, recovery Main2/2 prerequisite not established.')
(ROOT/('sources/native-main-first-start-usb'+str(options.first_start_usb_state)+'.json' if options.first_start_queries else 'sources/native-home-client-registration-active.json' if options.acknowledge_activation else 'sources/native-home-client-registration-gui-completion.json' if options.complete_gui_token else 'sources/native-home-client-registration-gui-worker.json' if options.run_gui_worker else 'sources/native-home-client-registration-gui-queue.json' if options.consume_gui_queue else 'sources/native-home-client-registration-gui-submit.json' if options.native_gui_submit else 'sources/native-home-client-registration-coordinator.json' if options.execute_coordinator else 'sources/native-home-client-registration-root.json' if options.dispatch_root_events else 'sources/native-home-client-registration-services.json' if options.native_event_services else 'sources/native-home-client-registration-manager-lookup.json' if options.registered_manager_lookup else 'sources/native-home-client-registration-native-lookup.json' if options.native_event_lookup else 'sources/native-home-client-registration-events.json' if options.receive_registration_events else 'sources/native-home-client-registration-reply.json' if reply_source else 'sources/native-home-client-registration-request.json')).write_text(json.dumps(r,indent=2)+'\n')
print('Original Home constructor/registration generates32-byte request and PID-derived ports864/865')
