"""Feed captured proxy return into original reaper/callback/RUN handler.

Registry, wait record and initial WaitActive state are explicit supplied boundaries.
Op3 observer transport, actual activation and display recovery remain virtual.
"""
from pathlib import Path
import hashlib,io,json,struct,argparse
from elftools.elf.elffile import ELFFile
from evidence_checks import verify_report
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--home-confirmation-report')
parser.add_argument('--home-confirmation-cycle',type=int,choices=(1,2),default=1,help='Select the original Home recovery cycle; cycle2 requires a three-cycle report.')
parser.add_argument('--proxy-exit-report',default='sources/native-frontend-proxy-exit.json')
parser.add_argument('--launch-report',default='sources/native-manager-proxy-exec-request.json')
parser.add_argument('--report',help='Distinct report under sources/, preserving standard contracts.')
parser.add_argument('--include-manager-op3-fixture',action='store_true',help='Independent diagnostic only; original proxy self-event shutdown is not manager op3.')
parser.add_argument('--pending-responder-switch',action='store_true',help='Request target2 from native RUN, then reap Homebrew before inactive ack; USB hardware not simulated.')
parser.add_argument('--native-stop-enumeration',action='store_true',help='Use native stop/filter/predicate and11858 running-app enumeration; AppList IDs/existence remain fixtures.')
parser.add_argument('--native-registry',action='store_true',help='Use native list constructor/insert/find/count/remove and native AppList enumeration from parsed config IDs.')
parser.add_argument('--native-return-registry',action='store_true',help='Native registry and original existence callback for ordinary Walkman return; does not enable Responder/USB flow.')
parser.add_argument('--manager-state-report',help='Import model RAM saved after this same launch, preserving domain state/records before reap; never device memory.')
parser.add_argument('--save-return-state',action='store_true',help='Save model RAM after native Walkman confirmation; no device access.')
parser.add_argument('--stop-before-walkman-confirmation',action='store_true',help='Reap and request Walkman only; do not supply a recovery acknowledgement.')
parser.add_argument('--native-ipc-exit-cleanup',action='store_true',help='Keep imported original IPC observer and execute port removal/pool return during reap.')
parser.add_argument('--core-state',type=int,choices=(1,2),default=2,help='Explicit original core mode fixture; use1 to match pre-unmount contents handoff.')
parser.add_argument('--usb-handoff',action='store_true',help='After native reaper/Responder confirmation, run fc60 with captured Responder op10 in same memory; libc remains virtual.')
parser.add_argument('--usb-unmount-errno',type=int,choices=(0,5,16,22),default=0,help='Virtual umount failure in same-memory handoff; no physical filesystem access.')
parser.add_argument('--responder-return',action='store_true',help='Captured Responder op6 -> original quit/reaper -> SpiderApp; virtual wait/IPC.')
options=parser.parse_args()
if options.home_confirmation_cycle==2:assert options.home_confirmation_report
if options.stop_before_walkman_confirmation:assert options.manager_state_report and not options.home_confirmation_report and not options.save_return_state
if options.manager_state_report:options.native_return_registry=True
if options.native_return_registry:
    assert not any((options.responder_return,options.usb_handoff,options.usb_unmount_errno,options.pending_responder_switch,options.native_stop_enumeration))
    options.native_registry=True
