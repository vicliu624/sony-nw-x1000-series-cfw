"""Continue returned manager/argv-query instance with actual second Home switch request."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,runpy,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'tools/check_saved_manager_arguments.py'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native-ipc',action='store_true');options=parser.parse_args()
inputs={'return_report':'sources/native-ipc-manager-return.json','output_report':'sources/native-ipc-saved-manager-arguments.json'} if options.native_ipc else {}
with contextlib.redirect_stdout(io.StringIO()):model=runpy.run_path(str(base),init_globals=inputs)
u=model['manager'];u.hook_del(model['manager_hook_id'])
source=ROOT/'sources/native-home-parent-activation-route-frame-receiver.json';home=verify_report(ROOT,str(source.relative_to(ROOT)))
requests=[bytes.fromhex(c['native_switch_wire_requests'][-1]['packet_hex']) for c in home['cases'] if c['rebuild_cycle']==1]
assert len(requests)==2 and requests[0]==requests[1]
packet=requests[0];words=list(struct.unpack('<8I',packet[:32]));assert words==[1060,8,1,6,55,0x30001,0,0]
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
core=0x60000000;changer=core+0x4b88;service,request=model['service'],model['request']
assert word(changer+4)==1 and word(0x60010000+12)==2
if options.native_ipc:
    assert word(core+0x51b4)==0xf298 and word(core+0x51b8)==0x60006000
    assert word(0x60006018)==0 and word(0x60006028)==0
before_table=word(changer);record_before=bytes(u.mem_read(0x60010000,256))
callback=word(core+0x51bc);assert callback==(0xf314 if options.native_ipc else 0x50000500)
# Return replay rebound the deactivate service to a virtual callback. Restore
# the constructor-selected stock adapter for this next request, not domain state.
assert word(changer+0x4a0)==0x50000600
u.mem_write(changer+0x4a0,struct.pack('<I',0xbd74))
notices=[];replies=[];observer_packets=[];recent=[]
symbols={s.name:s['st_value'] for s in model['elf'].get_section_by_name('.dynsym').iter_symbols()}
second_ack_running=False;proxy_register_running=False;framing_running=False;proxy_activation_running=False
forks=[];commands=[];registration_replies=[];event_queue=[];event_frames=[];activation_replies=[]
def cstr(p):return bytes(u.mem_read(p,1024)).split(b'\0',1)[0].decode()
def hook(uc,pc,size,data):
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    recent.append(hex(pc))
    if len(recent)>24:recent.pop(0)
    if second_ack_running and pc==0x11184:
        tokens=[]
        for i in range(8):
            pointer=word(a[0]+4*i)
            if not pointer:break
            tokens.append(cstr(pointer))
        commands.append(tokens);return
    if pc==callback:
        payload=list(struct.unpack('<3I',uc.mem_read(a[0],12)))
        assert (a[1],payload) in ((1,[6,0,0]),(0x30001,[5,0,0]));notices.append({'recipient':a[1],'packet':payload})
        if options.native_ipc:return
    elif pc==0x16d18:
        if framing_running:
            assert a[0]==44 and a[1] in (643,645) and a[3]==20;event_frames.append({'port':a[1],'bytes':bytes(uc.mem_read(a[2],20))})
        elif proxy_activation_running:
            assert a[:2]==[44,644] and a[3]==16;activation_replies.append(bytes(uc.mem_read(a[2],16)))
        elif proxy_register_running:
            assert a[:2]==[44,644] and a[3]==20;registration_replies.append(bytes(uc.mem_read(a[2],20)))
        else:
            assert a[:2]==[44,55] and a[3]==16;replies.append(list(struct.unpack('<4I',uc.mem_read(a[2],16))))
    elif options.native_ipc and pc==0xf298:
        observer_packets.append(list(struct.unpack('<3I',uc.mem_read(a[0],12))));return
    elif pc==0x50000100:
        payload=list(struct.unpack('<3I',uc.mem_read(a[0],12)));assert payload[0]==9;observer_packets.append(payload)
    elif (framing_running or options.native_ipc) and pc==0x1967c:
        assert a[2:]==[52,0];event_queue.append(bytes(uc.mem_read(a[1],52)))
    elif framing_running and pc==0x1978c:
        if not event_queue:uc.emu_stop();return
        uc.mem_write(a[1],event_queue.pop(0))
    elif second_ack_running and pc==symbols['fork']:
        forks.append(322);uc.reg_write(UC_ARM_REG_R0,322);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    elif second_ack_running and pc==0x1b858:
        if options.native_ipc and a[0]==0x6000601c:return
        uc.reg_write(UC_ARM_REG_R0,0x60014100 if proxy_register_running else 0x60010100);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    elif second_ack_running and pc==0x11538:
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    elif second_ack_running and pc==symbols['strlen']:
        uc.reg_write(UC_ARM_REG_R0,len(cstr(a[0])));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    elif second_ack_running and pc==symbols['memcpy']:
        uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    elif second_ack_running and pc==0x1b3c8:
        text=cstr(a[2]).encode()+b'\0';assert len(text)<=a[1];uc.mem_write(a[0],text)
    elif pc not in (0x1a4f0,0x1a508,0xa188,0x1c4d0,0xa30c) and not(second_ack_running and pc==0x11650):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.mem_write(request,packet)
for r,v in ((UC_ARM_REG_R0,service),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
try:u.emu_start(0xfa44,0x50000000,count=30000)
except Exception:
    (ROOT/'work/second-entry-model-gap.json').write_text(json.dumps({'recent':recent,'pc':hex(u.reg_read(UC_ARM_REG_PC)),'scope':'Model continuation failure, not a device fault'},indent=2)+'\n');raise
assert u.reg_read(UC_ARM_REG_PC)==0x50000000
assert notices==[{'recipient':1,'packet':[6,0,0]}] and replies==[[16,8,6,0]]
assert word(changer+8)==0x30001 and word(changer)!=before_table
assert bytes(u.mem_read(0x60010000,256))==record_before
waiting_table=word(changer)
pending_after_request=word(changer+8)
# Restore the stock launch adapter selected by the original constructor.
assert word(changer+0x494)==0x50000200
assert word(0x211dc)==0xbd24
u.mem_write(changer+0x494,struct.pack('<I',word(0x211dc)))
acknowledgements=[c['native_manager_close']['apf_ack_requests'][0] for c in home['cases'] if c['rebuild_cycle']==1]
assert len(acknowledgements)==2 and acknowledgements[0]==acknowledgements[1]==[24,10,1,1,55,1]
u.mem_write(request,struct.pack('<6I',*acknowledgements[0]));second_ack_running=True
for r,v in ((UC_ARM_REG_R0,service),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
try:u.emu_start(0xf75c,0x50000000,count=50000)
except Exception:
    (ROOT/'work/second-entry-ack-model-gap.json').write_text(json.dumps({'recent':recent,'pc':hex(u.reg_read(UC_ARM_REG_PC)),'registers':{name:hex(u.reg_read(r)) for name,r in [('r0',UC_ARM_REG_R0),('r1',UC_ARM_REG_R1),('r2',UC_ARM_REG_R2),('r3',UC_ARM_REG_R3)]},'scope':'Model continuation failure, not device fault'},indent=2)+'\n');raise
assert u.reg_read(UC_ARM_REG_PC)==0x50000000
assert replies==[[16,8,6,0],[16,10,1,0]]
assert forks==[322] and commands==[['appproxy','/contents/HOMEBREW/launcher/app','--native']]
target_after_launch=[word(0x60010100+i) for i in (4,8,12)]
assert word(0x60010000+12)==1 and target_after_launch==[322,0x30001,0]
assert word(changer+0x49c)==(0xbd54 if options.native_ipc else 0x50000300) and word(0x211dc+8)==0xbd54
u.mem_write(changer+0x49c,struct.pack('<I',word(0x211dc+8)))
proxy_path=ROOT/'work/targets-jp/appproxy';proxy_raw=proxy_path.read_bytes()
assert hashlib.sha256(proxy_raw).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
p=Uc(UC_ARCH_ARM,UC_MODE_ARM);p.mem_map(0x8000,0x40000)
proxy_elf=ELFFile(io.BytesIO(proxy_raw))
for segment in proxy_elf.iter_segments():
    if segment['p_type']=='PT_LOAD':p.mem_write(segment['p_vaddr'],segment.data())
p.mem_map(0x50000000,4096);p.mem_map(0x60000000,0x30000)
proxy_symbols={s.name:s['st_value'] for s in proxy_elf.get_section_by_name('.dynsym').iter_symbols()}
proxy_context=0x1ca5c;proxy_packets=[];opened_ports=[];thread_requests=[]
proxy_mode='registration';proxy_event_received=False;proxy_back_to_receive=False;frontend_forks=[];frontend_exec=[]
def proxy_hook(uc,pc,size,data):
    global proxy_event_received,proxy_back_to_receive
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
    if pc==proxy_symbols['getpid']:result=322
    elif pc==0xd258:
        opened_ports.append(a[1]);uc.mem_write(a[0],struct.pack('<I',499+len(opened_ports)))
    elif pc==0xd2c0:
        assert a[:2]==[500,55];data=bytes(uc.mem_read(a[2],a[3]));proxy_packets.append(data)
        assert a[3]==(24 if proxy_mode=='activation' else 32)
        u.mem_write(0x6001b000,data)
        for r,v in ((UC_ARM_REG_R0,0x60006000),(UC_ARM_REG_R1,0x6001b000),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
        u.emu_start(0xf75c if proxy_mode=='activation' else 0xf584,0x50000000,count=30000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    elif pc==0xd36c:
        if proxy_mode=='activation' and a[0]==501:
            assert a[2]==256
            if proxy_event_received and (not options.native_ipc or not proxy_pending_frames):proxy_back_to_receive=True;uc.emu_stop();return
            frame=proxy_pending_frames.pop(0) if options.native_ipc else next(item['bytes'] for item in event_frames if item['port']==645)
            uc.mem_write(a[1],frame);uc.mem_write(a[3],struct.pack('<I',len(frame)));proxy_event_received=True
        else:
            response=activation_replies[0] if proxy_mode=='activation' else registration_replies[0]
            assert a[0]==500 and a[2]==len(response)
            uc.mem_write(a[1],response);uc.mem_write(a[3],struct.pack('<I',len(response)))
    elif proxy_mode=='activation' and pc==proxy_symbols['fork']:
        assert struct.unpack('<I',uc.mem_read(proxy_context+4,4))[0]==2 and word(0x60010100+12)==2
        frontend_forks.append(0);result=0
    elif proxy_mode=='activation' and pc==proxy_symbols['execvp']:
        path=bytes(uc.mem_read(a[0],256)).split(b'\0',1)[0].decode();argv=[]
        for i in range(8):
            pointer=struct.unpack('<I',uc.mem_read(a[1]+4*i,4))[0]
            if not pointer:break
            argv.append(bytes(uc.mem_read(pointer,256)).split(b'\0',1)[0].decode())
        assert path=='/contents/HOMEBREW/launcher/app' and argv==commands[0][1:]
        frontend_exec.append({'path':path,'argv':argv});uc.emu_stop();return
    elif options.native_ipc and pc==0xe960:uc.mem_write(a[0],struct.pack('<I',0x6002a000))
    elif pc==0xe534:
        assert a[:2]==[0x9b40,proxy_context];thread_requests.append(hex(a[0]));out=struct.unpack('<I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),4))[0];uc.mem_write(out,struct.pack('<I',1234))
    elif pc not in (0xea80,0xeae8,0x98bc,0xf840):return
    uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
p.hook_add(UC_HOOK_CODE,proxy_hook);p.mem_write(0x1ca40,struct.pack('<I',proxy_context))
if options.native_ipc:
    p.reg_write(UC_ARM_REG_R0,proxy_context);p.reg_write(UC_ARM_REG_SP,0x60028000);p.reg_write(UC_ARM_REG_LR,0x50000000)
    p.emu_start(0x9904,0x50000000,count=10000);assert p.reg_read(UC_ARM_REG_PC)==0x50000000
for event,callback_address in ((4,0x95c0),(5,0x95c4),(6,0x969c)):
    for r,v in ((UC_ARM_REG_R0,proxy_context),(UC_ARM_REG_R1,event),(UC_ARM_REG_R2,callback_address),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):p.reg_write(r,v)
    p.emu_start(0x9d64,0x50000000,count=10000);assert p.reg_read(UC_ARM_REG_PC)==0x50000000
    assert struct.unpack('<I',p.mem_read(proxy_context+0x2c+event*4,4))[0]==callback_address
proxy_register_running=True
p.reg_write(UC_ARM_REG_R0,proxy_context);p.reg_write(UC_ARM_REG_SP,0x60028000);p.reg_write(UC_ARM_REG_LR,0x50000000)
p.emu_start(0xcdec,0x50000000,count=200000);assert p.reg_read(UC_ARM_REG_PC)==0x50000000 and p.reg_read(UC_ARM_REG_R0)==0
assert opened_ports==[644,645] and list(struct.unpack('<8I',proxy_packets[0]))==[32,0,0,0,644,645,322,0x10010001]
assert list(struct.unpack('<5I',registration_replies[0]))==[20,0,0,0,0x30001]
assert word(0x60010100+12)==1 and notices[-1]=={'recipient':0x30001,'packet':[5,0,0]}
assert struct.unpack('<I',p.mem_read(proxy_context+4,4))[0]==1 and thread_requests==['0x9b40']
framing_running=True
u.mem_write(0x6001c000,struct.pack('<3I',*notices[-1]['packet']))
frame_calls=[(0xf0fc,(0x60006000,))] if options.native_ipc else [(0xf314,(0x6001c000,0x30001,0x60006000)),(0xf0fc,(0x60006000,))]
for entry,args in frame_calls:
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(r,v)
    u.reg_write(UC_ARM_REG_SP,0x6001f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    u.emu_start(entry,0x50000000,count=30000)
    assert u.reg_read(UC_ARM_REG_PC)==(0x1978c if entry==0xf0fc else 0x50000000)
framing_running=False
assert {item['port'] for item in event_frames}==({645} if options.native_ipc else {643,645})
if options.native_ipc:
    proxy_pending_frames=[item['bytes'] for item in event_frames if item['port']==645]
    assert sum(struct.unpack('<5I',frame)[2]==5 for frame in proxy_pending_frames)==1
    assert word(0x60006028)==1
else:assert all(item['bytes']==struct.pack('<5I',20,0,5,0,0) for item in event_frames)
proxy_mode='activation';proxy_activation_running=True
vector,cursor=0x60020000,0x60021000
for i,token in enumerate(commands[0]):
    p.mem_write(vector+i*4,struct.pack('<I',cursor));encoded=token.encode()+b'\0';p.mem_write(cursor,encoded);cursor+=len(encoded)
p.mem_write(vector+len(commands[0])*4,bytes(4))
p.reg_write(UC_ARM_REG_R6,vector);p.reg_write(UC_ARM_REG_R4,0x1ca44)
p.emu_start(0x9778,0x9790,count=32);assert p.reg_read(UC_ARM_REG_PC)==0x9790
p.reg_write(UC_ARM_REG_R0,proxy_context);p.reg_write(UC_ARM_REG_SP,0x60028000);p.reg_write(UC_ARM_REG_LR,0x50000000)
p.emu_start(0x9b40,0x50000000,count=200000)
assert proxy_event_received and frontend_forks==[0] and len(frontend_exec)==1 and p.reg_read(UC_ARM_REG_PC)==proxy_symbols['execvp']
assert list(struct.unpack('<6I',proxy_packets[-1]))==[24,1,0x30001,1,644,2]
assert list(struct.unpack('<4I',activation_replies[0]))==[16,1,1,0]
assert word(0x60010100+12)==2 and word(changer+4)==0x30001
assert struct.unpack('<I',p.mem_read(proxy_context+4,4))[0]==2
paths=[Path(__file__),base,source,proxy_path,*model['paths']]
folder=ROOT/'work/native-manager-states'/(ROOT/'VERSION').read_text().strip();folder.mkdir(parents=True,exist_ok=True)
label='native-ipc-second-entry-run' if options.native_ipc else 'second-entry-run'
saved_path=folder/(label+'.bin');saved=bytes(u.mem_read(core,0x20000));saved_path.write_bytes(saved);paths.append(saved_path)
saved_regions=[]
for original in model['state']['module_regions']:
    address=int(original['address'],0);data=bytes(u.mem_read(address,original['bytes']))
    path=folder/(label+'-module-'+str(len(saved_regions))+'.bin');path.write_bytes(data);paths.append(path)
    saved_regions.append({'path':str(path.relative_to(ROOT)),'address':hex(address),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
report={'all_bounded_checks_passed':True,'request_words':words,'reply':replies[0],
        'notifications':notices,'pending_target':hex(pending_after_request),
        'state_table_before':hex(before_table),'state_table_after_request':hex(waiting_table),'state_table_after':hex(word(changer)),
        'same_returned_manager_instance':True,'home_record_unchanged_until_ack':True,
        'stock_deactivate_adapter_restored':'0xbd74','observer_packets':observer_packets,
        'second_inactive_ack':acknowledgements[0],'ack_reply':replies[-1],
        'second_native_launch_commands':commands,'virtual_fork_pids':forks,
        'stock_launch_adapter_restored':'0xbd24',
        'target_record_after_launch':target_after_launch,
        'second_proxy_registration':{'request_words':list(struct.unpack('<8I',proxy_packets[0])),'reply_words':list(struct.unpack('<5I',registration_replies[0])),'ports':opened_ports,'receiver_thread_requests':thread_requests,'client_state':1,'native_callback_registration':True,'old_port_entry_retained':word(0x60014000+8)==643},
        'second_proxy_activation':{'frames':[{'port':f['port'],'hex':f['bytes'].hex()} for f in event_frames],'request':list(struct.unpack('<6I',proxy_packets[-1])),'reply':list(struct.unpack('<4I',activation_replies[0])),'proxy_state':2,'manager_record_state':2,'current_app':word(changer+4),'frontend_virtual_child_forks':frontend_forks,'captured_frontend_exec_requests':frontend_exec,'stopped_before_exec':True},
        'sysmgrd_sha256':'131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0','appproxy_sha256':hashlib.sha256(proxy_raw).hexdigest(),
        'native_manager_state':{'path':str(saved_path.relative_to(ROOT)),'base':'0x60000000','bytes':len(saved),'sha256':hashlib.sha256(saved).hexdigest(),'home_record':'0x60010000','target_record':'0x60010100','current_app':0x30001,'pid':322,'module_regions':saved_regions,'scope':'Second native activation RUN model, not device memory.'},
        'cases':[{'target':'0x30001','proxy_registration':{'activation':{'proxy_requests':[list(struct.unpack('<6I',proxy_packets[-1]))]}}}],
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limits':['Continues original-manager return snapshot and argv-query instance; no record reconstruction.',
                  'Second request captured from separate original Home replay, copied via virtual transport.',
                  'Notification/observer callbacks,logging,locks,a30c readiness flush,launch permission,record allocation,fork and reply virtual.',
                  'Original second launch/registration/activation and exec-argv preparation execute; fork child0 virtual, stops before exec. Old virtual port entry retained; real IPC cleanup not established.',
                  'No full boot, real IPC, device execution or storage writes.']}
if options.native_ipc:
    report['native_ipc_service']={'constructor':'0xefd4','observer':'0xf298','direct_notification_callback':hex(callback),'explicit_activation_enqueue':False,'activation_frames':sum(struct.unpack('<5I',f['bytes'])[2]==5 for f in event_frames),'port_pool_used':word(0x60006028),'port_pool_capacity':word(0x60006024)}
    report['second_proxy_registration']['old_port_entry_retained']=False
    report['limits']=[line.replace('Old virtual port entry retained; real IPC cleanup not established.','First return removed old port registration; second registration uses native32-slot pool and frames reach only new port645.').replace('record allocation,fork and reply virtual.','process-record allocation,fork and reply virtual; IPC port pool allocation native in this variant.') for line in report['limits']]
    report['limits'].append('Native IPC observer/pool preserved across first return and second registration; original f314 direct notification callback preserved and executed; no explicit activation enqueue. Native default proxy callbacks handle all queued state broadcasts.')
(ROOT/('sources/native-manager-native-ipc-second-entry.json' if options.native_ipc else 'sources/native-manager-second-entry.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Second native proxy activation reaches child execvp boundary; actual frontend path/argv captured')
