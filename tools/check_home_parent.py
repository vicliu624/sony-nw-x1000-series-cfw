"""Original Home descriptor -> parent/grid construction -> list initialization.

Pool/libc/rectangle allocation are virtual. No drawing, physical I/O or firmware output.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
import re
from native_alarm_fixture import create as create_alarm_manager
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reverse-equal-sort', action='store_true',
                    help='Reverse equal-key input order before virtual sorting; preserve comparator order.')
parser.add_argument('--touch-outside', action='store_true',
                    help='Touch screen corner outside the new-entry bounds; require no selection or switch.')
parser.add_argument('--close-gui', action='store_true',
                    help='After native input/selection replay, execute original GUI-manager close on constructed Home.')
parser.add_argument('--close-manager', action='store_true',
                    help='Execute native whole UI-manager close, with virtual mappings/fd and final presentation.')
parser.add_argument('--consume-manager-close', action='store_true',
                    help='Run native GUI command6 and its consumer through actual manager cleanup; implies --close-manager.')
parser.add_argument('--ack-manager-close', action='store_true',
                    help='Continue native cleanup completion through pending collection/main/APF ack; transport virtual.')
parser.add_argument('--reopen-home',action='store_true',help='Close GUI page and rebuild Home twice in the same emulator; full manager reopen excluded.')
parser.add_argument('--native-open-root',action='store_true',help='Build mode0 reserved root before Home; stop original open before module startup.')
parser.add_argument('--native-open-complete',action='store_true',help='Execute outer mode0 open through module-start calls and return; virtual display/backing.')
parser.add_argument('--reopen-manager',action='store_true',help='Two mode0 open/Home/whole-manager close cycles in one emulator; OS services virtual.')
parser.add_argument('--command7-reopen',action='store_true',help='Drive second input restore from original GUI command7; rebuild backend remains harness boundary.')
parser.add_argument('--command7-worker',action='store_true',help='Replay original GUI resume worker and GUI completion after reconstruction; services virtual.')
parser.add_argument('--command7-ack',action='store_true',help='Consume actual resume completion through coordinator/APF activation ack; transport virtual.')
parser.add_argument('--native-page-rebuild',action='store_true',help='Execute original12ef8 orchestration and mode0 open; auxiliary subsystems/frame factory virtual.')
parser.add_argument('--native-recovery-frames',action='store_true',help='Construct original two recovery frames and image resources; allocator/syscalls virtual.')
parser.add_argument('--native-resource-catalog',action='store_true',help='Initialize original resource catalog; file enumeration supplied as unavailable.')
parser.add_argument('--native-home-assets',action='store_true',help='Load real group0 assets natively in the Home return replay; virtual file/allocator.')
parser.add_argument('--native-asset-handoff',action='store_true',help='Release assets through original command6 service and reload for return; virtual OS.')
parser.add_argument('--stock-resource-pools',action='store_true',help='Execute original resource-manager initialization16 groups/1024 images, no supplied pool capacities.')
parser.add_argument('--native-worker-assets',action='store_true',help='Original resume worker loads its eight DAT groups before rebuilding Home; mode fixture0.')
parser.add_argument('--native-cancel-predicate',action='store_true',help='Use original restore cancellation query on native initialized ticket; no cancellation in this Home case.')
parser.add_argument('--native-frame-update',action='store_true',help='Execute native view binding/frame processing to e8ed8, before receiver scheduling; float helpers virtual, not display qualification.')
parser.add_argument('--native-frame-receiver',action='store_true',help='Continue full frame function through original receiver/resource queue scheduling; experimental, no hardware qualification.')
parser.add_argument('--native-switch-client',action='store_true',help='Execute original APF switch packet construction before command6 cleanup, keeping client sequence; virtual transport.')
parser.add_argument('--native-name-lookup',action='store_true',help='Feed original Home name-query packet through original manager lookup over parser records; implies native switch client.')
parser.add_argument('--native-activation-route',action='store_true',help='Original activation callback/root dispatcher/coordinator enters GUI resume; other module services virtual.')
parser.add_argument('--three-home-cycles',action='store_true',help='Three Home cycles in one model per menu, producing a second native recovery confirmation.')
parser.add_argument('--activation-frame-report',help='Use captured original manager activation frame in Home receiver; offline transport only.')
args = parser.parse_args()
activation_frame_input=None
if args.activation_frame_report:
    from evidence_checks import verify_report
    frame_path=(ROOT/args.activation_frame_report).resolve();assert frame_path.is_relative_to(ROOT/'sources')
    frame_source=verify_report(ROOT,args.activation_frame_report)
    activation_frame_words=list(struct.unpack('<5I',bytes.fromhex(frame_source['notification_hex'])))
    assert activation_frame_words==[20,0,5,0,0]
    activation_frame_input={'path':args.activation_frame_report,'sha256':hashlib.sha256(frame_path.read_bytes()).hexdigest()}
    args.native_activation_route=True
if args.three_home_cycles:args.native_activation_route=True
if args.native_activation_route:args.native_name_lookup=True;args.native_frame_receiver=True
lookup_config=None;lookup_source=None
if args.native_name_lookup:
    from native_lookup_fixture import lookup
    args.native_switch_client=True
    version=(ROOT/'VERSION').read_text().strip();path=ROOT/'work'/('integration-'+version)/'system-overlay/etc/AppList.conf';content=path.read_bytes()
    manifest=json.loads((ROOT/'work'/('integration-'+version)/'manifest.json').read_text())
    assert hashlib.sha256(content).hexdigest()==next(row['sha256'] for row in manifest['files'] if row['path']=='system-overlay/etc/AppList.conf')
    lookup_config=content
    lookup_source={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(content).hexdigest()}
if args.native_switch_client:
    if args.native_name_lookup and args.native_frame_receiver:
        assert not any((args.reopen_home,args.reopen_manager,args.command7_reopen,args.native_frame_update,args.touch_outside))
    else:assert not any((args.reopen_home,args.reopen_manager,args.command7_reopen,args.native_frame_receiver,args.native_frame_update,args.touch_outside))
    args.ack_manager_close=True
if args.native_frame_receiver:args.native_frame_update=True
if args.native_frame_update:args.native_cancel_predicate=True
if args.native_cancel_predicate:args.native_worker_assets=True
if args.native_worker_assets:args.stock_resource_pools=True
if args.stock_resource_pools:args.native_asset_handoff=True
if args.native_asset_handoff:args.native_home_assets=True
if args.native_home_assets:args.native_resource_catalog=True
if args.native_resource_catalog:args.native_recovery_frames=True
if args.native_recovery_frames:args.native_page_rebuild=True
if args.native_page_rebuild:args.command7_ack=True
if args.command7_ack:args.command7_worker=True
if args.command7_worker:args.command7_reopen=True
if args.command7_reopen:args.reopen_manager=True;args.ack_manager_close=True
if args.reopen_manager:
    assert not args.close_gui and not args.reopen_home
    args.native_open_complete=True;args.close_manager=True
if args.native_open_complete:args.native_open_root=True
assert not (args.native_open_root and args.reopen_home)
if args.reopen_home:
    assert not args.consume_manager_close and not args.ack_manager_close and not args.close_manager
    args.close_gui=True
if args.ack_manager_close:
    args.consume_manager_close = True
if args.consume_manager_close:
    args.close_manager = True
assert not (args.close_gui and args.close_manager)
manifest = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text())
raw = (ROOT / manifest['artifact']).read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == manifest['candidate_sha256']
style = (ROOT / 'work/resource-analysis/style.dat').read_bytes()
assert hashlib.sha256(style).hexdigest() == '84c29fb6747390c92ac28e9b3cab3410c2af28d40d12da83890b8c2d189a6635'
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
asset_data=(ROOT/'work/resource-analysis/TEXGRP00.DAT').read_bytes() if args.native_home_assets else b''
if args.native_home_assets:assert hashlib.sha256(asset_data).hexdigest()=='32a0a248a9bc72eab858a3a147ab4c720e90d7294fade564ba0c5b722c5250f3'
rows = []
frame_schedule_records=[]
for menu in (0, 1):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    for address, size in [(0x50000000,4096),(0x60000000,0x40000),(0x61000000,0x107000),
                          (0x63000000,0x400000),(0x65000000,0x20000)]:
        u.mem_map(address, size)
    u.mem_write(0x61000000, style)
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value & 0xffffffff))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    put(0x754abc, 0x61000000)
    put(0x60000370, 0x63001000)  # Virtual storage for the native object pool.
    put(0x60000378, 384)
    if args.native_page_rebuild and high<=0xe60000:u.mem_map(0xe60000,0x4000)
    if args.native_recovery_frames:u.mem_map(0x69000000,0x1000000 if args.native_home_assets else 0x100000)
    if args.native_home_assets:
        u.mem_map(0x70000000,(len(asset_data)+4095)&~4095);u.mem_write(0x70000000,asset_data)
    worker_groups=[0,1,2,3,9,15,16,17]
    asset_files={0:asset_data};asset_bases={0:0x70000000};asset_streams={};worker_group_requests=[];asset_file_group_events=[];native_cancel_checks=[]
    if args.native_worker_assets:
        for group in worker_groups[1:]:
            data=(ROOT/f'work/resource-analysis/TEXGRP{group:02d}.DAT').read_bytes();asset_files[group]=data
            address=0x70000000+group*0x1000000;asset_bases[group]=address
            u.mem_map(address,(len(data)+4095)&~4095);u.mem_write(address,data)
    if args.native_worker_assets:
        provenance=json.loads((ROOT/'sources/native-worker-resource-requests.json').read_text())
        hashes={f['group']:f['sha256'] for f in provenance['cases'][0]['stock_group_files']}
        assert all(hashlib.sha256(data).hexdigest()==hashes[g] for g,data in asset_files.items())
    pixel_cursor=0x69000000;pixel_lengths={};asset_file_releases=[];asset51_handles=[]
    frame_pixel_allocations=[];frame_pixel_frees=[];frame_image_requests=[];home_image_queries=[]
    frame_transform_calls=[]
    frame_processing=False;frame_services=[]
    touch_payload = bytearray(11)
    allocations, styles, selection_events, switch_requests = [], [], [], []
    close_trace = []
    lifecycle_running = False
    resume_running=False;resume_trace=[];resume_events=[];resume_threads=[];resume_worker_services=[];page_rebuild_services=[];virtual_page_frames=[]
    activation_route_running=False;activation_route_phase='';activation_route_events=[];activation_route_calls=[];activation_route_modules=[];activation_route_pending=[];activation_route_delivery=[]
    root_initializing=False;root_initialization_events=[];root_initialization=None
    stop_route_running=False;stop_route_stage='';stop_route_events=[];stop_route_calls=[];stop_route_modules=[];stop_route_pending=[];stop_gui_results=[];stop_gui_tokens=[]
    stop_receiver_running=False;stop_receiver_received=0;stop_receiver_returned=False;stop_receiver_callbacks=[]
    receiver_notice=(20,0,6,0,0);activation_receiver_info=None
    stop_snapshot_services=[];stop_snapshot_times=[];stop_snapshot_submissions=[];stop_snapshot_gate_states=[]
    snapshot_wire_requests=[];battery_wire_requests=[];argument_wire_requests=[];snapshot_manager=create_alarm_manager(ROOT) if args.native_activation_route else None
    resume_modules=[(0x16b74,0xc),(0x143c0,0x10),(0xf32c,0x18),(0x3b498,0x1c),(0x37f08,0x20),(0x49d6c,0x38),(0x4492c,0x28),(0x499f8,0x34),(0x4f3dc,0x40)]
    lifecycle_events, cleanup_boundaries = [], []
    lifecycle_acks = []
    apf_requests=[];resume_acks=[];apf_expected_state=1;switch_wire_requests=[];lookup_wire_requests=[]
    if args.native_switch_client:
        for offset,value in ((0,1),(4,2),(12,55),(16,500),(20,0),(40,88)):put(0x820f68+offset,value)
    heap = 0x63200000
    def asset_group_at(address):
        value=bytes(u.mem_read(address,128)).split(b'\0')[0].decode()
        match=re.fullmatch(r'/usr/local/share/GUI/skinRom/TEXGRP(\d\d)\.DAT',value)
        assert match and int(match[1]) in asset_files,value
        return int(match[1])
    def hook(uc, pc, size, data):
        global heap,pixel_cursor,stop_receiver_received,stop_receiver_returned
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if stop_receiver_running:
            if pc in (0xeb9c,0xeaa0):stop_receiver_callbacks.append(hex(pc));return
            if pc==0x268d48 and a[0]==501:
                if stop_receiver_received:
                    stop_receiver_returned=True;uc.emu_stop();return
                uc.mem_write(a[1],struct.pack('<5I',*receiver_notice));put(a[3],20);stop_receiver_received+=1
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if stop_route_running:
            if pc==0x265800:stop_snapshot_gate_states.append(word(a[0]+4));return
            if pc==0xb0850:stop_snapshot_submissions.append(bytes(uc.mem_read(a[0],108)).hex());return
            if pc==0x268c9c and a[3]==128:
                packet=bytes(uc.mem_read(a[2],128));words=list(struct.unpack('<5I',packet[:20]))
                assert words==[128,len(apf_requests)+len(switch_wire_requests)+len(lookup_wire_requests)+len(snapshot_wire_requests)+len(battery_wire_requests)+len(argument_wire_requests),1,20,55]
                assert packet[20:].hex()==stop_snapshot_submissions[-1]
                response,manager_details=snapshot_manager(packet,1,200)
                assert list(struct.unpack('<5I',response))[:4]==[20,words[1],20,0]
                snapshot_wire_requests.append({'request_hex':packet.hex(),'words':words,'reply_hex':response.hex(),'manager':manager_details})
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc==0x268d48 and a[2]==20:
                response=bytes.fromhex(snapshot_wire_requests[-1]['reply_hex']);uc.mem_write(a[1],response);put(a[3],20)
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc in (0x17e28c,0x33c528,0x33c610):
                stop_snapshot_services.append(hex(pc))
                if pc==0x17e28c:
                    record=bytearray(384);struct.pack_into('<4I',record,104,1000,0,123,456);uc.mem_write(a[0],bytes(record))
                elif pc==0x33c528:uc.mem_write(a[0],struct.pack('<2I',1100,0))
                elif pc==0x33c610:
                    stop_snapshot_times.append(list(struct.unpack('<2I',uc.mem_read(a[0],8))));uc.mem_write(a[1],struct.pack('<7I',11,22,3,4,5,106,6))
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc==0x113a4:stop_gui_tokens.append(word(stop_gui_results[-1]));return
            if pc==0xa57f0 and a[0] in (0x420024,0x430113,0x420032):
                stop_route_events.append(a.copy());uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if stop_route_stage=='command' and pc==0x112fc:stop_route_calls.append(a.copy());return
            if stop_route_stage=='command' and pc in {p for p,offset in resume_modules}:
                assert a[1]==6;stop_route_modules.append(hex(pc))
                if pc==0x143c0:stop_gui_results.append(a[2]);return
                put(a[2],0);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if stop_route_stage=='command' and pc==0x48a14:stop_route_pending.append(a[:2]);return
        if root_initializing:
            if pc==0xa57f0:root_initialization_events.append(a.copy())
            elif pc not in (0x17c42c,0x33b918):return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_activation_route and activation_route_running:
            if pc==0x268c9c and a[3]==20:
                packet=bytes(uc.mem_read(a[2],20));words=list(struct.unpack('<5I',packet))
                assert words[3] in (7,35)
                assert words==[20,len(apf_requests)+len(switch_wire_requests)+len(lookup_wire_requests)+len(snapshot_wire_requests)+len(battery_wire_requests)+len(argument_wire_requests),1,words[3],55]
                response,manager_details=snapshot_manager(packet,2,200)
                if words[3]==7:
                    assert list(struct.unpack('<6I',response))==[24,words[1],7,0,1,0];target_requests=battery_wire_requests
                else:
                    assert len(response)==1044 and list(struct.unpack('<5I',response[:20]))==[1044,words[1],35,0,0];target_requests=argument_wire_requests
                target_requests.append({'request_hex':packet.hex(),'words':words,'reply_hex':response.hex(),'manager':manager_details})
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc==0x268d48 and a[0]==500 and a[2] in (24,1044):
                target_requests=battery_wire_requests if a[2]==24 else argument_wire_requests
                response=bytes.fromhex(target_requests[-1]['reply_hex']);uc.mem_write(a[1],response);put(a[3],len(response))
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc in (0xe5ac,0x3b2b8,0xe600):uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if pc==0xa57f0 and a[0] in (0x420011,0x420023,0x20303,0x580101):
                activation_route_events.append(a.copy());uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if activation_route_phase=='command' and pc==0x112fc:activation_route_calls.append(a.copy());return
            if activation_route_phase=='command' and pc in {pc for pc,offset in resume_modules}:
                assert a[1]==7;activation_route_modules.append(hex(pc))
                if pc==0x143c0:assert a[0]==0x613f00;return
                put(a[2],0);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if activation_route_phase=='command' and pc==0x48a14:
                activation_route_pending.append(a[:2]);return
        if args.native_frame_receiver and frame_processing and pc in (0x104a14,0x1072c0,0x107514,0x104f64):
            frame_services.append({'procedure':hex(pc),'args':[hex(value) for value in a]})
        if args.native_frame_update and pc==0x10e274:
            frame_transform_calls.append({'args':[hex(v) for v in a],'caller':hex(uc.reg_read(UC_ARM_REG_LR))})
        if args.native_frame_update and pc in [symbols[name] for name in ('__aeabi_i2f','__aeabi_fdiv','__aeabi_fmul','__aeabi_f2iz')]:
            def f32(value):return struct.unpack('<f',struct.pack('<I',value))[0]
            if pc==symbols['__aeabi_i2f']:value=float(a[0] if a[0]<0x80000000 else a[0]-0x100000000)
            elif pc==symbols['__aeabi_fdiv']:
                assert f32(a[1])!=0;value=f32(a[0])/f32(a[1])
            elif pc==symbols['__aeabi_fmul']:value=f32(a[0])*f32(a[1])
            else:
                result=int(f32(a[0]));assert -0x80000000<=result<0x80000000
                uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            result=struct.unpack('<I',struct.pack('<f',value))[0]
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        result = 0
        if args.native_cancel_predicate and pc==0x117fc:
            native_cancel_checks.append(word(word(0x613f00+0x4c)+12));return
        if args.native_worker_assets and pc in (0x117fc,0xf5714):
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_worker_assets and resume_running and pc==0xb4964:return
        if args.native_worker_assets and resume_running and pc==0xf6a58:
            worker_group_requests.append(a[2]);return
        if args.native_worker_assets and pc in (0x132774,0x132834,0x132800,0xe09c,0xdafc):
            if pc==0x132774:asset_streams[a[0]]=asset_group_at(a[2])
            elif pc==0x132834:assert a[3]==32;uc.mem_write(a[2],asset_files[asset_streams[a[0]]][:32])
            elif pc==0x132800:asset_streams.pop(a[0],None)
            elif pc==0xe09c:assert a[1]==0;result=100+asset_group_at(a[0])
            elif pc==0xdafc:
                group=word(uc.reg_read(UC_ARM_REG_SP))-100
                assert a==[0,(len(asset_files[group])+4095)&~4095,3,2];result=asset_bases[group]
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_worker_assets and pc==symbols['munmap'] and a[0] in asset_bases.values():
            group=next(g for g in asset_bases if asset_bases[g]==a[0]);assert a[1]==(len(asset_files[group])+4095)&~4095
            asset_file_group_events.append(['munmap',group]);asset_file_releases.append('munmap')
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_worker_assets and pc==symbols['close'] and a[0]-100 in asset_files:
            asset_file_group_events.append(['close',a[0]-100]);asset_file_releases.append('close')
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_home_assets and pc in (0x132774,0x132834,0x132800,0xe09c,0xdafc,0xd6b8,0xd808):
            if pc in (0x132774,0xe09c):
                address=a[2] if pc==0x132774 else a[0]
                assert bytes(uc.mem_read(address,128)).split(b'\0')[0]==b'/usr/local/share/GUI/skinRom/TEXGRP00.DAT'
                result=19 if pc==0xe09c else 0
            elif pc==0x132834:assert a[3]==32;uc.mem_write(a[2],asset_data[:32])
            elif pc==0xdafc:assert a[:4]==[0,(len(asset_data)+4095)&~4095,3,2];result=0x70000000
            elif pc==0xd6b8:
                left=bytes(uc.mem_read(a[0],a[2])).split(b'\0')[0];right=bytes(uc.mem_read(a[1],a[2])).split(b'\0')[0];result=0 if left==right else 1
            elif pc==0xd808:assert a[1];result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_home_assets and pc==symbols['munmap'] and a[0]==0x70000000:
            assert a[1]==(len(asset_data)+4095)&~4095
            asset_file_releases.append('munmap');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_home_assets and pc==symbols['close'] and a[0]==19:
            asset_file_releases.append('close');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_resource_catalog and pc in (0x3387c0,0x338dd4):
            uc.reg_write(UC_ARM_REG_R0,1 if pc==0x338dd4 else 0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_recovery_frames and pc==0x1093bc:
            home_image_queries.append({'descriptor':hex(a[0]),'words':list(struct.unpack('<5I',uc.mem_read(a[0],20))),'caller':hex(uc.reg_read(UC_ARM_REG_LR))})
            return
        if args.native_recovery_frames and pc==0x1093d0 and home_image_queries:
            home_image_queries[-1]['resolved_image_handle']=uc.reg_read(UC_ARM_REG_R0)
            return
        if args.native_recovery_frames and pc==0x1093f0 and home_image_queries:
            home_image_queries[-1]['status_before_return']=uc.reg_read(UC_ARM_REG_R3)
            home_image_queries[-1]['resolved_resource']=uc.reg_read(UC_ARM_REG_R2)
            return
        if args.native_recovery_frames and pc==0x133028:
            frame_image_requests.append({'dimensions_format':a[:3],'caller':hex(uc.reg_read(UC_ARM_REG_LR)),'objects_at_request':len(allocations)})
            return
        if args.native_recovery_frames and pc==0x3397f4:
            fmt=bytes(uc.mem_read(a[3],128)).split(b'\0')[0].decode();value=word(uc.reg_read(UC_ARM_REG_SP))
            text=(fmt%value).encode();assert len(text)<a[1]
            uc.mem_write(a[0],text+b'\0');uc.reg_write(UC_ARM_REG_R0,len(text));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_recovery_frames and pc==symbols['strlen']:
            text=bytes(uc.mem_read(a[0],128)).split(b'\0')[0]
            uc.reg_write(UC_ARM_REG_R0,len(text));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if resume_running and args.command7_worker and pc==0x337534:
            assert a==[0x13f38,0x613efc,8,0x18000],a
            resume_threads.append(a.copy());uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if resume_running and args.command7_worker and pc in (0x4e388,0x3ce08,0x3d6dc,0xb4964,0xb4a54,0xb52dc):
            resume_worker_services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if resume_running and pc in (0x120ec,0xb586c,0x120d8,0x5cfb4,0x13e04):
            resume_trace.append(hex(pc));return
        if resume_running and args.native_page_rebuild and pc==0x12ef8:
            resume_trace.append('native-page-rebuild');return
        if resume_running and args.native_page_rebuild and pc in (0xb5f88,0xb54e8,0xb4b84,0xb4b9c,0x33d8c0,0xb5034,0x48f38,0x48fe4,0x4a584,0x4a630,0x3dda4,0xb523c):
            page_rebuild_services.append({'pc':hex(pc),'argument':a[0],'virtual':pc not in (0xb54e8,0xb4b84,0xb4b9c)})
            if pc in (0xb54e8,0xb4b84,0xb4b9c) or (args.native_recovery_frames and pc==0xb5f88):return
            result=a[0] if pc==0x33d8c0 else 0
            if pc==0xb5f88:
                assert a[0] in (9,49)
                result=0x66006000+len(virtual_page_frames)*256;virtual_page_frames.append(result)
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if resume_running and pc==0x12ef8:
            resume_trace.append('deferred-page-rebuild');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        elif resume_running and pc in (0x51828,0x49984,0x497b4,0xb4a10,0x17c42c,0x335788,0x3357e4,0xff5c,0x10e68,0x140b4):
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        elif resume_running and pc==0xa57f0:
            resume_events.append(a);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        elif pc == 0xe9374:
            assert a[0] and a[0] not in allocations
            allocations.append(a[0])  # Observe native allocation; do not replace it.
            return
        if pc == 0xf577c:
            styles.append(a[3])
            return
        if ((lifecycle_running and args.ack_manager_close) or (resume_running and args.command7_ack)) and pc == 0x1fd30:
            assert a[1] == (7 if resume_running else 6)
            put(a[2],0)
        elif ((lifecycle_running and args.ack_manager_close) or (resume_running and args.command7_ack)) and pc == 0x268c9c:
            packet = list(struct.unpack('<6I',uc.mem_read(a[2],24)))
            assert a[:2] == [500,55] and a[3] == 24 and packet == [24,len(apf_requests)+len(switch_wire_requests)+len(lookup_wire_requests)+len(snapshot_wire_requests)+len(battery_wire_requests)+len(argument_wire_requests),1,1,55,apf_expected_state],(a,packet,rebuild_cycle)
            apf_requests.append(packet.copy())
            if resume_running:resume_acks.append(packet.copy())
            else:
                lifecycle_acks.append(packet)
                close_trace.append({'apf_ack':packet})
        elif ((lifecycle_running and args.ack_manager_close) or (resume_running and args.command7_ack)) and pc == 0x268d48:
            assert a[0] == 500 and a[2] == 16
            uc.mem_write(a[1],struct.pack('<4I',16,apf_requests[-1][1],1,0))
            put(a[3],16)
        elif args.native_name_lookup and pc==0x268c9c and a[3]==276:
            assert a[:2]==[500,55]
            packet=bytes(uc.mem_read(a[2],276));words=list(struct.unpack('<5I',packet[:20]))
            assert words==[276,len(lookup_wire_requests)+len(switch_wire_requests)+len(apf_requests)+len(snapshot_wire_requests)+len(battery_wire_requests)+len(argument_wire_requests),1,36,55]
            assert packet[20:].split(b'\0',1)[0]==b'/contents/HOMEBREW/launcher/app'
            parser_details={};reply,comparisons=lookup(ROOT,packet,config_bytes=lookup_config,core_state=2,details=parser_details)
            assert parser_details['native_parser_executed'] and parser_details['record_count']==7
            assert list(struct.unpack('<5I',reply))==[20,words[1],36,0,0x30001]
            lookup_wire_requests.append({'packet_hex':packet.hex(),'packet_sha256':hashlib.sha256(packet).hexdigest(),'words':words,'reply_hex':reply.hex(),'comparisons':comparisons,'parser':parser_details})
        elif args.native_switch_client and pc==0x268c9c:
            assert a[:2]==[500,55] and a[3]==1060
            packet=bytes(uc.mem_read(a[2],a[3]));words=list(struct.unpack('<8I',packet[:32]))
            assert words==[1060,len(switch_wire_requests)+len(lookup_wire_requests)+len(apf_requests)+len(snapshot_wire_requests)+len(battery_wire_requests)+len(argument_wire_requests),1,6,55,0x30001,0,0]
            switch_wire_requests.append({'packet_hex':packet.hex(),'packet_sha256':hashlib.sha256(packet).hexdigest(),'words':words})
        elif args.native_switch_client and pc==0x268d48:
            assert a[0]==500
            if args.native_name_lookup and a[2]==20:
                uc.mem_write(a[1],bytes.fromhex(lookup_wire_requests[-1]['reply_hex']));put(a[3],20)
            else:
                assert a[2]==16
                uc.mem_write(a[1],struct.pack('<4I',16,switch_wire_requests[-1]['words'][1],6,0));put(a[3],16)
        elif args.native_name_lookup and pc==0x339720:
            value=bytes(uc.mem_read(a[2],256)).split(b'\0',1)[0];assert len(value)+1<=a[1]
            uc.mem_write(a[0],value+b'\0')
        elif ((lifecycle_running and args.ack_manager_close) or (resume_running and args.command7_ack) or args.native_switch_client) and pc in (0x337a80,0x337ae8,0x265298,0x17c42c):
            result = 0
        elif lifecycle_running and pc in (0x4c73c,0x48fe8,0x4a634,0xb4a34,0x14da0):
            cleanup_boundaries.append(hex(pc))
            if args.native_asset_handoff and pc==0xb4a34:return
        elif lifecycle_running and pc == 0x33d8c0:
            result = a[0]
        elif pc == 0x1094f0:
            result = 0x65000000
        elif pc == 0xe87f4:
            result = 0x60000000
        elif args.native_open_root and pc==0x11649c:
            result=0
        elif args.native_open_root and pc==0x132a78:
            if args.native_home_assets and a[0]!=383*4936:
                assert 0<a[0]<=240*432*4,a
                length=(a[0]+4095)&~4095;result=pixel_cursor;pixel_cursor+=length
                assert pixel_cursor<=0x6a000000
                pixel_lengths[result]=length;frame_pixel_allocations.append(result)
            elif args.native_recovery_frames and a[0]==207360:
                if len(frame_pixel_allocations)>=4:
                    gap={'scope':'Native recovery frames constructed; Home requests additional image resources, not a passing integration','menu':menu,'cycle':rebuild_cycle,'constructed_objects':len(allocations),'pixel_allocations':len(frame_pixel_allocations),'pixel_frees':len(frame_pixel_frees),'image_requests':frame_image_requests,'image_queries':home_image_queries,'catalog_initialization_executed':args.native_resource_catalog,'limits':['Resource pool and allocator fixture provisioned for four recovery-frame buffers only.','Additional Home requests need provenance/capacity analysis, not guessed unlimited backing.','No firmware/device changes.']}
                    (ROOT/'sources/native-home-recovery-frame-resource-gap.json').write_text(json.dumps(gap,indent=2)+'\n')
                assert len(frame_pixel_allocations)<4,(len(allocations),len(frame_pixel_allocations),len(frame_pixel_frees),rebuild_cycle)
                result=0x69000000+len(frame_pixel_allocations)*0x40000;frame_pixel_allocations.append(result)
            else:
                assert a[0]==383*4936,a
                result=0x63001000
        elif pc == symbols['ioctl']:
            assert a[1] == 0x80045401
            uc.mem_write(a[2], bytes(touch_payload))
        elif pc == symbols['qsort']:
            assert a[2] == 4 and a[3] in (0xef8f0, 0xf8214)
            values = list(struct.unpack('<' + 'I' * a[1], uc.mem_read(a[0], 4 * a[1])))
            # Native comparator orders signed z + priority; libc sorting is virtual.
            def depth(node):
                return struct.unpack('<i', uc.mem_read(node + 0x2fc, 4))[0] + struct.unpack('<i', uc.mem_read(node + 0x468, 4))[0]
            def model_order(index):
                value = word(word(0x732594) + 4 + index * 0x5c + 0x58)
                return value if value < 0x80000000 else value - 0x100000000
            if args.reverse_equal_sort:
                values.reverse()
            values.sort(key=depth if a[3] == 0xef8f0 else model_order)
            uc.mem_write(a[0], struct.pack('<' + 'I' * len(values), *values))
        elif pc in (0x33c528, 0x10752c, 0x2a730, 0xb00bc):
            result = 0
        elif pc == 0xa57f0:
            if lifecycle_running:
                lifecycle_events.append(a)
                close_trace.append({'queued':a})
            else:
                selection_events.append(a)
        elif pc == 0x2664d0:
            assert bytes(uc.mem_read(a[1], 64)).split(b'\0')[0] == b'/contents/HOMEBREW/launcher/app'
            if args.native_name_lookup:return
            put(a[2], 0x30001)
        elif pc == 0x2681e8:
            assert a[1:] == [0x30001, 0, 0]
            switch_requests.append(a[1:])
            if args.native_switch_client:
                assert a[0]==0x820f68
                return
        elif args.close_manager and pc == symbols['sysconf']:
            assert a[0] == 30
            result = 4096
        elif args.close_manager and pc == symbols['munmap']:
            assert a[0] in (0x63001000, 0x67000000) or a[0] in frame_pixel_allocations
            if a[0] in frame_pixel_allocations:
                assert a[1]==(pixel_lengths[a[0]] if args.native_home_assets else 208896);assert a[0] not in frame_pixel_frees;frame_pixel_frees.append(a[0])
            if a[0] == 0x67000000:
                assert a[1] == 0x500000
            close_trace.append({'call':'munmap','address':hex(a[0]),'bytes':a[1]})
        elif args.close_manager and pc == symbols['close']:
            assert a[0] == 17
            close_trace.append({'call':'close','fd':a[0]})
        elif args.close_manager and pc in (0x115f68, 0x11600c):
            close_trace.append({'virtual_presentation':hex(pc)})
        elif pc == symbols['malloc']:
            result = heap
            heap += (a[0] + 15) & ~15
            assert heap < 0x63400000
        elif pc == symbols['memset']:
            uc.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            result = a[0]
        elif pc == symbols['memcpy']:
            uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])))
            result = a[0]
        elif pc == symbols['__modsi3']:
            assert a[0] < 0x80000000 and a[1] > 0
            result = a[0] % a[1]
        elif pc not in (symbols['free'], 0x33b748, 0x33b83c, 0x33b918):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def interrupt(uc, number, data):
        raise AssertionError(f'Unexpected syscall/interrupt {number}')
    u.hook_add(UC_HOOK_CODE, hook)
    u.hook_add(UC_HOOK_INTR, interrupt)
    def call(pc, values):
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), values):
            u.reg_write(reg, value)
        u.reg_write(UC_ARM_REG_SP, 0x60008000)
        u.reg_write(UC_ARM_REG_LR, 0x50000000)
        try:u.emu_start(pc, 0x50000000, count=5000000 if args.native_home_assets else 200000)
        except Exception as exc:raise AssertionError((hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),resume_trace)) from exc
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    def complete_resume_worker():
        global resume_running,apf_expected_state
        resume_running=True
        if args.native_activation_route:activation_route_delivery.append(0x20670)
        assert call(0x17c608,(0x68000d00,0x20670,0x207,0))==0
        assert len(resume_threads)==1 and list(u.mem_read(0x68000d00,2))==[1,3]
        call(0x13f38,(0x613efc,))
        assert resume_events[-2:]==[[0x20671,0,0,0],[0x420034,0,0x207,0]],resume_events
        if args.native_activation_route:activation_route_delivery.append(0x20671)
        call(0x17c608,(0x68000d00,0x20671,0,0))
        if args.command7_ack:
            done=resume_events[-1]
            if args.native_activation_route:activation_route_delivery.append(0x420034)
            assert call(0x71ee4,(0,done[0],done[2],done[3]))==0
            assert word(0x68000900)==0 and resume_events[-1]==[0x410009,0,0,0]
            # Reuse actual main state2/2 left by first close acknowledgement.
            assert list(u.mem_read(0x68000c00,2))==[2,2]
            assert word(0x820f68+4)==1
            apf_expected_state=2
            if args.native_activation_route:activation_route_delivery.append(0x410009)
            assert call(0x17c608,(0x68000c00,0x410009,0,0))==0
            apf_expected_state=1
            assert word(0x820f68+4)==2 and len(resume_acks)==1,(word(0x820f68+4),resume_acks,apf_requests,resume_events,list(u.mem_read(0x68000c00,2)))
        resume_running=False
        assert list(u.mem_read(0x68000d00,2))==[1,4]
    if args.native_resource_catalog:
        catalog=call(0xf647c,())
        call(0xf6488,(catalog,))
        assert word(catalog+0x11c+51*4)==0 # Initialization alone does not load/resolve asset slots.
    if args.native_home_assets:
        if args.stock_resource_pools:
            assert call(0x11e9b8,(0x7a0660,))==0
            assert word(0x7a0660)==0 and word(0x7a0660+0x30294)==0
        else:
            assert call(0x132938,(0x7a0660+0x18284,1))==0
            assert call(0x132938,(0x7a0660+0x2f28c,512))==0
        put(0x60008000,1)
        assert call(0xf6a58,(catalog,0,0,0))==0
        assert word(catalog+0x11c+51*4)==51 and word(0x7a0660+0x30294)==139
        asset51_handles.append(51)
    native_input_restorations=[]
    if args.native_activation_route:
        u.mem_map(0x68001000,4096)
        root_initializing=True
        assert call(0x714c4,(0,))==0
        assert word(0x6833d8)==0x6833dc and list(u.mem_read(0x6833dc,2))==[1,1]
        saved_completion=bytes(u.mem_read(0x613e60+0x4c,24));saved_state=bytes(u.mem_read(0x613e2c,28))
        u.mem_write(0x613e60+0x4c,bytes(24));put(0x613e2c+4,1)
        for slot in range(6):
            assert call(0x17c608,(0x6833dc,0x420102,slot,0))==0
            assert list(u.mem_read(0x6833dc,2))==([2,1] if slot==5 else [1,1])
        assert root_initialization_events==[[0x42001a,0,0,0]]
        root_initialization={'constructor':'0x714c4','context':'0x6833dc','initial':[1,1],'after_notifications':[2,1],'notification_slots_fixture':list(range(6)),'state_field_fixture':1,'unconsumed_events':root_initialization_events.copy(),'context_byte13':u.mem_read(0x6833dc+13,1)[0],'constructed_at_recovery_boundary':False,'constructed_before_first_home':True}
        assert root_initialization['context_byte13']==5
        u.mem_write(0x613e60+0x4c,saved_completion);u.mem_write(0x613e2c,saved_state)
        root_initializing=False
        root_context_before_home=bytes(u.mem_read(0x6833dc,32))
        root_initializing=True
        assert call(0x6dec0,(0,))==0
        assert word(0x683324)==0x683328 and list(u.mem_read(0x683328,2))==[1,1]
        assert u.mem_read(0x683328+13,1)[0]==11
        consumer_context_before_home=bytes(u.mem_read(0x683328,32))
        root_initializing=False
        u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_R7,0x60010000)
        u.emu_start(0xfcb4,0xfd68,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0xfd68
        assert word(0x820f68+0x2c+6*4)==0xeb9c
        put(0x820f68+0x24,1);put(0x820f68+0x1c,501)
    home_cycle_count=3 if args.three_home_cycles else 2 if args.reopen_home or args.reopen_manager else 1
    for rebuild_cycle in range(home_cycle_count):
        if rebuild_cycle:
            lifecycle_running=False
            resume_trace.clear();resume_events.clear();resume_threads.clear();resume_worker_services.clear();page_rebuild_services.clear();virtual_page_frames.clear();resume_acks.clear();worker_group_requests.clear()
            activation_route_events.clear();activation_route_calls.clear();activation_route_modules.clear();activation_route_pending.clear();activation_route_delivery.clear()
            # Reuse supplied object backing after GUI-page close; no OS remap is claimed.
            allocations.clear();styles.clear();selection_events.clear();switch_requests.clear();close_trace.clear()
            lifecycle_events.clear();cleanup_boundaries.clear();lifecycle_acks.clear()
            put(0x60000370,0x63001000);put(0x60000378,384)
            assert word(0x6000037c)==0 and word(0x60000788)==0 # Native close must clear counts.
            if args.reopen_manager and args.consume_manager_close and not args.command7_reopen:
                # Original120ec calls this before rebuilding through12ef8.
                flags_before=word(0x60000004)
                assert call(0xb586c,(0,))==0
                assert word(0x60000004)&8==0
                native_input_restorations.append({'cycle':rebuild_cycle,'procedure':'0xb586c','argument':0,'flags_before':flags_before,'flags_after':word(0x60000004),'source_call':'0x120f8'})
        if rebuild_cycle and args.native_asset_handoff and not args.native_worker_assets:
            assert word(0x7a0660+0x30294)==0
            put(0x60008000,1)
            assert call(0xf6a58,(catalog,0,0,0))==0
            reloaded51=word(catalog+0x11c+51*4);asset51_handles.append(reloaded51)
            assert call(0x132fd0,(reloaded51,0x66005000))==0
            assert list(struct.unpack('<3I',u.mem_read(word(0x66005000),12)))==[78,78,0x10008]
        if rebuild_cycle and args.command7_reopen:
            context=bytearray(32);context[0]=1;context[1]=2;context[13]=10
            struct.pack_into('<I',context,4,0x3ea150)
            u.mem_write(0x68000d00,bytes(context));put(0x68233c,0x68000d00)
            if args.native_cancel_predicate:
                call(0x3365bc,(0x66007000,0));put(0x613f00+0x4c,0x66007000)
            if args.native_recovery_frames:
                call(0x112008,(0x75cf44,))
                if not args.native_home_assets:assert call(0x132938,(0x7a0660+0x2f28c,4))==0
            if args.native_page_rebuild:
                receiver=call(0x104870,());put(0x60008000,0x60000000)
                assert call(0x10487c,(receiver,0xe9690,0xe8794,0xe87bc))==0
            resume_running=True
            if args.native_activation_route:
                for index,(procedure,offset) in enumerate(resume_modules):put(0x613e60+offset,0x613f00 if procedure==0x143c0 else 0x68001000+index*32)
                assert word(0x68000900)==0 and word(0x613e60+8)==0
                assert bytes(u.mem_read(0x6833dc,32))==root_context_before_home
                root_initialization['preserved_until_recovery_checked']=True
                root_initialization['context_sha256_before_home_and_recovery']=hashlib.sha256(root_context_before_home).hexdigest()
                activation_route_running=True;activation_route_phase='callback'
                assert word(0x820f68+4)==1 and word(0x820f68+0x2c+5*4)==0xeaa0
                receiver_notice=tuple(activation_frame_words) if activation_frame_input else (20,0,5,0,0);stop_receiver_received=0;stop_receiver_returned=False;stop_receiver_callbacks.clear();stop_receiver_running=True
                u.reg_write(UC_ARM_REG_R0,0x820f68);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
                u.emu_start(0x26551c,0x50000000,count=100000)
                stop_receiver_running=False
                assert stop_receiver_received==1 and stop_receiver_returned and stop_receiver_callbacks==['0xeaa0']
                activation_receiver_info={'entry':'0x26551c','callback':'0xeaa0','callback_invoked_by_harness':False,'notification_fixture':list(receiver_notice),'returned_to_receive':True,'client_state_before_confirmation':word(0x820f68+4)}
                assert activation_route_events==[[0x420011,0,1,0],[0x420023,0,0,0]]
                activation_route_delivery.append(0x420011);call(0x17c608,(0x6833dc,0x420011,1,0))
                assert activation_route_events[2:]==[[0x20303,0,1,0],[0x580101,0,1,0]]
                activation_route_phase='command';activation_route_delivery.append(0x420023);assert call(0x17c608,(0x6833dc,0x420023,0,0))==0
                activation_route_phase='children'
                activation_route_delivery.append(0x20303)
                call(0x17c608,(0x68000d00,0x20303,1,0));assert word(0x613f00+0x56d8)==1
                battery=bytearray(32);battery[0]=1;battery[1]=1;battery[13]=24;struct.pack_into('<I',battery,4,0x412b70);u.mem_write(0x68000f00,bytes(battery));put(0x671c40+32,0)
                activation_route_delivery.append(0x580101);call(0x17c608,(0x68000f00,0x580101,1,0));assert word(0x671c40+32)==1
                activation_route_running=False
                assert len(activation_route_calls)==1 and activation_route_calls[0][:2]==[0x613e60,7]
                assert activation_route_modules==[hex(procedure) for procedure,offset in resume_modules]
                assert activation_route_pending==[[0x68000900,0x207]] and word(0x68000900)==1
            else:assert call(0x143c0,(0x613f00,7,0x68000800))==0
            resume_running=False
            assert (args.native_activation_route or word(0x68000800)==0x207) and word(0x613f00+0x5eb0)==1
            assert resume_events==[[0x20670,0,0x207,0]],resume_events
            if args.command7_ack:
                if not args.native_activation_route:
                    put(0x613e60+4,7);put(0x613e60+8,0)
                    put(0x613e60+0x2c,0x68000900);put(0x613e60+0x14,0x68000a00)
                    assert call(0x48a14,(0x68000900,0x207))==0
            assert word(0x60000004)&8==0 and word(0x6bafb8)==7
            assert resume_trace==['0x120ec','0xb586c','0x120d8','0x5cfb4','native-page-rebuild' if args.native_page_rebuild else 'deferred-page-rebuild','0x13e04'],resume_trace
            if args.native_page_rebuild:
                if not args.native_recovery_frames:assert len(virtual_page_frames)==2
                else:
                    assert word(0x75cf44+0x138)==2 and (len(set(frame_pixel_allocations)-set(frame_pixel_frees))==4 if args.native_home_assets else len(frame_pixel_allocations)==4)
                    assert word(word(0x75cf44)+0xae4)==21 and word(word(0x75cfac)+0xae4)==21
                assert [v['argument'] for v in page_rebuild_services if v['pc']=='0xb54e8']==[383]
                assert [v['argument'] for v in page_rebuild_services if v['pc']=='0xb4b84']==[0]
                assert word(0x60000000)==0 and word(0x65000000)==1 and len(allocations)==(3 if args.native_recovery_frames else 1)

        if not (rebuild_cycle and args.native_page_rebuild):
            for pool_address, capacity in [(0x60000380,384),(0x60000804,5),
                                           (0x60029754,10),(0x6002920c,128)]:
                assert call(0x104730, (pool_address, capacity)) == 0
            call(0x109524, (0x65000000,))
            assert word(0x65000000) == 0
            if not args.native_open_complete:
                assert call(0x1095b4, (0x65000000,)) == 0
                assert word(0x65000000) == 1
        call(0x10e754, (0x4e692c, 156))
        assert call(0x10e558, (menu, 0x6500f000)) == 0
        descriptor = word(0x6500f000)
        d = list(struct.unpack('<43I', u.mem_read(descriptor, 172)))
        call(0xeba18, (0x60000008,))
        if args.native_frame_update:
            # Original e8800 loop: two views, centers(120,216,-200), bind +364/+368.
            for register,value in ((UC_ARM_REG_R7,0x60000008),(UC_ARM_REG_R11,0x60000000),(UC_ARM_REG_R10,1),(UC_ARM_REG_R6,0xffffff38),(UC_ARM_REG_SP,0x60008000)):
                u.reg_write(register,value)
            u.emu_start(0xe88c8,0xe8900,count=10000)
            assert u.reg_read(UC_ARM_REG_PC)==0xe8900
            assert word(0x60000364)==0x60000010 and word(0x60000368)==0x6000012c
        else:call(0xeba80, (0x60000008,))
        if args.native_open_root and not (rebuild_cycle and args.native_page_rebuild):
            if args.native_open_complete:
                receiver=call(0x104870,())
                put(0x60008000,0x60000000)
                assert call(0x10487c,(receiver,0xe9690,0xe8794,0xe87bc))==0
            assert call(0xe8b64,(0x60000000,383))==0
            for reg,value in ((UC_ARM_REG_R0,0x60000000),(UC_ARM_REG_R1,0),(UC_ARM_REG_SP,0x60008000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
            if args.native_open_complete:
                u.emu_start(0xe9388,0x50000000,count=5000000 if args.native_home_assets else 200000)
                assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
                assert word(0x60000000)==0 and word(0x65000000)==1 and word(0x732d3c+0x180)==1
            else:
                u.emu_start(0xe9388,0xe948c,count=5000000 if args.native_home_assets else 200000)
                assert u.reg_read(UC_ARM_REG_PC)==0xe948c
            assert word(0x60029b68)==allocations[0] and word(allocations[0]+0xae4)==1
        if rebuild_cycle and args.reopen_manager and args.consume_manager_close and not args.command7_reopen:
            assert word(0x6bafb8)==0 and word(0x613f00+0x5f18)==7
            call(0x13e04,(0x613f00,))
            assert word(0x6bafb8)==7
        if rebuild_cycle and args.native_worker_assets:
            complete_resume_worker()
            assert worker_group_requests==worker_groups,worker_group_requests
            assert word(0x7a0660)==8 and word(0x7a0660+0x30294)==554
            reloaded51=word(catalog+0x11c+51*4);asset51_handles.append(reloaded51)
            assert call(0x132fd0,(reloaded51,0x66005000))==0
            assert list(struct.unpack('<3I',u.mem_read(word(0x66005000),12)))==[78,78,0x10008]
        assert call(0x1096e0, (0x65000000, descriptor)) == 0
        root = word(descriptor + 0x94)
        assert root == allocations[3 if rebuild_cycle and args.native_recovery_frames else 1 if args.native_open_root else 0] and word(descriptor + 0x98) == 1
        assert word(0x60000788) == len(allocations)
        pending_after_creation = word(0x60000788)
        if args.native_open_root:assert pending_after_creation==(107 if rebuild_cycle and args.native_recovery_frames else 105) and len(allocations)==pending_after_creation
        if rebuild_cycle and args.command7_worker and not args.native_worker_assets:complete_resume_worker()
        grid, model = word(root + 0xb68), word(root + 0xb2c)
        content = word(grid + 0xb00)
        content_position_after_init = list(struct.unpack('<3i', u.mem_read(content + 0x2f4, 12)))
        root_position = list(struct.unpack('<3i', u.mem_read(root + 0x2f4, 12)))
        assert root_position == [120,208 if menu == 0 else 232,0], (menu, root_position, d[:6])
        assert list(struct.unpack('<3i', u.mem_read(grid + 0x2f4, 12))) == root_position
        assert d[0x27] == 49 and word(model) == 49
        content_size = list(struct.unpack('<2I', u.mem_read(content + 0x3a8, 8)))
        assert content_size == [252,400] and word(grid + 0xb1c) == 74
        centers = []
        for index in range(d[0x13]):
            put(0x6001f004, index)
            call(0xfca30, (grid, 0x6001f000, 0x6001f100))
            centers.append(list(struct.unpack('<3i', u.mem_read(0x6001f100, 12))))
        # Original frame prefix commits newly allocated objects for scheduling.
        frame_initial_positions={node:list(struct.unpack('<3i',u.mem_read(node+0x2f4,12))) for node in allocations} if args.native_frame_update else {}
        if args.native_frame_update:
            call(0x119258,(0x761394,))
            assert word(0x761394+0xc158)==0x761394+0xc15c
        for reg, value in [(UC_ARM_REG_R0, 0x60000000), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        frame_stop=0x50000000 if args.native_frame_receiver else 0xe8ed8 if args.native_frame_update else 0xe8e58
        frame_processing=True;frame_services.clear()
        try:
            u.emu_start(0xe8de8,frame_stop,count=5000000 if args.native_home_assets else 200000)
        except Exception as error:
            if args.native_frame_update:
                (ROOT/'work/native-frame-update-gap.json').write_text(json.dumps({'menu':menu,'cycle':rebuild_cycle,'pc':hex(u.reg_read(UC_ARM_REG_PC)),'registers':{name:hex(u.reg_read(reg)) for name,reg in [('r0',UC_ARM_REG_R0),('r1',UC_ARM_REG_R1),('r2',UC_ARM_REG_R2),('r3',UC_ARM_REG_R3),('lr',UC_ARM_REG_LR),('sp',UC_ARM_REG_SP)]},'transform_calls':frame_transform_calls[-12:],'stack_words':[hex(word(u.reg_read(UC_ARM_REG_SP)+i*4)) for i in range(12)],'error':str(error),'scope':'Experimental frame execution failed; not a passing check'},indent=2)+'\n')
            raise
        assert u.reg_read(UC_ARM_REG_PC)==frame_stop
        frame_processing=False
        if args.native_frame_receiver:
            procedures=[item['procedure'] for item in frame_services]
            assert procedures==['0x104a14','0x1072c0','0x107514','0x104f64'],procedures
            assert word(0x732d3c+0x180)==1
            frame_schedule_records.append({'menu':menu,'cycle':rebuild_cycle,'services':frame_services.copy(),'receiver_state_after':word(0x732d3c+0x180),'frame_return':u.reg_read(UC_ARM_REG_R0)})
        if args.native_frame_update:
            (ROOT/'work/native-frame-update-progress.json').write_text(json.dumps({'menu':menu,'cycle':rebuild_cycle,'reached_stop':hex(frame_stop),'native_view_bindings':[hex(word(0x60000364)),hex(word(0x60000368))],'transform_calls':frame_transform_calls,'limits':['Frame processing reached receiver boundary; later manual positioning replay not integrated.','IEEE float helpers supplied by host; no physical rendering or complete frame qualification.'],'complete_check_passed':False},indent=2)+'\n')
        assert word(0x60000788) == 0 and word(0x6000037c) == len(allocations)
        assert all(word(a + 0x460) & 1 and not word(a + 0x460) & 0x2000 for a in allocations)
        valid_slots = [i for i in range(word(model)) if word(model + 4 + i * 0x5c) != 0xffffffff]
        assert valid_slots == list(range(d[0x13]))
        new_index = d[0x13] - 1
        new_metadata = list(struct.unpack('<15I', u.mem_read(model + 4 + new_index * 0x5c, 60)))
        assert new_metadata[new_metadata[1] + 1] == new_index
        new_control = word(model + 0x40 + new_index * 0x5c)
        assert new_control in allocations
        assert word(new_control + 0x4c4) == content
        grid_links, content_links = word(grid + 0x4cc), word(content + 0x4cc)
        assert grid_links and content_links and grid_links != content_links
        leaf = call(0xed03c, (new_control, 1))
        assert leaf in allocations and word(leaf + 0xae4) == 14
        local_entry=list(struct.unpack('<3i',u.mem_read(new_control+0x2f4,12)))
        local_leaf=list(struct.unpack('<3i',u.mem_read(leaf+0x2f4,12)))
        if args.native_frame_update:
            local_entry=frame_initial_positions[new_control];local_leaf=frame_initial_positions[leaf]
        # Only the original parent-relative position prefix, before animation/backend work.
        for node in (() if args.native_frame_update else (content, new_control, leaf)):
            for reg, value in [(UC_ARM_REG_R0, node), (UC_ARM_REG_R1, 0x6001c000),
                               (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            try:u.emu_start(0xeea80,0xeeb68,count=100000)
            except Exception as error:
                if args.native_frame_update:
                    (ROOT/'work/native-frame-position-gap.json').write_text(json.dumps({'node':hex(node),'pc':hex(u.reg_read(UC_ARM_REG_PC)),'registers':{name:hex(u.reg_read(reg)) for name,reg in [('r0',UC_ARM_REG_R0),('r1',UC_ARM_REG_R1),('r2',UC_ARM_REG_R2),('r3',UC_ARM_REG_R3),('lr',UC_ARM_REG_LR)]},'error':str(error),'scope':'Experimental post-frame position update failure; not a device failure'},indent=2)+'\n')
                raise
            assert u.reg_read(UC_ARM_REG_PC) == 0xeeb68
        content_position = list(struct.unpack('<3i', u.mem_read(content + 0x2f4, 12)))
        entry_position = list(struct.unpack('<3i', u.mem_read(leaf + 0x2f4, 12)))
        assert content_position == [126, root_position[1], 0]
        assert local_entry==centers[new_index],(local_entry,centers[new_index],local_leaf,content_position,entry_position)
        assert entry_position == [content_position[0]+local_leaf[0],content_position[1]+local_leaf[1],local_leaf[2]],(entry_position,local_leaf,content_position)
        if not args.native_home_assets:assert local_leaf==centers[new_index]
        call(0xede84, (leaf,))
        entry_bounds = list(struct.unpack('<4i', u.mem_read(leaf + 0xa2c, 16)))
        x, y = entry_position[:2]
        assert entry_bounds == [x - 32, y - 32, x + 31, y + 31]
        # Feed virtual raw contact/release through the entire original dispatcher.
        # No centered-coordinate helper wiring or direct leaf-input callback calls.
        if not rebuild_cycle:u.mem_map(0x66000000, 0x10000)
        view = call(0xebb74, (0x60000008,))
        call(0xeb5ec, (view,))
        call(0x119258, (0x761394,))
        px, py = (239, 431) if args.touch_outside else (x, y)
        if args.touch_outside:
            assert not (entry_bounds[0] <= px <= entry_bounds[2] and entry_bounds[1] <= py <= entry_bounds[3])
        rx, ry = (px * 2929 + 239) // 240, ((431 - py) * 5281 + 431) // 432
        struct.pack_into('>HH', touch_payload, 2, rx, ry)
        touch_trace = []
        for contact, phase in ((1, 2), (0, 3)):
            touch_payload[1] = contact
            assert call(0x115acc, (0x66000000, 0x66001000)) == 0
            assert word(0x66001000) == phase
            assert list(struct.unpack('<2I', u.mem_read(0x6600100c, 8))) == [px, py]
            put(0x60008000, 0)
            call(0xf6cd0, (0x66002000, 0x66001000, 0, 0))
            call(0xe9690, (0x60000000, 0x66002000))
            touch_trace.append({'contact': contact, 'native_phase': phase,
                                'decoded_pixel': [px, py], 'pending_count': word(leaf + 0x498)})
        pending_types = [word(word(leaf + 0x480 + i * 4) + 4) for i in range(word(leaf + 0x498))]
        if args.reopen_manager and args.ack_manager_close and pending_types!=[0x11,0x14,0x13,0x14]:
            gap={'scope':'Same-memory command6/APF-ack then mode0 reopen, second input incomplete','menu':menu,'cycle':rebuild_cycle,'pending_types':pending_types,'touch_trace':touch_trace,'manager_flags':hex(word(0x60000004)),'restored_input_mask':word(0x6bafb8),'saved_input_mask':word(0x613f00+0x5f18),'limits':['Original13e04 restored saved mask; no direct manager flag clearing attempted.','Mode0 reopened and Home rebuilt, but full command7 input/event registration not integrated.','OS/IPC services remain virtual; not a hardware failure claim.']}
            (ROOT/'sources/native-home-manager-reopen-input-gap.json').write_text(json.dumps(gap,indent=2)+'\n')
        assert pending_types == ([] if args.touch_outside else [0x11, 0x14, 0x13, 0x14]),(menu,rebuild_cycle,pending_types,word(0x60000004),word(0x6bafb8),touch_trace)
        buffer, records = 0x66003000, 0x66004000
        u.mem_write(buffer,bytes(24)) # Fresh caller-owned collection output, including count0.
        put(buffer + 0x10, 64)
        put(buffer + 0x14, records)
        assert call(0xef1d4, (root, buffer)) == 0
        collected_types = [word(records + i * 0x2b0 + 8) for i in range(word(buffer + 8))]
        assert collected_types == ([8] if args.touch_outside else [8, 0x11, 0x14, 0x13, 0x14])
        selected_metadata = [] if args.touch_outside else list(struct.unpack('<15I', u.mem_read(records + 3 * 0x2b0 + 0x1c, 60)))
        if not args.touch_outside:
            assert selected_metadata == new_metadata
        assert word(leaf + 0x498) == 0
        # Browser and state contexts are supplied; use the real constructed descriptor.
        consumer = 0x65010000
        put(consumer + 0xea48, 1)
        put(consumer + 0x2ff8, menu)
        for unused_slot in range(1, 4):
            put(consumer + 0x2ff8 + unused_slot * 0x2e94, 0xffffffff)
        put(consumer + 0x2b18 + menu * 8, descriptor)
        u.mem_write(consumer + 0x2ff8 + 0x20, bytes(u.mem_read(buffer, 24)))
        call(0x2c4bc, (consumer,))
        assert selection_events == ([] if args.touch_outside else [[0x2010b, 0, new_index, menu]])
        context = bytearray(32)
        context[0], context[1], context[13] = 1, 11, 10
        struct.pack_into('<I', context, 4, 0x3ea150)
        put(0x613e4c, menu + 1)
        for stage in (() if args.touch_outside else ('gui', 'home')):
            if stage == 'home':
                context[0], context[1] = 0x33, 2
                struct.pack_into('<I', context, 4, 0x3f55d8)
            u.mem_write(0x66002000, bytes(context))
            event = selection_events[-1]
            call(0x17c608, (0x66002000, event[0], event[2], event[3]))
        if not args.touch_outside:
            assert selection_events[-1] == [0x4a0111, 0, new_index, menu]
        assert switch_requests == ([] if args.touch_outside else [[0x30001, 0, 0]])
        rows.append({'menu': menu,'rebuild_cycle':rebuild_cycle, 'native_root_factory': '0x1096e0', 'native_object_allocator': '0xe9300','reserved_root_present':args.native_open_root,'outer_mode0_open_returned':args.native_open_complete,'command7_restore_trace':resume_trace.copy(),'command7_events':[e.copy() for e in resume_events],'native_page_rebuild_executed':args.native_page_rebuild,'native_page_rebuild_services':[v.copy() for v in page_rebuild_services],'virtual_page_frames':virtual_page_frames.copy(),'recovery_frame_pixels':frame_pixel_allocations.copy(),'command7_activation_acks':[a.copy() for a in resume_acks],'command7_thread_requests':[t.copy() for t in resume_threads],'command7_worker_services':resume_worker_services.copy(),'native_input_restorations':native_input_restorations.copy(),
                     'native_pending_object_count': pending_after_creation,
                     'native_pending_after_pool_commit': word(0x60000788),
                     'native_active_after_pool_commit': word(0x6000037c),
                     'native_descriptor_created_state': word(descriptor + 0x98),
                     'native_valid_slots': valid_slots, 'native_new_entry_metadata': new_metadata,
                     'native_new_entry_control_created': True,
                     'native_child_list_storage_distinct': True,
                     'root_position': root_position, 'content_size': content_size,
                     'content_position_after_init': content_position_after_init,
                     'content_position_after_update_prefix': content_position,
                     'native_new_entry_position_after_update_prefix': entry_position,'native_entry_preupdate_position':local_entry,'native_leaf_preupdate_position':local_leaf,
                     'native_new_entry_hit_bounds': entry_bounds,
                     'native_full_dispatch_touch_trace': touch_trace,
                     'native_pending_action_types': pending_types,
                     'native_root_collected_action_types': collected_types,
                     'native_root_collected_selection_metadata': selected_metadata,
                     'native_selection_events': [e.copy() for e in selection_events],
                     'native_switch_requests': [e.copy() for e in switch_requests],
                     'capacity_constructor_argument': d[0x27], 'native_model_capacity': word(model),
                     'native_factory_styles': styles.copy(), 'cell_centers_in_current_content': centers})
        if args.native_switch_client:rows[-1]['native_switch_wire_requests']=[e.copy() for e in switch_wire_requests]
        if args.native_name_lookup:rows[-1]['native_lookup_wire_requests']=[e.copy() for e in lookup_wire_requests]
        if args.native_activation_route:rows[-1]['native_activation_route']={'events':[e.copy() for e in activation_route_events],'coordinator_calls':[e.copy() for e in activation_route_calls],'module_calls':activation_route_modules.copy(),'pending_registered':[e.copy() for e in activation_route_pending],'delivery_order':activation_route_delivery.copy(),'root_initialization':root_initialization,'native_receiver':activation_receiver_info,'native_battery_query_requests':[entry.copy() for entry in battery_wire_requests],'native_argument_query_requests':[entry.copy() for entry in argument_wire_requests],'other_modules_virtual':True}
        if args.close_gui:
            assert word(0x65000000) == 1 and word(descriptor + 0x98) == 1
            close_status = call(0x109a24, (0x65000000,))
            assert close_status == 0 and word(0x65000000) == 0 and word(descriptor + 0x98) == 0
            rows[-1]['native_gui_close'] = {'procedure':'0x109a24','status':close_status,
                                          'gui_manager_state_after':word(0x65000000),
                                          'descriptor_created_after':word(descriptor + 0x98)}
        if args.close_manager:
            resource_manager = call(0x1072c0, ())
            assert call(0x1072cc, (resource_manager,)) == 0
            # Supplied runtime bookkeeping, not a full UI/display startup.
            put(0x60000374, (383 if args.native_open_root else 384) * 0x1348)
            put(0x60029ba8, 0xffffffff)
            put(0x5ff134, 1)
            put(0x7dca00, 17)
            put(0x7dca04, 0x67000000)
            if args.consume_manager_close:
                if not rebuild_cycle:u.mem_map(0x68000000,4096)
                put(0x4f7820,0x68000000)
                put(0x613f00+0x5eb0,1)
                put(0x6bafb8,7)
                lifecycle_running = True
                if args.native_activation_route:
                    stop_route_events.clear();stop_route_calls.clear();stop_route_modules.clear();stop_route_pending.clear();stop_gui_results.clear();stop_gui_tokens.clear()
                    stop_snapshot_services.clear();stop_snapshot_times.clear();stop_snapshot_submissions.clear();stop_snapshot_gate_states.clear()
                    for index,(procedure,offset) in enumerate(resume_modules):put(0x613e60+offset,0x613f00 if procedure==0x143c0 else 0x68001000+index*32)
                    put(0x613e60+0x2c,0x68000900);put(0x613e60+0x14,0x68000a00)
                    assert word(0x683324)==0x683328 and bytes(u.mem_read(0x683328,32))==consumer_context_before_home
                    stop_route_running=True;stop_route_stage='forward'
                    assert word(0x820f68+4)==2
                    receiver_notice=(20,0,6,0,0)
                    stop_receiver_received=0;stop_receiver_returned=False;stop_receiver_callbacks.clear();stop_receiver_running=True
                    u.reg_write(UC_ARM_REG_R0,0x820f68);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
                    u.emu_start(0x26551c,0x50000000,count=100000)
                    stop_receiver_running=False
                    assert stop_receiver_received==1 and stop_receiver_returned and stop_receiver_callbacks==['0xeb9c']
                    assert stop_route_events==[[0x420024,0,0,0]]
                    packet=stop_route_events[-1];assert call(0x17c608,(0x6833dc,packet[0],packet[2],packet[3]))==0
                    assert stop_route_events==[[0x420024,0,0,0],[0x430113,0,6,0]]
                    saved_mode=word(0x613e2c+32);put(0x613e2c+32,0)
                    packet=stop_route_events[-1];assert call(0x17c608,(0x683328,packet[0],packet[2],packet[3]))==0
                    assert bytes(u.mem_read(0x683328,32))==consumer_context_before_home
                    put(0x613e2c+32,saved_mode)
                    assert stop_route_events[-1]==[0x420032,0,0x683348,0]
                    snapshot_before_submission=bytes(u.mem_read(0x683348,108));assert word(0x683348+36)==1
                    stop_route_stage='command';packet=stop_route_events[-1]
                    assert call(0x17c608,(0x6833dc,packet[0],packet[2],packet[3]))==0
                    stop_route_running=False
                    assert len(stop_gui_results)==1 and stop_route_calls[0][:2]==[0x613e60,6]
                    assert stop_gui_tokens==[0x206];close_token=stop_gui_tokens[0]
                    assert stop_route_modules==[hex(p) for p,offset in resume_modules]
                    assert stop_route_pending==[[0x68000900,0x206]] and word(0x68000900)==1
                    assert stop_snapshot_times==[[985,0]] and stop_snapshot_submissions==[snapshot_before_submission.hex()]
                    assert stop_snapshot_gate_states==[2]
                else:
                    assert call(0x143c0,(0x613f00,6,0x68000800)) == 0
                    close_token=word(0x68000800)
                assert close_token == 0x206 and lifecycle_events == [[0x20111,0,0,0]]
                if args.ack_manager_close:
                    if not args.native_activation_route:
                        put(0x613e60+4,6)
                        put(0x613e60+8,0)
                        put(0x613e60+0x2c,0x68000900)
                        put(0x613e60+0x14,0x68000a00)
                        assert call(0x48a14,(0x68000900,close_token)) == 0
                assert call(0x57d50,()) == 2
                assert lifecycle_events == [[0x20111,0,0,0],[0x420034,0,0x206,0]]
                assert word(0x60000000) == 1 and word(0x60000378) == 20
                assert word(0x613f00+0x5eb0) == 0 and word(0x613f00+0x5f18) == 7 and word(0x6bafb8) == 0
                if args.ack_manager_close:
                    event = lifecycle_events[-1]
                    assert call(0x71ee4,(0,event[0],event[2],event[3])) == 0
                    assert word(0x68000900) == 0 and lifecycle_events[-1] == [0x41000a,0,0,0]
                    client = 0x820f68
                    for offset,value in ((0,1),(4,2),(12,55),(16,500)):
                        if args.command7_ack and rebuild_cycle:assert word(client+offset)==value
                        else:put(client+offset,value)
                    main_context = bytearray(32)
                    main_context[0],main_context[1],main_context[13] = 3,4,6
                    struct.pack_into('<I',main_context,4,0x3ef680)
                    if args.command7_ack and rebuild_cycle:assert list(u.mem_read(0x68000c00,2))==[3,4]
                    else:u.mem_write(0x68000c00,bytes(main_context))
                    event = lifecycle_events[-1]
                    assert call(0x17c608,(0x68000c00,event[0],event[2],event[3])) == 0
                    assert list(bytes(u.mem_read(0x68000c00,2))) == [2,2]
                    assert word(client+4) == 1 and lifecycle_acks == [[24,apf_requests[-1][1],1,1,55,1]],(word(client+4),lifecycle_acks,apf_requests,list(u.mem_read(0x68000c00,16)))
            else:
                assert call(0xe8b7c, (0x60000000,)) == 0
                assert word(0x60000000) == 0xffffffff
            assert word(0x65000000) == 0 and word(descriptor + 0x98) == 0
            assert word(0x7dca04) == 0 and word(0x5ff134) == 0
            syscalls = [item for item in close_trace if 'call' in item]
            assert syscalls[-2:] == [{'call':'munmap','address':'0x67000000','bytes':0x500000}, {'call':'close','fd':17}]
            if args.consume_manager_close:
                assert next(i for i,item in enumerate(close_trace) if item.get('call') == 'close') < next(i for i,item in enumerate(close_trace) if item.get('queued') == [0x420034,0,0x206,0])
            assert [item['virtual_presentation'] for item in close_trace if 'virtual_presentation' in item] == ['0x115f68','0x11600c','0x115f68','0x11600c']
            rows[-1]['native_manager_close'] = {'procedure':'0xe8b7c','trace':[item.copy() for item in close_trace],
                                               'manager_state_after':word(0x60000000),
                                               'gui_state_after':word(0x65000000),
                                               'descriptor_created_after':word(descriptor + 0x98)}
            if args.consume_manager_close:
                rows[-1]['native_manager_close']['via_command6_consumer'] = True
                if args.native_activation_route:rows[-1]['native_manager_close']['native_stop_route']={'callback_entry':'0xeb9c','callback_invoked_by_harness':False,'native_receiver':'0x26551c','native_registration':True,'notification_fixture':[20,0,6,0,0],'returned_to_receive':stop_receiver_returned,'events':[e.copy() for e in stop_route_events],'coordinator_calls':[e.copy() for e in stop_route_calls],'module_calls':stop_route_modules.copy(),'pending_registered':[e.copy() for e in stop_route_pending],'consumer_initialization':{'constructor':'0x6dec0','context':'0x683328','mode_state':[1,1],'context_byte13':11,'constructed_before_first_home':True,'context_preserved':True},'snapshot_mode_field_fixture':0,'snapshot_native_gate_client_states':stop_snapshot_gate_states.copy(),'snapshot_submissions_virtual':stop_snapshot_submissions.copy(),'snapshot_service_fixtures':stop_snapshot_services.copy(),'snapshot_converted_times':stop_snapshot_times.copy(),'snapshot_apf_transport_executed':True,'snapshot_wire_requests':[entry.copy() for entry in snapshot_wire_requests],'other_eight_modules_virtual':True,'root_context_retained':True}
                rows[-1]['native_manager_close']['other_mocked_cleanup_boundaries'] = cleanup_boundaries.copy()
            if args.ack_manager_close:
                assert next(i for i,item in enumerate(close_trace) if item.get('call') == 'close') < next(i for i,item in enumerate(close_trace) if 'apf_ack' in item)
                rows[-1]['native_manager_close']['apf_ack_requests'] = [a.copy() for a in lifecycle_acks]
                rows[-1]['native_manager_close']['client_state_after'] = word(0x820f68+4)
                rows[-1]['native_manager_close']['all_apf_requests']=[a.copy() for a in apf_requests]
    if args.native_cancel_predicate:assert native_cancel_checks and all(v==0 for v in native_cancel_checks)
    if args.native_home_assets:
        assert sorted(frame_pixel_allocations)==sorted(frame_pixel_frees),(len(frame_pixel_allocations),len(frame_pixel_frees))
        before_asset_release=word(0x7a0660+0x30294)
        assert before_asset_release==(0 if args.native_asset_handoff else 139),before_asset_release
        assert call(0xf6c30,(catalog,0))==0
        assert word(0x7a0660)==0 and word(0x7a0660+0x30294)==0
        assert asset_file_releases==['munmap','close']*(1+8*(home_cycle_count-1) if args.native_worker_assets else home_cycle_count if args.native_asset_handoff else 1),asset_file_releases
        copy_requests=[q for q in frame_image_requests if q['caller']=='0xf6220']
        assert copy_requests and all(q['dimensions_format'][:2]==[78,78] for q in copy_requests),copy_requests
        rows[-1]['native_asset_lifecycle']={'file_sha256':hashlib.sha256(asset_data).hexdigest(),'group0_records':139,'worker_loaded_groups':worker_group_requests.copy(),'native_cancel_checks':native_cancel_checks.copy(),'file_group_events':[e.copy() for e in asset_file_group_events],'asset51_handles_by_load':asset51_handles.copy(),'native_command6_catalog_release':args.native_asset_handoff,'copy_requests':copy_requests,'pixel_allocations':len(frame_pixel_allocations),'pixel_releases':len(frame_pixel_frees),'logical_mapping_bytes_total':sum(pixel_lengths.values()),'images_before_group_release':before_asset_release,'images_after_group_release':0,'file_releases':asset_file_releases.copy(),'image_pool_capacity':1024 if args.stock_resource_pools else 512,'group_pool_capacity':16 if args.stock_resource_pools else 1,'pool_capacity_from_original_initializer':args.stock_resource_pools,'pixel_arena_bytes_fixture':0x1000000}
report = {'candidate_sha256': digest,'native_mode0_reserved_root':args.native_open_root, 'cases': rows,
          'virtual_sort_equal_order': 'reversed' if args.reverse_equal_sort else 'preserved',
          'touch_target': 'outside-new-entry' if args.touch_outside else 'new-entry-center',
          'limits': ['Original GUI manager init/open, index-pool init/pop, descriptor/root factory, object/rectangle allocation and list initialization execute; backing storage, manager getter and libc remain virtual.',
                     'Active default-view allocation is supplied; no original global manager startup or full scheduler.',
                     'Position prefix eea80..eeb68 executes for content/new control/leaf, then native hit-bound refresh. Other controls, full updates/animation/layout/scroll and actual page display remain unqualified.',
                     'Original e8de8..e8e58 commits pending object flags/counts; later frame/update/render code is not executed. Pool-active is not a page-visibility proof.',
                     'Virtual ioctl contact/release pass through original 115acc/f6cd0/full e9690 on the native 104-node pool and bounded updated new-entry position; libc qsort uses a virtual stable implementation of ef8f0 ordering, auxiliary33c528 returns0. Tie-order independence, full frame/layout/visibility and physical touch remain unqualified.',
                     'Original root collection ef1d4/f1b08 and browser2c4bc consume the actual touch-produced records in this replay; GUI/Home contexts are supplied and event delivery is manually pumped through17c608. APF lookup/change and action-consumption side effects are virtual; no process switch or hardware return occurs.',
                     'No hardware access or flashable image is generated; actual display/page rendering remains unqualified.']}
if args.native_cancel_predicate:
    report['limits'].append('Original3365bc initializes supplied ticket storage, owner binding supplied;117fc/109e4/336640 execute native cancellation reads. This Home replay does not request cancellation; concurrent cancellation/USB/APF source unqualified.')
if args.native_worker_assets and not args.native_cancel_predicate:
    report['limits'].append('Second-cycle original resume worker loads actual8-group/550-image set before Home construction; no pre-command7 reload. Mode getter supplies0, cancel callback117fc supplies no cancellation, status UI f5714 and display post-load helpers virtual. First startup only group0; actual process/driver/full native page state machine excluded.')
if args.stock_resource_pools and not args.native_worker_assets:
    report['limits'].append('Original11e9b8 initializes16 group slots and1024 image slots; no host pool-capacity writes in this mode. File/OS/IPC and16MiB virtual pixel arena remain fixtures; only group0 asset load is joined here.')
if args.native_home_assets and not args.stock_resource_pools:
    report['limits'].append('Real group0 DAT loads/maps/registers through original code in the same emulator; directory enumeration and file/allocator/libc virtual. Resource pool capacity512 and16MiB monotonic backing are fixtures, not device RAM claims; allocated pixel buffers and group resources are checked released. Other asset groups and actual drawing unqualified.')
if args.native_open_root and not args.native_open_complete:
    report['limits'].append('Original mode0 e9388 prefix creates reserved type1 root and pool capacity383 before Home, total105 controls. Stops before module startup at e948c; no full-open return, display initialization or APF reactivation proof.')
if args.command7_reopen and not args.command7_worker:
    report['limits'].append('Original143c0 command7 drives120ec/b586c/20110/5cfb4/13e04;12ef8 backend is intercepted and rebuilt explicitly later in the harness. Auxiliary GUI services virtual;20670/token207 is observed but async activation worker/completion is not consumed in this case.')
if args.native_page_rebuild and not args.native_recovery_frames:
    report['limits'].append('Original12ef8 executes close/capacity383/mode0-open/callback registration in the command7 call. Frame factoryb5f88 returns two virtual handles; auxiliary page/subsystem services remain virtual. Home1096e0 construction still follows explicitly in harness, not through the complete native Home page state machine.')
if args.command7_ack and not args.native_page_rebuild:
    report['limits'].append('Actual worker420034/token207 passes native pending removal/PCS boundary/410009/main/APF activation ack. Main2/2 and client1 come from previous close; accepted virtual reply gives client2, next close returns1. IPC, PCS and completion helpers remain virtual; reconstruction12ef8 still deferred.')
if args.command7_worker and not args.command7_ack:
    report['limits'].append('Original GUI20670 consumer requests thread13f38, scheduled manually; worker11a04 runs with 4e388/3ce08/3d6dc/b4964/b4a54/b52dc virtual. Actual20671 is delivered to original GUI transition3->4;420034 token207 observed but coordinator/APF activation ack not consumed. Page rebuild12ef8 remains deferred harness boundary.')
if args.native_open_complete:
    report['limits'].append('Original outer mode0 open e9388 returns0, opens GUI and starts receiver; display setup/backing are virtual and other manager/view prerequisites remain supplied.')
if args.reopen_manager:
    assert [(r['menu'],r['rebuild_cycle']) for r in rows]==[(m,c) for m in (0,1) for c in range(3 if args.three_home_cycles else 2)]
    report['limits'].append('Two whole-manager close/mode0-open/Home cycles per menu share emulator memory. Receiver initialization10487c executes before open; supplied OS backing/pools are re-established. Native b586c(0) from120ec restores event mode before second open;13e04 restores saved mask. Full command7 dispatch, real external app/driver/APF transport remain excluded.')
if args.reopen_home:
    assert [(r['menu'],r['rebuild_cycle']) for r in rows]==[(m,c) for m in (0,1) for c in range(3 if args.three_home_cycles else 2)]
    report['limits'].append('Reopen mode rebuilds twice within the same emulator per menu. GUI-page close only; object backing/pool fixtures reused. Full UI-manager close/reopen, physical remap, APF reactivation and command7 are not integrated.')
if args.close_gui:
    report['limits'].append('Original GUI-manager close executes on the constructed Home and changes descriptor/manager state to0. This is not full e8b7c manager shutdown; pool unmap, display close and APF lifecycle are not executed here.')
if args.close_manager:
    report['limits'].append('Original e8b7c/GUI/control cleanup and115ee8/14a3f0 execute. Empty resource cache initialized natively; object-pool byte count, display-active flag, display mapping/fd and no-worker handle supplied. sysconf/munmap/close and two final presentation pairs are virtual. No actual unmap/driver drain/worker cleanup or APF return qualification.')
if args.consume_manager_close:
    report['limits'].append('Original143c0 command6 and57d50/13dd0/12fd4 execute before/through native manager cleanup, then emit completion206. Other page/subsystem cleanup helpers are mocked, event consumer manually pumped and initial module/backend/input state supplied. Actual unmap/close success, rendering drain and APF ack not qualified.')
if args.ack_manager_close:
    report['limits'].append('Native pending registration/removal and actual-generated41000a feed main/APF ack after display-close request. Initial main3/4/client2 supplied; PCS/IPC/reply and transition helpers virtual. Actual manager acceptance and hardware release unqualified.')
if args.native_switch_client:
    report['all_bounded_checks_passed']=True
    report['source_hashes']={'tools/check_home_parent.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    report['limits'].append('Original switch client executes with active client2 and initial sequence0 supplied; switch seq0 precedes inactive ack seq1 in this same instance. Lookup ID and actual IPC replies remain virtual.')
if args.native_name_lookup:
    report['source_hashes'][lookup_source['path']]=lookup_source['sha256']
    report['source_hashes']['tools/native_lookup_fixture.py']=hashlib.sha256((ROOT/'tools/native_lookup_fixture.py').read_bytes()).hexdigest()
    report['limits'].append('Original1574c parses current staged AppList in the same lookup emulator before1084c; stdio/accounts/string/allocation/IPC boundaries virtual, core state2 supplied. Client seq0 lookup, seq1 switch, seq2 inactive ack.')
if args.native_activation_route:
    report['source_hashes']['tools/native_alarm_fixture.py']=hashlib.sha256((ROOT/'tools/native_alarm_fixture.py').read_bytes()).hexdigest()
    report['source_hashes']['work/targets-jp/sysmgrd']=hashlib.sha256((ROOT/'work/targets-jp/sysmgrd').read_bytes()).hexdigest()
    report['limits'].append('Snapshot operation20 uses original client and separate persistent original-manager alarm model; actual replies shift client sequence. Clocks/locks/transport/persistence virtual; not the application-manager process instance.')
suffix = ('-lookup-client' if args.native_name_lookup else '') + ('-switch-client' if args.native_switch_client else '') + ('-stock-pools' if args.stock_resource_pools else '') + ('-handoff' if args.native_asset_handoff else '') + ('-assets' if args.native_home_assets else '') + ('-catalog' if args.native_resource_catalog else '') + ('-frames' if args.native_recovery_frames else '') + ('-native-rebuild' if args.native_page_rebuild else '') + ('-activation-ack' if args.command7_ack else '') + ('-worker' if args.command7_worker else '') + ('-command7' if args.command7_reopen else '') + ('-manager-reopen' if args.reopen_manager else '') + ('-open-complete' if args.native_open_complete else '-open-root' if args.native_open_root else '') + ('-reopen' if args.reopen_home else '') + ('-outside' if args.touch_outside else '') + ('-reverse-sort' if args.reverse_equal_sort else '') + ('-close' if args.close_gui else '') + ('-ack-manager-close' if args.ack_manager_close else '-consumer-manager-close' if args.consume_manager_close else '-manager-close' if args.close_manager else '')
if args.native_worker_assets:suffix=('-native-ticket' if args.native_cancel_predicate else '')+'-worker-assets'+('-outside' if args.touch_outside else '')
if args.native_frame_update:
    suffix='-frame-update'
    report['native_frame_update']={'original_view_binding_loop':'0xe88c8..0xe8900','frame_procedure':'0xe8de8','stop_before_receiver':'0xe8ed8','position_prefix_replayed_separately':False,'float_helpers_virtual':['__aeabi_i2f','__aeabi_fdiv','__aeabi_fmul','__aeabi_f2iz'],'physical_display_validated':False}
    report['limits']=[line for line in report['limits'] if not line.startswith('Position prefix eea80') and not line.startswith('Original e8de8..e8e58')]
    report['limits'].append('Original view binding and frame processing through e8ed8 execute before input and close on both cycles. Relative factory positions are captured before frame and checked against native absolute positions; no separate prefix replay. IEEE float imports virtual. Final receiver scheduling, actual framebuffer rendering/presentation, animation and hardware remain unqualified.')
if args.native_frame_receiver:
    suffix='-activation-route-frame-receiver' if args.native_activation_route else '-lookup-frame-receiver' if args.native_name_lookup else '-frame-receiver'
    report['native_frame_receiver']={'frame_returns':True,'scheduling':frame_schedule_records,'physical_display_validated':False}
    report['limits']=[line.replace('Final receiver scheduling, actual framebuffer rendering/presentation, animation and hardware remain unqualified.','Actual framebuffer rendering/presentation, animation and hardware remain unqualified; see native_frame_receiver for CPU queue scheduling.') for line in report['limits']]
    report['limits'].append('Full original e8de8 returns after104a14/resource getter1072c0/107514/104f64. Queue scheduling is native but callbacks, files, OS synchronization and float helpers remain supplied; not actual thread scheduling or physical display recovery.')
if args.native_activation_route:
    report['native_activation_route']=True
    report['limits'].append('Original APF receiver/callback, constructed Root and coordinator enter original GUI resume. Client/manager query instructions execute with supplied records/cache; module objects and other module-command services virtual. Event/thread delivery scheduled, not physical OS/hardware.')
if args.three_home_cycles:
    suffix+='-three-cycles';report['home_cycles_per_menu']=3
    report['limits'].append('Third Home cycle supplies a second original recovery acknowledgement. Per-cycle observations reset; client/Root/consumer/query-service state retained. Existing GUI-context/backing fixtures remain; no full stock boot or real process loop.')
if activation_frame_input:
    suffix+='-captured-activation'
    report['activation_frame_input']=activation_frame_input
    report['source_hashes'][activation_frame_input['path']]=activation_frame_input['sha256']
    report['limits'].append('Activation receiver bytes come from captured original manager return notification via separate original framing model; destination registry and delivery remain fixtures, not a live IPC connection.')
(ROOT / f'sources/native-home-parent{suffix}.json').write_text(json.dumps(report, indent=2) + '\n')
print(str(len(rows))+' bounded Home cases verified; content252x400, capacity49 and new entry constructed')