responder_return_input=None
if options.responder_return:
    assert not(options.usb_handoff or options.usb_unmount_errno or options.pending_responder_switch or options.native_stop_enumeration or options.include_manager_op3_fixture)
    options.native_registry=True;options.core_state=1
    source_path='sources/native-responder-walkman-lookup-reply.json'
    source_bytes=(ROOT/source_path).read_bytes();source=json.loads(source_bytes)
    assert source['all_passed'] and source['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
    packet=bytes.fromhex(next(row for row in source['cases'] if row['case']=='success')['requests'][1]['packet_hex'])
    assert len(packet)==1060 and list(struct.unpack('<8I',packet[:32]))==[1060,56,2,6,66,1,1,0]
    responder_return_input={'path':source_path,'sha256':hashlib.sha256(source_bytes).hexdigest(),'packet_hex':packet.hex()}
if options.usb_unmount_errno:options.usb_handoff=True
handoff_capture=None
if options.usb_handoff:
    options.native_registry=True;options.core_state=1
    capture_path=ROOT/'sources/native-responder-activation-usb-request.json'
    capture_bytes=capture_path.read_bytes();capture=json.loads(capture_bytes)
    assert capture['all_passed'] and capture['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
    row=next(r for r in capture['cases'] if r['case']=='active-success')
    assert row['activation_requests']==[[24,55,2,1,66,2]] and row['selected_actions']==['0xfa3c']
    handoff_capture={'path':capture_path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(capture_bytes).hexdigest(),'request':row['captured_requests'][0]['words']}
    assert handoff_capture['request']==[20,56,2,10,66]
if options.native_registry and not options.responder_return and not options.native_return_registry:options.native_stop_enumeration=True
if options.native_stop_enumeration:options.pending_responder_switch=True
return_target=2 if options.pending_responder_switch else 1
home_input=None;home_packet=None
if options.home_confirmation_report:
    home_path=(ROOT/options.home_confirmation_report).resolve();assert home_path.is_relative_to(ROOT/'sources')
    home_bytes=home_path.read_bytes();home=json.loads(home_bytes)
    candidate=(ROOT/'work/home-entry-candidate/SpiderApp.analysis-only.elf').read_bytes()
    assert home['candidate_sha256']==hashlib.sha256(candidate).hexdigest()
    confirmations=[]
    for row in home['cases']:
        if row['rebuild_cycle']==options.home_confirmation_cycle:
            packets=row['command7_activation_acks'] if options.home_confirmation_cycle==2 else row['native_manager_close']['all_apf_requests']
            selected=[packet for packet in packets if packet[2]==1 and packet[3]==1 and packet[5]==2]
            assert len(selected)==1;confirmations.append(selected[0])
    assert len(confirmations)==2 and confirmations[0]==confirmations[1]
    home_packet=confirmations[0]
    home_input={'path':options.home_confirmation_report,'sha256':hashlib.sha256(home_bytes).hexdigest(),'candidate_sha256':home['candidate_sha256'],'native_home_activation_packet':home_packet,'recovery_cycle':options.home_confirmation_cycle}
proxy_path=(ROOT/options.proxy_exit_report).resolve();assert proxy_path.is_relative_to(ROOT/'sources')
captured=proxy_path.read_bytes()
proxy=json.loads(captured)
assert proxy['frontend_exit_input'] and proxy['cases']
assert all(row['quit_after_reaped_child'] for row in proxy['cases'])
statuses=sorted({row['monitor_return']<<8 for row in proxy['cases']})
launch_path=(ROOT/options.launch_report).resolve();assert launch_path.is_relative_to(ROOT/'sources')
launch_bytes=launch_path.read_bytes()
launch=json.loads(launch_bytes)
manager_state=None;manager_state_bytes=None
if options.manager_state_report:
    assert (ROOT/options.manager_state_report).resolve()==launch_path
    manager_state=launch['native_manager_state'];state_path=(ROOT/manager_state['path']).resolve();assert state_path.is_relative_to(ROOT/'work')
    manager_state_bytes=state_path.read_bytes();assert len(manager_state_bytes)==manager_state['bytes']==0x20000 and hashlib.sha256(manager_state_bytes).hexdigest()==manager_state['sha256']
    assert manager_state['base']=='0x60000000' and manager_state['current_app']==0x30001 and manager_state['pid']>0
assert launch['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
if options.native_ipc_exit_cleanup:
    assert manager_state and launch['native_ipc_service']['constructor']=='0xefd4' and launch['native_ipc_service']['observer']=='0xf298'
assert launch['appproxy_sha256']==proxy['appproxy_sha256']
frontend_bytes=(ROOT/proxy['frontend_exit_input']['path']).read_bytes()
assert hashlib.sha256(frontend_bytes).hexdigest()==proxy['frontend_exit_input']['sha256']
if proxy['frontend_exit_input'].get('mode')=='actual-workflow-exits':
    assert options.report
    verify_report(ROOT,options.proxy_exit_report)
    verify_report(ROOT,proxy['frontend_exit_input']['path'])
    argument_report=proxy['frontend_exit_input']['proxy_argument_report']
    argument=verify_report(ROOT,argument_report);assert argument['passed']
    assert argument['actual_candidate_sha256']==proxy['frontend_exit_input']['frontend_sha256']
    assert (ROOT/argument['composition']).resolve()==(ROOT/proxy['frontend_exit_input']['composition']).resolve()
    assert hashlib.sha256((ROOT/argument_report).read_bytes()).hexdigest()==proxy['frontend_exit_input']['proxy_argument_report_sha256']
    assert argument['source_hashes'][options.launch_report]==hashlib.sha256(launch_bytes).hexdigest()
    for observation in proxy['frontend_exit_input']['observations']:verify_report(ROOT,observation['report'])
else:
    assert {'path':options.launch_report,'sha256':hashlib.sha256(launch_bytes).hexdigest()} in json.loads(frontend_bytes)['proxy_capture_inputs']
assert proxy['registration_report_sha256']==hashlib.sha256(launch_bytes).hexdigest()
activation_source=next(row for row in launch['cases'] if row['target']=='0x30001')
activation_packets=activation_source['proxy_registration']['activation']['proxy_requests']
assert len(activation_packets)==1
activation_packet=activation_packets[0]
assert activation_packet[:4]==[24,1,0x30001,1] and activation_packet[5]==2
if options.responder_return:
    client_bytes=(ROOT/'sources/native-responder-activation-usb-request.json').read_bytes();client=json.loads(client_bytes)
    assert client['all_passed'] and client['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
    activation_packet=next(r for r in client['cases'] if r['case']=='active-success')['activation_requests'][0]
    assert activation_packet==[24,55,2,1,66,2]
    statuses=[0] # supplied normal Responder wait result; not a real process observation
raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes()
digest=hashlib.sha256(raw).hexdigest()
assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
manager_module_regions=[]
if manager_state:
    expected={(segment['p_vaddr'],segment['p_memsz']) for segment in elf.iter_segments() if segment['p_type']=='PT_LOAD' and segment['p_flags']&2}
    assert {(int(region['address'],0),region['bytes']) for region in manager_state['module_regions']}==expected
    for region in manager_state['module_regions']:
        path=(ROOT/region['path']).resolve();assert path.is_relative_to(ROOT/'work');content=path.read_bytes()
        assert len(content)==region['bytes'] and hashlib.sha256(content).hexdigest()==region['sha256']
        manager_module_regions.append((int(region['address'],0),content))
rows=[]
for status in statuses:
 for running in ((True,) if manager_state else (False,) if options.pending_responder_switch or options.responder_return else (True,False)):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x30000)
    ctx=0x60000000;changer=ctx+0x4b88;record=0x60020000;app=2 if options.responder_return else 0x30001;pid=manager_state['pid'] if manager_state else 321
    if manager_state:
        u.mem_write(ctx,manager_state_bytes);record=int(manager_state['target_record'],0)
        for address,content in manager_module_regions:u.mem_write(address,content)
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    if manager_state:
        domain_offsets=[0,4,0x18,0x4b88,0x4b8c,0x4b90,0x503c,0x5144,0x5148]+[record-ctx+i for i in (0,4,8,12)]+[int(manager_state['home_record'],0)-ctx+i for i in (0,4,8,12)]
        domain_before={hex(offset):word(ctx+offset) for offset in domain_offsets}
        assert [word(record+i) for i in (4,8,12)]==[pid,app,2]
    # Start in native WaitActive, then deliver activation through the dispatcher.
    if manager_state:
        wait_table=word(changer);assert wait_table==0x34bd0 and word(changer+4)==app
    else:
        u.reg_write(UC_ARM_REG_LR,0x50000000)
        u.emu_start(0x15050,0x50000000,count=1000)
        wait_table=u.reg_read(UC_ARM_REG_R0)
        assert wait_table==0x34bec
        put(changer,wait_table)
    put(ctx+0x41c4,1);put(ctx+0x41c0,77);put(ctx+0x41b0,0xb2f4);put(ctx+0x41b4,ctx)
    if manager_state:assert word(ctx+0x503c)==options.core_state
    else:put(ctx+0x503c,options.core_state);put(ctx+0x5144,app);put(ctx+0x5148,pid)
    put(ctx+0x41b8,0xb614);put(ctx+0x41bc,ctx)
    if options.native_ipc_exit_cleanup:
        assert [word(ctx+i) for i in (0x51b4,0x51b8)]==[0xf298,0x60006000]
    else:put(ctx+0x51b4,0x50000100);put(ctx+0x51b8,0x12345678)
    if options.native_ipc_exit_cleanup:assert [word(ctx+i) for i in (0x51bc,0x51c0)]==[0xf314,0x60006000]
    else:put(ctx+0x51bc,0x50000500);put(ctx+0x51c0,0x87654321)
    if manager_state:assert word(record+4)==pid and word(record+8)==app and word(record+12)==2
    else:
        for register,value in ((UC_ARM_REG_R0,record),(UC_ARM_REG_R1,pid),(UC_ARM_REG_R2,app),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0x165fc,0x50000000,count=1000)
        assert list(struct.unpack('<5I',u.mem_read(record+4,20)))==[pid,app,0,0,0]
        put(changer+8,app)
    for offset,callback in ((0x494,0x50000200),(0x49c,0x50000300),(0x4a4,0x50000400)):
        put(changer+offset,0xbd54 if options.native_ipc_exit_cleanup and offset==0x49c else callback)
    put(changer+0x4a0,0x50000600)
    put(changer+0x490,ctx);put(changer+0x4a8,0xbd94);put(changer+0x4ac,0xbd9c)
    walkman_record=int(manager_state['home_record'],0) if manager_state else 0x60020100
    if manager_state:assert word(walkman_record+8)==return_target and word(walkman_record+12)==1
    else:
        for register,value in ((UC_ARM_REG_R0,walkman_record),(UC_ARM_REG_R1,432),(UC_ARM_REG_R2,return_target),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0x165fc,0x50000000,count=1000)
    callbacks=[];events=[];calls=[];notices=[];removed=[];quit_notices=[];quit_replies=[];activation_replies=[];walkman_replies=[];phase='activation'
    ipc_cleanup_calls=[];ipc_cleanup_queue=[];native_activation_notices=[]
    def ipc_entries():
        pointer=word(0x60006018);values=[];seen=set()
        while pointer:
            assert pointer not in seen;seen.add(pointer);values.append([word(pointer+4),word(pointer+8)]);pointer=word(pointer)
        return values
    ipc_entries_before=ipc_entries() if options.native_ipc_exit_cleanup else None
    native_stop_calls=[];native_running_enumerations=[]
    storage_events=[];handoff_replies=[];recent=[]
    helpers={0xa188,0x1c4d0,0x16578,0xb1f8,0xaa40,0xaa74,0xaaac,0xaf54,0xa780,0xa714,0xad84,0xae68,0xa30c,0x113e4,0x169b0,0x1c5ac,0x1e518,0x1b594,0x1a458,0x1a4f0,0x1a508}
    def hook(uc,pc,size,data):
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if options.native_ipc_exit_cleanup and pc==0xf314:
            native_activation_notices.append({'recipient':a[1],'packet':list(struct.unpack('<3I',uc.mem_read(a[0],12)))});return
        if options.native_ipc_exit_cleanup and pc==0xf298:
            assert a[1]==0x60006000;notices.append(list(struct.unpack('<3I',uc.mem_read(a[0],12))));return
        if options.native_ipc_exit_cleanup and pc==0x1967c:
            assert a[0]==77 and a[2]==52;ipc_cleanup_queue.append(list(struct.unpack('<5I',uc.mem_read(a[1],20))))
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if options.native_ipc_exit_cleanup and pc==symbols['memcpy']:
            assert a[2]<=0x10000;uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])))
            uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if manager_state:
            recent.append({'pc':hex(pc),'r0':hex(a[0]),'r1':hex(a[1]),'r2':hex(a[2]),'lr':hex(uc.reg_read(UC_ARM_REG_LR))})
            if len(recent)>32:recent.pop(0)
        if options.usb_handoff and phase=='usb-handoff':
            if pc==0x1c888 and options.usb_unmount_errno in (5,16):
                storage_events.append('fatal-boundary:1c888');uc.emu_stop();return
            storage_helpers={0x13680,0x17588,symbols['sync'],symbols['umount'],symbols['open'],symbols['ioctl'],symbols['close'],symbols['__errno_location']}
            if pc in storage_helpers:
                def string(p):return bytes(uc.mem_read(p,128)).split(b'\0',1)[0].decode()
                if pc==0x13680:storage_events.append('virtual-pre-unmount-helper')
                elif pc==symbols['sync']:storage_events.append('sync')
                elif pc==symbols['umount']:
                    assert string(a[0])=='/contents' and removed==[app]
                    storage_events.append('umount:/contents')
                    result=-1 if options.usb_unmount_errno else 0
                elif pc==symbols['__errno_location']:
                    put(ctx+0x26000,options.usb_unmount_errno);result=ctx+0x26000
                elif pc==symbols['open']:
                    assert string(a[0])=='/dev/mgscsi' and a[1]==1
                    storage_events.append('open:mgscsi');result=77
                elif pc==symbols['ioctl']:
                    assert a in ([77,0x40017325,1],[91,0x40046702,0])
                    storage_events.append('ioctl:'+hex(a[1]))
                elif pc==symbols['close']:
                    assert a[0]==77;storage_events.append('close:mgscsi')
                uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if options.native_stop_enumeration and pc in (0xae68,0xaf54):
            native_stop_calls.append({'procedure':hex(pc),'policy':a[1],'removed':removed.copy()});return
        if pc==0xb2f4:callbacks.append(a);return
        if pc==0x19ef4:result=1
        elif pc==0x110ac:
            if options.native_registry:return
            result=(1 if a[1]==0x10001 or a[1]==app and app not in removed else 0) if options.native_stop_enumeration else 1
        elif options.native_stop_enumeration and pc==0x15b70:
            app_ids=[1,2,0x10001,0x10002,0x10003,0x20001,app]
            if options.native_registry:
                native_running_enumerations.append({'source':'native15b70 over original-parser IDs','removed':removed.copy()});return
            assert a[2]==16;uc.mem_write(a[1],struct.pack('<7I',*app_ids));put(uc.reg_read(UC_ARM_REG_R3),len(app_ids));native_running_enumerations.append({'known_ids':app_ids,'removed':removed.copy()})
        elif pc==0x16028:result=101
        elif pc==symbols['read']:
            assert a[0]==101 and a[2]==8;uc.mem_write(a[1],struct.pack('<II',pid,status));result=8
        elif pc==0x16510:
            if options.native_registry:return
            result=walkman_record if word(a[2])==return_target else record
        elif options.native_return_registry and pc==0x16578:return
        elif pc==0x163dc:
            if options.native_ipc_exit_cleanup and a[0]==0x60006008:ipc_cleanup_calls.append(word(a[2]))
            else:removed.append(word(a[2]))
            if options.native_registry:return
        elif pc==0x14758:
            if phase=='walkman':assert a[0]==changer and a[1] in (1,2) and a[2]==return_target
            else:assert a==[changer,2 if phase=='activation' else 0,app]
            events.append(a)
            return
        elif options.native_return_registry and pc==0xbd84:
            assert a[:2]==[return_target,ctx];calls.append({'operation':'exists','target':a[0]});return
        elif options.native_ipc_exit_cleanup and pc==0xbd54:
            assert a[0]==return_target;calls.append({'operation':'activate','target':a[0]});return
        elif pc in (0x50000200,0x50000300,0x50000400):
            operation={0x50000200:'launch',0x50000300:'activate',0x50000400:'exists'}[pc]
            calls.append({'operation':operation,'target':a[0]});result=int(running) if operation=='exists' else 0
        elif pc==0x50000600:calls.append({'operation':'deactivate','target':a[0]})
        elif pc==0x1485c:
            calls.append({'operation':'set_state','table':hex(a[1])});return
        elif pc==0x50000100:
            notices.append(list(struct.unpack('<3I',uc.mem_read(a[0],12))));assert a[1]==0x12345678
        elif pc==0x50000500:
            quit_notices.append(list(struct.unpack('<3I',uc.mem_read(a[0],12))))
            assert a[1:]==[app,0x87654321]
        elif pc==0x16d18:
            (handoff_replies if phase=='usb-handoff' else activation_replies if phase=='activation' else walkman_replies if phase=='walkman' else quit_replies).append(list(struct.unpack('<4I',uc.mem_read(a[2],16))))
        elif pc in (0x1c888,0x1c8c8):raise AssertionError('Original fatal path')
        elif pc not in helpers:return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    def registry_call(address,values):
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(register,value)
        u.reg_write(UC_ARM_REG_SP,0x60028000);u.reg_write(UC_ARM_REG_LR,0x50000000)
        u.emu_start(address,0x50000000,count=30000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    if options.responder_return:
        scratch_changer=ctx+0x27000
        assert registry_call(0x14648,(scratch_changer,ctx,0x211dc))==0
        assert word(scratch_changer+0x498)==0xbd44
        put(changer+0x498,word(scratch_changer+0x498))
    if options.native_return_registry:
        scratch_changer=ctx+0x27000;assert registry_call(0x14648,(scratch_changer,ctx,0x211dc))==0
        assert word(scratch_changer+0x4a4)==0xbd84;put(changer+0x4a4,word(scratch_changer+0x4a4))
    if options.native_registry and not manager_state:
        parsed=json.loads((ROOT/'sources/native-applist-full-config.json').read_text())
        entries=next(row['records'] for row in parsed['cases'] if row['case']=='full-merged')
        ids=[int(entry['id'],0) for entry in entries];assert len(ids)==7 and ids[-1]==0x30001 and app in ids
        put(ctx,len(ids));put(ctx+4,0x60022000)
        for index,app_id in enumerate(ids):put(0x60022000+index*0x510,app_id)
        assert registry_call(0x162b4,(ctx+8,))==0
        daemon_record=0x60020200;registry_call(0x165fc,(daemon_record,900,0x10001))
        assert registry_call(0x1633c,(ctx+8,daemon_record))==0
        assert registry_call(0x1633c,(ctx+8,record))==0
        if options.native_return_registry and running:
            put(walkman_record+12,1);assert registry_call(0x1633c,(ctx+8,walkman_record))==0
        assert registry_call(0x110ac,(ctx,app))==1 and registry_call(0x110ac,(ctx,0x10001))==1
        assert registry_call(0x110ac,(ctx,return_target))==int(options.native_return_registry and running)
    if manager_state:
        assert registry_call(0x110ac,(ctx,app))==1 and registry_call(0x110ac,(ctx,return_target))==1 and registry_call(0x16594,(ctx+8,0,0))==2
        assert domain_before=={hex(offset):word(ctx+offset) for offset in domain_offsets}
    ipc=0x60021000;request=0x60021100
    put(ipc,ctx);put(ipc+4,44)
    if not manager_state:
        u.mem_write(request,struct.pack('<6I',*activation_packet))
        for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0xf75c,0x50000000,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        run_table=word(changer)
        assert run_table==0x34bd0 and word(run_table+4)==0x1538c and word(changer+4)==app
        assert events==[[changer,2,app]] and calls==[{'operation':'set_state','table':'0x34bd0'}]
        assert activation_replies==[[16,activation_packet[1],activation_packet[3],0]]
        activation={'initial_table':hex(wait_table),'core_state_fixture':options.core_state,'entry':'0xf75c','captured_proxy_request':activation_packet,'replies':activation_replies,'record_state':word(record+12),'event':events.copy(),'transitions':calls.copy(),'current_id':word(changer+4),'result_table':hex(run_table)}
        assert word(record+12)==2
    else:
        run_table=word(changer);assert run_table==0x34bd0 and word(changer+4)==app and word(record+12)==2
        activation={'from_saved_manager_state':True,'initial_table':hex(run_table),'record_state':2,'current_id':app,'source_sha256':manager_state['sha256']}
    events.clear();calls.clear();notices.clear();phase='quit'
    if options.include_manager_op3_fixture:
        ipc=0x60021000;request=0x60021100
        put(ipc,ctx);put(ipc+4,44)
        u.mem_write(request,struct.pack('<6I',24,55,0,3,66,app))
        for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0xf89c,0x50000000,count=30000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        assert quit_notices==[[4,0,0]] and quit_replies==[[16,55,3,0]],(quit_notices,quit_replies)
        assert word(record+12)==2 and word(record+16)==0 and word(changer)==run_table
        assert not events and not calls
    pending_switch=None
    if options.responder_return:
        u.mem_write(request,bytes.fromhex(responder_return_input['packet_hex']))
        for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0xfa44,0x50000000,count=30000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        assert word(changer)==0x34c24 and word(changer+4)==2 and word(changer+8)==1
        assert quit_notices==[[4,0,0]] and quit_replies==[[16,56,6,0]]
        assert not any(row['operation'] in ('launch','activate') for row in calls)
        pending_switch={'target':1,'native_request':'0xfa44','mode':1,'mode1_callback_from_original_constructor':True,'table_before_reap':hex(word(changer)),'request_input':responder_return_input}
        calls.clear()
    if options.pending_responder_switch:
        for register,value in ((UC_ARM_REG_R0,changer),(UC_ARM_REG_R1,2),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        try:u.emu_start(0x1480c,0x50000000,count=30000)
        except Exception as error:raise AssertionError((hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),calls,str(error))) from error
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
        assert word(changer)==0x34c5c and word(changer+8)==2 and word(changer+4)==app
        assert calls==[{'operation':'set_state','table':'0x34c5c'}],calls
        pending_switch={'target':2,'native_request':'0x1480c','trace':calls.copy(),'table_before_reap':hex(word(changer))}
        if options.native_stop_enumeration:
            assert quit_notices==[[4,0,0]]
            for register,value in ((UC_ARM_REG_R0,ctx),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
            u.emu_start(0xaf54,0x50000000,count=10000)
            assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==1
            assert word(changer)==0x34c5c and not any(item['operation']=='launch' for item in calls)
            pending_switch['native_busy_before_reap']=True
        calls.clear()
    phase='exit'
    for register,value in ((UC_ARM_REG_R0,ctx),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
    try:u.emu_start(0x11998,0x50000000,count=50000)
    except Exception as error:
        if manager_state:
            area=ROOT/'work/manager-return-state';area.mkdir(exist_ok=True)
            (area/'gap.json').write_text(json.dumps({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'lr':hex(u.reg_read(UC_ARM_REG_LR)),'recent':recent,'calls':calls,'events':events,'notices':notices,'removed':removed},indent=2)+'\n')
        raise
    assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    assert callbacks==[[app,1,ctx]] and removed==[app] and events==[[changer,0,app]]
    assert notices==[[9,3,app]] and word(changer+8)==return_target
    assert word(changer)==(0x34bec if running else 0x34c40)
    assert word(changer+4)==0
    expected_calls=([{'operation':'exists','target':return_target}] if not options.pending_responder_switch else [])+[{'operation':'activate' if running else 'launch','target':return_target},{'operation':'set_state','table':'0x34bec' if running else '0x34c40'}]
    assert calls==expected_calls,calls
    rows.append({'proxy_wait_status':status,'native_activation_before_exit':activation,'native_op3':{'executed':options.include_manager_op3_fixture,'part_of_proxy_shutdown':False,'request':[24,55,0,3,66,app],'observer_packets':quit_notices,'replies':quit_replies,'activated_record_preserved':True},'normal_callbacks':callbacks,'RUN_event':events,'initial_native_state_table':hex(run_table),'final_native_state_table':hex(word(changer)),'exiting_current_id_cleared':word(changer+4)==0,'walkman_running_fixture':running,'requests':calls,'next_target':word(changer+8)})
    rows[-1]['RUN_event']=events.copy();rows[-1]['requests']=calls.copy()
    rows[-1]['core_observer_packets_before_return']=[packet.copy() for packet in notices]
    if options.native_ipc_exit_cleanup:
        assert {'recipient':return_target,'packet':[5,0,0]} in native_activation_notices
        rows[-1]['native_walkman_activation']={'adapter':'0xbd54','original_activate':'0xa594','parameter_update':'0x11650','notifications':native_activation_notices.copy(),'libc_memcpy_virtual':True}
        expected_event_port=launch['second_proxy_registration']['ports'][1] if 'second_proxy_registration' in launch else 643
        assert ipc_entries_before==[[app,expected_event_port]] and ipc_entries()==[] and word(0x6000601c+12)==0
        assert ipc_cleanup_calls==[app] and [9,3,app] in notices
        rows[-1]['native_ipc_exit_cleanup']={'observer_preserved':True,'entries_before':ipc_entries_before,'entries_after':ipc_entries(),'pool_used_after':word(0x6000601c+12),'native_removed_app_ids':ipc_cleanup_calls.copy(),'queue_prefixes':ipc_cleanup_queue.copy()}
    rows[-1]['pending_responder_switch']=pending_switch
    if options.native_registry:
        assert registry_call(0x110ac,(ctx,app))==0
        if not manager_state:assert registry_call(0x110ac,(ctx,0x10001))==1
        rows[-1]['native_registry']={'app_removed_by_native_list':True,'daemon_preserved_by_native_lookup':not bool(manager_state),'initial_records_inserted_natively':not bool(manager_state),'records_imported_from_launch':bool(manager_state),'applist_IDs_seeded_from_native_parser':True,'full_registration_constructor_not_executed':True}
        if options.native_return_registry:
            count_after_reap=1 if manager_state else 2 if running else 1
            assert registry_call(0x16594,(ctx+8,0,0))==count_after_reap
            rows[-1]['native_registry'].update({'walkman_initially_present':running,'original_exists_callback':'0xbd84','count_after_reap':count_after_reap})
    if options.native_stop_enumeration:
        assert [item['procedure'] for item in native_stop_calls]==['0xae68','0xaf54','0xaf54']
        assert len(native_running_enumerations)==3 and native_running_enumerations[-1]['removed']==[app]
        rows[-1]['native_stop_enumeration']={'calls':native_stop_calls,'enumerations':native_running_enumerations,'homebrew_stop_notice':quit_notices.copy(),'daemon_id_still_present':0x10001,'registry_existence_fixture':not options.native_registry}
    events.clear();calls.clear();notices.clear();phase='walkman'
    if options.native_registry and not (options.native_return_registry and running):assert registry_call(0x1633c,(ctx+8,walkman_record))==0
    confirmation_states=[] if options.stop_before_walkman_confirmation else [2] if running else [1,2]
    for value in confirmation_states:
        packet=home_packet.copy() if value==2 and home_packet and return_target==1 else [24,90+value,return_target,1,66,value]
        u.mem_write(request,struct.pack('<6I',*packet))
        for register,argument in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,argument)
        u.emu_start(0xf75c,0x50000000,count=30000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and word(walkman_record+12)==value
        assert walkman_replies[-1]==[16,packet[1],packet[3],0]
    if options.stop_before_walkman_confirmation:
        assert word(changer+4)==0 and word(changer+8)==1 and word(walkman_record+12)==1
        assert not events and not walkman_replies
    else:
        assert word(changer)==run_table and word(changer+4)==return_target and word(changer+8)==1
        assert events==([[changer,2,return_target]] if running else [[changer,1,return_target],[changer,2,return_target]])
    if options.native_return_registry:assert registry_call(0x16594,(ctx+8,0,0))==(1 if manager_state else 2) and registry_call(0x110ac,(ctx,return_target))==1
    rows[-1]['walkman_confirmation']={'states':confirmation_states,'not_delivered':options.stop_before_walkman_confirmation,'activation_from_native_home':bool(home_packet) and return_target==1,'startup_state1_still_fixture':not running,'events':events.copy(),'replies':walkman_replies,'transitions':calls.copy(),'current_app':word(changer+4),'post_activation_fallback_target':word(changer+8),'final_table':hex(word(changer)),'display_recovery_validated':False}
    if options.native_return_registry:rows[-1]['native_registry'].update({'count_after_pending_return' if options.stop_before_walkman_confirmation else 'count_after_walkman_activation':1 if manager_state else 2,'home_record_state':word(walkman_record+12)})
    if options.usb_handoff:
        assert return_target==2 and word(ctx+0x503c)==1
        assert registry_call(0x110ac,(ctx,app))==0 and registry_call(0x110ac,(ctx,2))==1
        put(ctx+0x41c8,91) # USB descriptor from unreplayed original startup
        u.mem_write(request,struct.pack('<5I',*handoff_capture['request']))
        phase='usb-handoff'
        for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
        u.emu_start(0xfc60,0x50000000,count=30000)
        prefix=['virtual-pre-unmount-helper','sync','sync','umount:/contents']
        if options.usb_unmount_errno in (5,16):
            assert u.reg_read(UC_ARM_REG_PC)==0x1c888
            assert storage_events==prefix+['fatal-boundary:1c888'] and not handoff_replies
            assert word(ctx+0x503c)==1 and word(ctx+0x41c8+40)==5
        else:
            assert u.reg_read(UC_ARM_REG_PC)==0x50000000
            assert storage_events==prefix+['open:mgscsi','ioctl:0x40017325','close:mgscsi','ioctl:0x40046702']
            assert handoff_replies==[[16,56,10,0]] and word(ctx+0x503c)==2
        rows[-1]['same_memory_usb_handoff']={'request_capture':handoff_capture,'homebrew_absent_before_unmount':True,'responder_present_before_unmount':True,'events':storage_events,'replies':handoff_replies,'final_core_state':word(ctx+0x503c),'supplied_unmount_errno':options.usb_unmount_errno,'returned_normally':u.reg_read(UC_ARM_REG_PC)==0x50000000}
report={'scope':__doc__,'proxy_exit_report_sha256':hashlib.sha256(captured).hexdigest(),'proxy_activation_report_sha256':hashlib.sha256(launch_bytes).hexdigest(),'native_home_input':home_input,'sysmgrd_sha256':digest,'cases':rows,
        'physical_device_access':False,'Sony_return_validated':False,'proxy_quit_wire_to_manager_op3_verified':False,
        'limits':['Default path does not call managerop3: original proxy sends8-byte self-event shutdown then exits. Optional managerop3 is an independent diagnostic fixture only. Registry lookup and wait records virtual.',
                  'Initial WaitActive and core state2 supplied; captured proxy activation request feeds originalf75c/c86c/11558, b614 emits event2 and original14758/14fc8/1485c enter RUN. IPC transport virtual; request bytes come from separate original proxy replay.',
                  'Walkman state2 comes from bounded native Home recovery replay when native_home_input is present; otherwise supplied. Startup state1 remains supplied; no real Walkman process or transport.',
                  'Activation/launch callbacks virtual; native manager returns current app1/RUN after supplied acknowledgements, no player rendering, hardware or USB/sleep qualification.']}
if options.pending_responder_switch:
    report['scope']='Original target2 request from RUN -> special transition -> Homebrew reaped -> Responder launch/confirmation; supporting predicates/services supplied, not USB hardware'
    report['limits'].append('Target2 uses special34c5c state, not ordinary34c24 wait-inactive. Original bd94/af54 all-apps-stopped predicate returns supplied0, bd9c/ae68 stop orchestration supplied. No USB interrupt, actual stop-all or Responder storage export executed; confirmations are fixtures.')
    report['limits']=[line.replace('native manager returns current app1/RUN after supplied acknowledgements','native manager returns current app2/RUN after supplied acknowledgements') for line in report['limits']]
    for row in rows:row['responder_confirmation']=row.pop('walkman_confirmation')
if options.native_stop_enumeration:
    report['limits']=[line.replace('Original bd94/af54 all-apps-stopped predicate returns supplied0, bd9c/ae68 stop orchestration supplied.','Original bd94/af54 and bd9c/ae68 execute; AppList/existence queries remain supplied.') for line in report['limits']]
    report['limits'].append('ae68/a4d8/af54/11858 execute; static AppList IDs and active-registry lookup supplied. Homebrew is active initially and daemon10001 stays active after reaping; native filter ignores class1 for Responder gate. No actual process stop or USB export.')
if options.native_registry:
    report['limits']=[line.replace('Registry lookup and wait records virtual.','Wait records supplied; linked-list registry lookup/removal native.').replace('static AppList IDs and active-registry lookup supplied.','AppList IDs seeded from native parser; active-registry operations execute natively.').replace('AppList/existence queries remain supplied.','AppList IDs supplied from parser; native enumeration and existence queries execute.') for line in report['limits']]
    report['limits'].append('Native162b4/1633c/16510/16594/163dc/110ac/15b70 execute; locks remain virtual, AppList record IDs seeded from captured original parser, initial process/daemon records and post-launch Responder insertion explicitly scheduled. Full IPC registration/startup not executed.')
report['core_state_fixture']=options.core_state
filename='native-proxy-manager-saved-state-return.json' if manager_state else 'native-proxy-manager-walkman-native-registry.json' if options.native_return_registry else 'native-proxy-manager-responder-native-registry.json' if options.native_registry else 'native-proxy-manager-responder-native-stop.json' if options.native_stop_enumeration else 'native-proxy-manager-responder.json' if options.pending_responder_switch else 'native-proxy-manager-return.json'
if options.core_state!=2:
    filename=filename.replace('.json','-core-state1.json')
    report['limits']=[item.replace('core state2 supplied','core state1 supplied') for item in report['limits']]
    report['limits'].append('Core state1 was explicitly supplied for consistency with pre-unmount service; it is not derived from full stock boot.')
if options.usb_handoff:
    filename='native-proxy-manager-responder-usb-handoff.json'
    if options.usb_unmount_errno:filename=filename.replace('.json','-errno'+str(options.usb_unmount_errno)+'.json')
    report['limits'].append('Same manager memory continues from original reaper/registry and supplied Responder confirmations to captured op10/fc60/unmount/allow. Initial USB descriptor91, pre-unmount helper13680, libc effects and IPC scheduling remain fixtures; kernel callbacks/physical USB not executed.')
if options.responder_return:
    filename='native-manager-responder-return-walkman.json'
    report['scope']='Captured original Responder op6 -> original manager quit request/wait-state -> native reaper -> SpiderApp startup/activation confirmations'
    report['responder_return_input']=responder_return_input
    report['responder_activation_report_sha256']=hashlib.sha256(client_bytes).hexdigest()
    report['limits'].append('Responder is app2; its activation packet comes from original client report, normal exit status0 is supplied. Original fa44/cddc/mode1 quit/registry/reaper execute; real Responder exit, IPC delivery and SpiderApp launch/confirmations are virtual. Homebrew/proxy exit reports are existing dependencies, not proof of a physical Responder process exit.')
if options.native_return_registry:
    report['native_return_registry']=True
    report['limits']=[line.replace('post-launch Responder insertion','post-launch Walkman insertion') for line in report['limits']]
    report['limits'].append('Ordinary Walkman return uses constructor-selected bd84/110ac and actual registry insert/find/remove/count; Home presence/PID/state and later startup record insertion remain scheduled fixtures. No Responder/USB flow is enabled.')
if manager_state:
    report['domain_preservation_checked']=True
    report['activation_replayed']=False
    report['limits']=[line.replace('Initial WaitActive and core state2 supplied; captured proxy activation request feeds originalf75c/c86c/11558, b614 emits event2 and original14758/14fc8/1485c enter RUN. IPC transport virtual; request bytes come from separate original proxy replay.','RUN/current/core and registry state imported from the captured launch; no activation replay. I/O readiness and callback service bindings remain supplied.').replace('initial process/daemon records and post-launch Walkman insertion explicitly scheduled.','records imported from saved launch memory, not reconstructed or reinserted in this mode.') for line in report['limits']]
    report['manager_state_input']={'report':options.manager_state_report,'report_sha256':hashlib.sha256(launch_bytes).hexdigest(),'state':manager_state,'domain_fields_preserved':domain_before}
    report['limits'].append('Imports model RAM at function boundaries, not a CPU/thread snapshot. Keeps AppList, records, RUN/current/pending fields; virtual I/O/observer/launch services are rebound. No initial record reconstruction or activation replay in this mode.')
if options.native_ipc_exit_cleanup:
    report['native_ipc_callbacks_preserved']={'observer':'0xf298','direct_notification':'0xf314','context':'0x60006000','walkman_activation_adapter':'0xbd54'}
    report['limits']=[line.replace('Activation/launch callbacks virtual;','Original bd54/a594/11650 Walkman activation and notification execute; launch callback and libc memcpy virtual;').replace('virtual I/O/observer/launch services are rebound.','virtual I/O/launch services are rebound; original IPC observer and direct notification callbacks preserved.').replace('Full IPC registration/startup not executed.','IPC registration comes from imported native launch; full system startup not executed.') for line in report['limits']]
if options.stop_before_walkman_confirmation:
    report['scope']='Captured proxy exit -> original reaper/registry -> Walkman activation request; stops before recovery confirmation'
    report['stop_before_walkman_confirmation']=True
    report['limits']=[line.replace('Walkman state2 comes from bounded native Home recovery replay when native_home_input is present; otherwise supplied. Startup state1 remains supplied; no real Walkman process or transport.','Walkman confirmation is not supplied; existing record remains state1, no real Walkman process/rendering.').replace('Activation/launch callbacks virtual; native manager returns current app1/RUN after supplied acknowledgements, no player rendering, hardware or USB/sleep qualification.','Activation callback virtual; manager waits with current app0/target1. No recovery acknowledgement, rendering, hardware or USB/sleep qualification.') for line in report['limits']]
output=ROOT/'sources'/filename
if options.report:
    output=(ROOT/options.report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
    report['all_bounded_checks_passed']=True
    report['source_hashes']={options.proxy_exit_report:hashlib.sha256(captured).hexdigest(),options.launch_report:hashlib.sha256(launch_bytes).hexdigest(),'tools/check_proxy_manager_return.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if home_input:report['source_hashes'][home_input['path']]=home_input['sha256']
    if manager_state:
        report['source_hashes'][manager_state['path']]=manager_state['sha256']
        for region in manager_state['module_regions']:report['source_hashes'][region['path']]=region['sha256']
    if options.native_return_registry:report['source_hashes']['sources/native-applist-full-config.json']=hashlib.sha256((ROOT/'sources/native-applist-full-config.json').read_bytes()).hexdigest()
if options.save_return_state:
    assert options.report and manager_state and home_input and len(rows)==1
    assert rows[0]['walkman_confirmation']['current_app']==1 and word(walkman_record+12)==2
    folder=ROOT/'work/native-manager-states'/(ROOT/'VERSION').read_text().strip();folder.mkdir(parents=True,exist_ok=True)
    saved=bytes(u.mem_read(0x60000000,0x20000));path=folder/(output.stem+'-returned.bin');path.write_bytes(saved)
    regions=[]
    for original in manager_state['module_regions']:
        address=int(original['address'],0);data=bytes(u.mem_read(address,original['bytes']))
        region_path=folder/(output.stem+'-returned-module-'+str(len(regions))+'.bin');region_path.write_bytes(data)
        regions.append({'path':str(region_path.relative_to(ROOT)),'address':hex(address),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    report['returned_manager_state']={'path':str(path.relative_to(ROOT)),'base':'0x60000000','bytes':len(saved),'sha256':hashlib.sha256(saved).hexdigest(),'home_record':hex(walkman_record),'current_app':1,'home_record_state':2,'module_regions':regions,'scope':'Model RAM after native Home confirmation; not device memory.'}
    report['source_hashes'][str(path.relative_to(ROOT))]=hashlib.sha256(saved).hexdigest()
    for region in regions:report['source_hashes'][region['path']]=region['sha256']
output.write_text(json.dumps(report,indent=2)+'\n')
print('Proxy exit -> native reaper -> Walkman activation requested; confirmation not supplied' if options.stop_before_walkman_confirmation else 'Captured Responder return request -> native quit/reap -> SpiderApp confirmations: passed' if options.responder_return else 'Proxy exit -> native manager dispatch -> '+('pending Responder preserved' if options.pending_responder_switch else 'Walkman return')+': passed')
