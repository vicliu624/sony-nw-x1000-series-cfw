"""Original command7 coordinator and pending-request collection, virtual modules."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native-gui-resume',action='store_true')
parser.add_argument('--consume-gui-resume',action='store_true')
parser.add_argument('--complete-gui-resume',action='store_true')
parser.add_argument('--dispatch-gui-resume',action='store_true')
parser.add_argument('--finish-gui-transition',action='store_true')
parser.add_argument('--native-resume-worker',action='store_true')
parser.add_argument('--worker-error',type=int,default=0)
parser.add_argument('--ack-activation',action='store_true')
parser.add_argument('--reject-activation',action='store_true')
parser.add_argument('--root-reactivation',action='store_true')
parser.add_argument('--activation-callback',action='store_true')
parser.add_argument('--ordered-activation',action='store_true')
parser.add_argument('--consume-battery-event',action='store_true')
parser.add_argument('--native-resume-slot',action='store_true')
parser.add_argument('--native-page-coordinator',action='store_true')
parser.add_argument('--native-frame-factory',action='store_true')
parser.add_argument('--frame-child-failure',action='store_true')
parser.add_argument('--native-frame-initializer',action='store_true')
parser.add_argument('--native-frame-base',action='store_true')
parser.add_argument('--native-frame-pixels',action='store_true')
parser.add_argument('--native-resource-register',action='store_true')
parser.add_argument('--release-frames',action='store_true')
parser.add_argument('--home-state-transition',action='store_true')
parser.add_argument('--native-home-preparation',action='store_true')
parser.add_argument('--complete-registry-initialization',action='store_true')
parser.add_argument('--native-page-request',action='store_true')
parser.add_argument('--native-page-manager',action='store_true')
parser.add_argument('--native-home-template',action='store_true')
parser.add_argument('--native-template-transition',action='store_true')
parser.add_argument('--native-template-dispatch',action='store_true')
parser.add_argument('--native-view-pool',action='store_true')
parser.add_argument('--native-view-startup-prefix',action='store_true')
parser.add_argument('--native-manager-init',action='store_true')
parser.add_argument('--native-receiver-init',action='store_true')
parser.add_argument('--native-frame-receiver',action='store_true')
parser.add_argument('--native-frame-activation',action='store_true')
parser.add_argument('--native-frame-child',action='store_true')
parser.add_argument('--native-attach-dispatch',action='store_true')
parser.add_argument('--native-graphics-context',action='store_true')
parser.add_argument('--native-activation-queues',action='store_true')
parser.add_argument('--native-receiver-start',action='store_true')
parser.add_argument('--native-upstream-init',action='store_true')
parser.add_argument('--native-upstream-message',action='store_true')
parser.add_argument('--native-processor-registration',action='store_true')
parser.add_argument('--native-upstream-reject',action='store_true')
parser.add_argument('--native-upstream-completion',action='store_true')
args=parser.parse_args()
assert not args.native_upstream_completion or args.native_upstream_reject
assert not args.native_upstream_reject or (args.native_upstream_message and args.native_processor_registration)
assert not args.native_processor_registration or args.native_upstream_init
assert not args.native_upstream_message or args.native_upstream_init
assert not args.native_upstream_init or args.native_receiver_start
assert not args.native_receiver_start or args.native_activation_queues
assert not args.native_activation_queues or args.native_graphics_context
assert not args.native_graphics_context or args.native_attach_dispatch
assert not args.native_attach_dispatch or args.native_frame_child
assert not args.native_frame_child or args.native_frame_activation
assert not args.native_frame_activation or args.native_frame_receiver
assert not args.native_frame_receiver or (args.native_receiver_init and args.native_frame_base)
assert not args.native_receiver_init or args.native_manager_init
assert not args.native_manager_init or args.native_view_startup_prefix
assert not args.native_view_startup_prefix or args.native_view_pool
assert not args.native_view_pool or args.native_template_dispatch
assert not args.native_template_dispatch or args.native_template_transition
assert not args.native_template_transition or args.native_home_template
assert not args.native_home_template or args.native_page_manager
assert not args.native_page_manager or args.native_page_request
assert not args.native_page_request or (args.native_home_preparation and args.complete_registry_initialization)
assert not args.complete_registry_initialization or (args.native_frame_base and args.native_page_coordinator)
assert not args.native_home_preparation or args.home_state_transition
assert not args.home_state_transition or (args.finish_gui_transition and args.native_resume_slot)
assert not args.release_frames or (args.native_resource_register and args.consume_gui_resume)
assert not args.native_resource_register or args.native_frame_pixels
assert not args.native_frame_pixels or args.native_frame_base
assert not args.native_frame_base or args.native_frame_initializer
assert not args.native_frame_initializer or (args.native_frame_factory and not args.frame_child_failure)
assert not args.frame_child_failure or args.native_frame_factory
assert not args.native_frame_factory or args.native_page_coordinator
assert not args.native_page_coordinator or args.native_gui_resume
assert not args.native_resume_slot or args.consume_gui_resume
assert not args.consume_battery_event or args.ordered_activation
assert not args.ordered_activation or (args.activation_callback and args.consume_gui_resume)
assert not args.activation_callback or args.root_reactivation
assert not args.root_reactivation or args.native_gui_resume
assert not args.ack_activation or args.complete_gui_resume
assert not args.reject_activation or args.ack_activation
assert not args.native_resume_worker or args.consume_gui_resume
assert not args.worker_error or args.native_resume_worker
assert not args.finish_gui_transition or args.dispatch_gui_resume
assert not args.dispatch_gui_resume or args.consume_gui_resume
assert not args.complete_gui_resume or args.consume_gui_resume
assert not args.consume_gui_resume or args.native_gui_resume
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
dynamic_symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def branch_target(address):
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address < segment['p_vaddr'] + segment['p_filesz']:
            at = segment['p_offset'] + address - segment['p_vaddr']
            instruction = struct.unpack_from('<I', raw, at)[0]
            assert instruction >> 24 == 0xea
            displacement = instruction & 0xffffff
            if displacement & 0x800000:
                displacement -= 0x1000000
            return address + 8 + displacement * 4
    raise AssertionError('Branch outside original image')
assert branch_target(0xac420) == dynamic_symbols['pcs_channel_get_list']
assert branch_target(0xac580) == dynamic_symbols['pcs_channel_set_accessed_flag']
modules = [(0x16b74, 0xc), (0x143c0, 0x10), (0xf32c, 0x18),
           (0x3b498, 0x1c), (0x37f08, 0x20), (0x49d6c, 0x38),
           (0x4492c, 0x28), (0x499f8, 0x34), (0x4f3dc, 0x40)]
rows = []
for pending in ([None] if args.native_gui_resume else [None, 'already-busy', 'pcs', 'native-pcs'] + [pc for pc, offset in modules]):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    if args.native_page_coordinator:u.mem_map(0xe60000,0x2000)
    if args.native_frame_initializer:u.mem_map(0x61000000,0x10000)
    if args.native_frame_pixels:u.mem_map(0x62000000,0x100000)
    ctx, tracker, result = 0x613e60, 0x60010000, 0x60003000
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    put(ctx + 0x2c, tracker)
    put(ctx + 4, 99)
    put(tracker, int(pending == 'already-busy'))
    objects = {pc: 0x60004000 + i * 256 for i, (pc, offset) in enumerate(modules)}
    for pc, offset in modules:
        put(ctx + offset, objects[pc])
    restore_trace=[];thread_requests=[];resume_work=[];worker_services=[];ack_packets=[];slot_services=[];page_running=False;page_services=[];manager_open_requests=[];manager_capacity_requests=[];page_handles=[];frame_resources=[];frame_controls=[];pixel_mappings=[];resource_headers=[];resource_names=[];pixel_unmaps=[];home_running=False;home_services=[];home_page_requests=[];page_manager_requests=[];page_manager_services=[];home_template_calls=[];template_packets=[];template_dispatch_effects=[];frame_receiver_calls=[];graphics_qsort_counts=[];upstream_pumping=False;upstream_deliveries=[];upstream_validation_returns=[];upstream_completion_path=[]
    if args.native_gui_resume:
        objects[0x143c0]=0x613f00
        put(ctx+0x10,0x613f00)
        put(0x613f00+0x5eb0,0)
        put(0x613f00+0x5f18,7)
        put(0x6bafb8,0)
        context=bytearray(32);context[0]=1;context[1]=2;context[13]=10
        struct.pack_into('<I',context,4,0x3ea150)
        u.mem_write(0x60012000,bytes(context));put(0x68233c,0x60012000)
    if args.native_page_coordinator:
        put(0x613f00+0x5eb8,0);put(0x613f00+0x5ebc,0)
    if args.native_resume_slot:put(0x613f00+0x48,0x6001b000)
    put(ctx + 0x14, 0x60008000)
    put(0x60008004, 0x60009000)
    dirty_cache = (0, 24, 49)
    if pending == 'native-pcs':
        for i in dirty_cache:
            u.mem_write(0x691bd0 + i * 24, struct.pack('<6I', 1, 0x60001000 + i * 64,
                                                     0x60002000 + i * 64, 2, 3, 4))
    if args.native_template_dispatch and not args.native_view_pool:
        # Supplied active-view fixture: ebb74 requires record+108 bit0.
        # This is not execution of the original GUI-manager startup.
        put(0x6dfa18+8,0)
        put(0x6dfa28+108,1)
    calls, events, completion, released, pcs_refresh = [], [], [], [], []
    def hook(uc, pc, size, data):
        global page_running
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        answer=0
        if args.native_upstream_completion and upstream_pumping and pc in (0x104de8,0x104e94,0xe9690):
            upstream_completion_path.append(hex(pc));return
        if args.native_upstream_message and pc==0xe1e0:
            left=bytes(u.mem_read(a[0],a[2]));right=bytes(u.mem_read(a[1],a[2]))
            uc.reg_write(UC_ARM_REG_R0,0 if left==right else 1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_upstream_reject and upstream_pumping and pc==0x1055f8:
            upstream_validation_returns.append(uc.reg_read(UC_ARM_REG_R0));return
        if args.native_upstream_message and upstream_pumping and pc==0x104c20:
            upstream_deliveries.append({'receiver':hex(a[0]),'envelope_type':word(a[1]+72),'word76':word(a[1]+76)})
            if args.native_upstream_completion:return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_graphics_context and pc==0xdc94:
            assert a[1]<=1 and a[2]==4,a
            graphics_qsort_counts.append(a[1])
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_frame_receiver and pc in (0xef1a0,0xecd6c,0xef5dc):
            frame_receiver_calls.append(hex(pc));return
        if home_running and args.native_template_dispatch and pc in (0x1160c8,0x1160e0):
            assert a[0]==0x806,a
            template_dispatch_effects.append({'pc':hex(pc),'argument':hex(a[0])});uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and args.native_template_dispatch and pc in (0xeb87c,0xeb84c):
            template_dispatch_effects.append({'pc':hex(pc),'target':hex(a[0]),'value':hex(a[1])});return
        if home_running and args.native_template_transition and pc==0xe9690:
            assert a[0]==0x6dfa18
            packet=bytes(u.mem_read(a[1],676));template_packets.append({'words0_3':list(struct.unpack('<4I',packet[:16])),'sha256':hashlib.sha256(packet).hexdigest()})
            if args.native_template_dispatch:return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and args.native_home_template and pc==0xa953c:
            assert a[0]==0x691b50;home_template_calls.append(a[0]);return
        if home_running and args.native_home_template and pc in (0xaa994,0xaaa38,0xaab70):
            home_services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and args.native_page_manager and pc in (0xe0170,0xe01a4,0xe02ec,0xe0e00):
            page_manager_services.append({'pc':hex(pc),'args':a,'virtual':not ((args.native_home_template and pc==0xe0170) or (args.native_template_transition and pc==0xe02ec))})
            if (args.native_home_template and pc==0xe0170) or (args.native_template_transition and pc==0xe02ec):return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and args.native_page_request and pc==0xdf3b4:
            assert a[:3]==[0xe601e0,33,0] and word(a[0]+0x2e8)==45,a
            page_manager_requests.append(a[:3])
            if args.native_page_manager:return
            uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and args.native_home_preparation and pc==0xa9160:return
        if home_running and args.native_home_preparation and pc in (0x52354,0x52ac4,0x14e20,0x4dd20):
            if pc==0x14e20:
                home_page_requests.append(a[:2])
                if args.native_page_request:return
            home_services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if home_running and pc in (0x4c73c,0x49804,0xa9160,0xb52dc):
            home_services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        if args.native_frame_factory and pc==0xb5f88:
            assert a[0] in (9,49)
            page_handles.append({'request':a[0],'handle':hex(0x75cf44+104*len(page_handles))});return
        if args.release_frames and pc==0xd934:
            assert a[0] in pixel_mappings and a[1]==208896,a
            pixel_unmaps.append(a[0])
        elif args.native_resource_register and pc==0xdb08:
            answer=len(bytes(u.mem_read(a[0],128)).split(b'\0')[0])
        elif args.native_resource_register and pc==0x3397f4:
            fmt=bytes(u.mem_read(a[3],128)).split(b'\0')[0].decode()
            value=word(uc.reg_read(UC_ARM_REG_SP));text=(fmt%value).encode()
            assert a[1]==16 and a[2]==0 and len(text)<16,(fmt,a)
            u.mem_write(a[0],text+b'\0');resource_names.append(text);answer=len(text)
        elif args.native_frame_pixels and pc==0xe09c:
            assert bytes(u.mem_read(a[0],10))==b'/dev/zero\x00' and a[1]==0
            answer=17
        elif args.native_frame_pixels and pc==0xe324:assert a[0]==30;answer=4096
        elif args.native_frame_pixels and pc==0xdafc:
            assert a==[0,208896,3,2],a
            answer=0x62000000+len(pixel_mappings)*0x40000;pixel_mappings.append(answer)
        elif args.native_frame_pixels and pc==0xd6f4:assert a[0]==17
        elif args.native_frame_pixels and pc==0x11f18c:
            assert a[0]==0x7a0660 and a[2]!=0,a
            if args.native_resource_register:
                resource=len(frame_resources);frame_resources.append(resource);resource_headers.append(0x7a0660+0x192a4+resource*88);return
            resource=100+len(frame_resources);header=0x61008000+len(frame_resources)*64
            u.mem_write(header,bytes(u.mem_read(a[1],64)));resource_headers.append(header)
            put(a[2],resource);frame_resources.append(resource)
        elif args.native_frame_initializer and pc==0x133028:
            assert a[:3]==[240,432,2],a
            if args.native_frame_pixels:return
            resource=100+len(frame_resources);put(a[3],resource);frame_resources.append(resource)
        elif args.native_frame_initializer and pc==0xedea8:
            assert a[0] in (0x61000000,0x61001348) and a[1]==21,a
            frame_controls.append(hex(a[0]))
            if args.native_frame_base:return
            put(a[0]+0xae4,21)
        elif args.native_frame_base and pc==0xd574:
            u.mem_write(a[0],bytes([a[1]&255])*a[2]);answer=a[0]
        elif args.native_frame_base and pc in (0x1090b4,0xef3d8,0x109404,0xf7dfc,0xf7e34,0xedb34,0xede84):pass
        elif args.native_frame_initializer and pc==0xd85c:
            u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));answer=a[0]
        elif args.native_frame_initializer and pc==0x1334f8:pass
        elif args.frame_child_failure and pc==0xe9300:
            page_services.append('virtual_child_control_allocation_null')
        elif args.native_frame_factory and pc==0x112878:
            assert a[0] in (0x75cf44,0x75cfac) and a[2:]==[240,432],a
            center=list(struct.unpack('<3I',uc.mem_read(a[1],12)));assert center==[120,216,0],center
            flags=word(uc.reg_read(UC_ARM_REG_SP));assert flags in (9,49)
            if args.native_frame_initializer:
                page_services.append('native_frame_initializer112878');return
            if args.frame_child_failure:
                page_services.append('native_frame_initializer112878_failure');return
            put(a[0]+0x4c,1);page_services.append('virtual_frame_initializer112878')
        elif args.native_page_coordinator and pc==0x12fcc:page_running=False;return
        elif args.native_page_coordinator and page_running and pc in (0x33d8c0,0xb4b9c,0xb54e8,0xb4b84,0xa7a0c,0xb5034,0x48f38,0x48fe4,0x4a584,0x4a630,0x3ce08,0x3d6dc,0x3dda4,0xb523c,0xb5f88):
            page_services.append(hex(pc))
            if pc==0xb4b84:manager_open_requests.append(a[0])
            if pc==0xb54e8:manager_capacity_requests.append(a[0])
            if pc==0xb5f88:
                assert a[0] in (9,49),a
                answer=0x6001e000+len(page_handles)*256;page_handles.append({'request':a[0],'handle':hex(answer)})
        elif args.native_resume_slot and pc==0x4e388:return
        elif args.native_resume_slot and pc in (0xdde70,0xddeb0,0xde3c0):
            answer=0x6001c000 if pc==0xdde70 else 0
            if pc!=0xdde70:slot_services.append({'service':hex(pc),'code':a[1]})
        elif args.activation_callback and pc==0xb07e8:
            put(a[0],0);put(a[0]+4,0)
        elif args.activation_callback and pc==0xb0bdc:put(a[0],0)
        elif args.activation_callback and pc in (0xe5ac,0x3b2b8,0xe600):pass
        elif args.ack_activation and pc==0x268c9c:
            values=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            assert values[:2]==[500,55] and values[3]==24
            packet=list(struct.unpack('<6I',uc.mem_read(values[2],24)))
            assert packet==[24,0,1,1,55,2],packet
            ack_packets.append(packet)
        elif args.ack_activation and pc==0x268d48:
            values=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            assert values[0]==500 and values[2]==16
            uc.mem_write(values[1],struct.pack('<4I',16,0,1,0x1d04 if args.reject_activation else 0));put(values[3],16)
        elif args.ack_activation and pc in (0x337a80,0x337ae8,0xb00bc,0x265298):pass
        elif args.native_resume_worker and pc==0x11a04:return
        elif args.native_resume_worker and pc in (0x3ce08,0x3d6dc,0xb4964,0xb4a54,0xb52dc):
            worker_services.append({'pc':hex(pc),'args':a})
            if pc==0xb4964:
                assert a[1]==0x117fc,a
                answer=args.worker_error
        elif args.consume_gui_resume and pc==0x337534:
            assert a==[0x13f38,0x613efc,8,0x18000],a
            assert word(0x613efc)==0x207
            thread_requests.append(a)
        elif args.consume_gui_resume and pc in (0x4e388,0x11a04):
            resume_work.append(hex(pc))
        elif args.native_gui_resume and pc in (0x120ec,0x120d8,0x5cfb4,0x13e04):
            restore_trace.append(hex(pc));return
        elif args.native_gui_resume and pc==0x12ef8:
            assert word(0x6bafb8)==0 and word(0x613f00+0x5eb0)==1
            restore_trace.append('page-rebuild-service')
            if args.native_page_coordinator:page_running=True;return
        elif args.native_gui_resume and pc in (0xb586c,0x51828,0x49984,0x497b4,0xb4a10):pass
        elif pc in objects:
            assert a[:2] == [objects[pc], 7]
            calls.append(pc)
            if args.native_gui_resume and pc==0x143c0:return
            put(a[2], 0xabc if pending == pc else 0)
        elif pc == 0x1fd30:
            assert a[:2] == [0x60008000, 7]
            calls.append(pc)
            if pending == 'native-pcs':
                return  # Execute original PCS dispatcher, command7 body and cache clearing.
            put(a[2], 0xdef if pending == 'pcs' else 0)
        elif pc in (0x2991bc, 0xe0e4):
            released.append((pc, a[0]))
        elif pc == 0x21f30:
            assert a[0] == 0x60009000
            pcs_refresh.append(pc)
        elif pc == 0xa57f0:
            events.append(a)
        elif pc in (0x10e68, 0x140b4):
            completion.append(pc)
        elif pc not in (0xff5c, 0x116d4, 0x33b83c, 0x335788, 0x3357e4, 0x17c42c, 0x33b918, 0xe30f8):
            return
        uc.reg_write(UC_ARM_REG_R0, answer)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    if args.native_view_pool:
        def view_call(pc,*values):
            for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),values):u.reg_write(reg,value)
            u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
            u.emu_start(pc,0x50000000,count=10000)
            assert u.reg_read(UC_ARM_REG_PC)==0x50000000
            return u.reg_read(UC_ARM_REG_R0)
        if args.native_view_startup_prefix:
            manager_init_services=[]
            def startup_hook(uc,pc,size,data):
                virtual=(0x115e28,0x1053c4,0x105fb8,0x112008,0x1072cc,0x109524,0x106f98,0x10945c,0x109460,0x109464,0xf6488,0x10e410,0xec478)
                if args.native_upstream_init:virtual=tuple(x for x in virtual if x!=0x106f98)
                if args.native_receiver_init:virtual=tuple(x for x in virtual if x not in (0x1053c4,0x105fb8))
                if args.native_manager_init and pc in virtual:
                    manager_init_services.append(hex(pc))
                    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
                elif pc==0x115e28:
                    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
                elif pc==0xe8900 and not args.native_manager_init:uc.emu_stop()
            prefix_hook=u.hook_add(UC_HOOK_CODE,startup_hook)
            u.reg_write(UC_ARM_REG_R0,0x6dfa18);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
            u.emu_start(0xe8800,0x50000000,count=100000)
            u.hook_del(prefix_hook)
            assert u.reg_read(UC_ARM_REG_PC)==(0x50000000 if args.native_manager_init else 0xe8900)
            if args.native_manager_init:
                assert word(0x732d3c+0x46c)==0xe9690 and word(0x732d3c+0x470)==0xe8794 and word(0x732d3c+0x474)==0xe87bc and word(0x732d3c+0x478)==0x6dfa18
            if args.native_receiver_init:
                receiver=0x732d3c;queue=0x733208
                assert word(receiver)==0xffffffff and word(receiver+20)==0x104c20 and word(receiver+24)==receiver and word(receiver+0x180)==0
                assert [word(queue+0x1b000+i) for i in (4,8,12,16,20,24,28,32)]==[228,28,0,0,0x700000,0x200000,0,0]
            assert word(0x6dfa24)==2 and word(0x6dfa18+0x364)==0x6dfa28 and word(0x6dfa18+0x368)==0x6dfb44
            assert view_call(0xebb74,0x6dfa20)==0x6dfa28
            for record in (0x6dfa28,0x6dfb44):
                assert word(record+108)&1 and word(record+128)==120 and word(record+132)==216 and word(record+136)==0xffffff38
        else:
            view_call(0xeba18,0x6dfa20)
            assert word(0x6dfa24)==0
            allocated=[view_call(0xeba80,0x6dfa20) for _ in range(3)]
            assert allocated==[0x6dfa28,0x6dfb44,0x6dfc60],allocated
            assert view_call(0xeba80,0x6dfa20)==0 and word(0x6dfa24)==3
            view_call(0xebb30,0x6dfa20,allocated[2])
            assert view_call(0xebb74,0x6dfa20)==allocated[2]
            view_call(0xebadc,0x6dfa20,allocated[2])
            view_call(0xebadc,0x6dfa20,allocated[1])
            view_call(0xebb30,0x6dfa20,allocated[0])
            assert view_call(0xebb74,0x6dfa20)==allocated[0] and word(0x6dfa24)==1
    if args.complete_registry_initialization:
        for reg,value in ((UC_ARM_REG_R0,0),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
        u.emu_start(0x14d0c,0x50000000,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        assert word(0xe601e0)==16 and word(0xe601e0+0x44)==81 and word(0xe601e0+0x2e8)==45

    if args.native_graphics_context:
        for reg,value in ((UC_ARM_REG_R0,0x761394),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
        u.emu_start(0x119258,0x50000000,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        assert word(0x761394+0xc158)==0x761394+0xc15c
    if args.native_frame_initializer:
        put(0x6dfa18+0x370,0x61000000)
        for reg,value in ((UC_ARM_REG_R0,0x6dfa18+0x380),(UC_ARM_REG_R1,2),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
        u.emu_start(0x104730,0x50000000,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000

    if args.native_resource_register:
        for reg,value in ((UC_ARM_REG_R0,0x7a0660+0x2f28c),(UC_ARM_REG_R1,4),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
        u.emu_start(0x132938,0x50000000,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
    for reg, value in [(UC_ARM_REG_R0, ctx), (UC_ARM_REG_R1, 7), (UC_ARM_REG_R2, result),
                       (UC_ARM_REG_SP, 0x60018000), (UC_ARM_REG_LR, 0x50000000)]:
        u.reg_write(reg, value)
    activation_events=[]
    if args.activation_callback:
        u.emu_start(0xeaa0,0x50000000,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        activation_events=[e.copy() for e in events]
        assert activation_events==[[0x420011,0,1,0],[0x420023,0,0,0]],activation_events
        events.clear()
    entry=0x112fc
    if args.root_reactivation:
        root_context=bytearray(32);root_context[0]=2;root_context[1]=1;root_context[13]=10
        struct.pack_into('<I',root_context,4,0x3f4f18);u.mem_write(0x60013000,bytes(root_context))
        if args.ordered_activation:
            first=activation_events[0]
            for reg,value in ((UC_ARM_REG_R0,0x60013000),(UC_ARM_REG_R1,first[0]),(UC_ARM_REG_R2,first[2]),(UC_ARM_REG_R3,first[3]),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(reg,value)
            u.emu_start(0x17c608,0x50000000,count=100000)
            assert u.reg_read(UC_ARM_REG_PC)==0x50000000
            first_root_events=[e.copy() for e in events]
            assert first_root_events==[[0x20303,0,1,0],[0x580101,0,1,0]],first_root_events
            events.clear()
        for reg,value in ((UC_ARM_REG_R0,0x60013000),(UC_ARM_REG_R1,activation_events[1][0] if args.activation_callback else 0x420023),(UC_ARM_REG_R2,activation_events[1][2] if args.activation_callback else 0),(UC_ARM_REG_R3,activation_events[1][3] if args.activation_callback else 0)):u.reg_write(reg,value)
        entry=0x17c608
    u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    try:u.emu_start(entry, 0x50000000, count=100000)
    except Exception as exc:raise AssertionError((hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),page_services)) from exc
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and u.reg_read(UC_ARM_REG_R0) == 0
    if pending == 'already-busy':
        assert not calls and word(ctx + 4) == 99 and not events and not completion
    else:
        assert word(ctx + 4) == 7
        assert calls[:9] == [pc for pc, offset in modules]
        if args.native_gui_resume:
            assert len(calls)==9 and word(tracker)==1 and word(tracker+4)==0x207
            assert (args.root_reactivation or word(result)==1) and not completion
            assert events==[[0x20670,0,0x207,0]]
        elif isinstance(pending, int):
            assert len(calls) == 9 and word(tracker) == 1 and word(tracker + 4) == 0xabc
            assert word(result) == 1 and not events and not completion
        elif pending == 'pcs':
            assert calls[-1] == 0x1fd30 and word(tracker) == 1 and word(tracker + 4) == 0xdef and word(ctx + 8) == 1
            assert not events and not completion
        else:
            assert calls[-1] == 0x1fd30 and word(tracker) == 0,(calls,word(tracker),events,restore_trace)
            assert events == ([[0x20670,0,0x207,0],[0x410009,0,0,0]] if args.native_gui_resume else [[0x410009, 0, 0, 0]]) and completion == [0x10e68, 0x140b4]
    if pending == 'native-pcs':
        assert pcs_refresh == [0x21f30]
        assert released == [(pc, base + i * 64) for i in dirty_cache
                            for pc, base in ((0x2991bc, 0x60001000), (0xe0e4, 0x60002000))]
        assert bytes(u.mem_read(0x691bd0, 50 * 24)) == bytes(50 * 24)
    if args.native_gui_resume:
        assert word(0x6bafb8)==7 and word(0x613f00+0x5eb0)==1
        assert restore_trace==['0x120ec','0x120d8','0x5cfb4','page-rebuild-service','0x13e04'],restore_trace
    if args.consume_gui_resume:
        def invoke(pc,values):
            for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(reg,value)
            u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
            try:u.emu_start(pc,0x50000000,count=100000)
            except Exception as exc:
                if args.native_attach_dispatch:
                    failure={'scope':'Failed native attach notification replay, not a passing check','pc':hex(u.reg_read(UC_ARM_REG_PC)),'lr':hex(u.reg_read(UC_ARM_REG_LR)),'registers_r0_r1':[hex(u.reg_read(r)) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)],'graphics_owner':'0x761394','graphics_context_offset':'0xc158','graphics_context_pointer':hex(word(0x761394+0xc158)),'last_instructions':frame_child_trace.copy(),'limits':['Graphics prelude115e28 remains virtual; native graphics context initialization enabled: '+str(args.native_graphics_context),'No additional mappings or guessed graphics context supplied.','No device code or firmware changed.']}
                    (ROOT/'sources/native-attach-dispatch-failure.json').write_text(json.dumps(failure,indent=2)+'\n')
                raise AssertionError((hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),restore_trace, [hex(u.reg_read(r)) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)], hex(word(0x6dfa20)),template_dispatch_effects)) from exc
            assert u.reg_read(UC_ARM_REG_PC)==0x50000000
        if args.ordered_activation:
            event=first_root_events[0]
            invoke(0x17c608,(0x60012000,event[0],event[2],event[3]))
            assert word(0x613f00+0x56d8)==1
            if args.consume_battery_event:
                battery_context=bytearray(32);battery_context[0]=1;battery_context[1]=1;battery_context[13]=24
                struct.pack_into('<I',battery_context,4,0x412b70);u.mem_write(0x6001a000,bytes(battery_context));put(0x671c40+32,0)
                event=first_root_events[1];before_events=[e.copy() for e in events]
                invoke(0x17c608,(0x6001a000,event[0],event[2],event[3]))
                assert word(0x671c40+32)==1 and events==before_events

        if args.dispatch_gui_resume:
            gui_before=list(u.mem_read(0x60012000,2))
            invoke(0x17c608,(0x60012000,0x20670,0x207,0))
            gui_after=list(u.mem_read(0x60012000,2))
            assert gui_before==[1,2] and gui_after==[1,3],(gui_before,gui_after)
        else:
            invoke(0x5cf90,(0,0x20670,0x207,0))
        assert len(thread_requests)==1
        invoke(thread_requests[0][0],(thread_requests[0][1],0,0,0))
        assert events[-2:]==[[0x20671,0,0,0],[0x420034,0,0x207,0]],events
        assert word(tracker)==1
        worker_events=[e.copy() for e in events[-2:]]
        if args.finish_gui_transition:
            before_finish_events=len(events)
            invoke(0x17c608,(0x60012000,worker_events[0][0],worker_events[0][2],worker_events[0][3]))
            gui_finished=list(u.mem_read(0x60012000,2))
            assert gui_finished==[1,4],gui_finished
            gui_entry_events=[e.copy() for e in events[before_finish_events:]]
            assert gui_entry_events==[],gui_entry_events
        pending_trace=[word(tracker)]
        if args.complete_gui_resume:
            actual=worker_events[-1]
            before_events=[e.copy() for e in events]
            invoke(0x71ee4,(0,actual[0],0x999,0))
            assert word(tracker)==1 and events==before_events and not completion
            invoke(0x71ee4,(0,actual[0],actual[2],actual[3]))
            pending_trace.append(word(tracker))
            assert pending_trace==[1,0]
            assert calls[-1]==0x1fd30 and completion==[0x10e68,0x140b4]
            assert events[-1]==[0x410009,0,0,0]
    if args.ack_activation:
        client=0x820f68;main_context=0x60011000
        for offset,value in ((0,1),(4,1),(12,55),(16,500)):put(client+offset,value)
        main=bytearray(32);main[0]=2;main[1]=2;main[13]=6;struct.pack_into('<I',main,4,0x3ef680)
        u.mem_write(main_context,bytes(main));actual=events[-1];assert actual[0]==0x410009
        invoke(0x17c608,(main_context,actual[0],actual[2],actual[3]))
        main_after=list(u.mem_read(main_context,2));client_after=native_client_state=word(client+4)
        assert main_after==[3,4] and client_after==(1 if args.reject_activation else 2) and len(ack_packets)==1
    rows.append({'pending_fixture': hex(pending) if isinstance(pending, int) else pending,
                 'module_calls': [hex(pc) for pc in calls], 'pending_count': word(tracker),
                 'output_pending': None if args.root_reactivation else word(result), 'events': events,
                 'completion_helpers': [hex(pc) for pc in completion]})
    if args.native_gui_resume:rows[-1]['native_restore_trace']=restore_trace
    if args.consume_gui_resume:rows[-1].update({'thread_requests':thread_requests,'mocked_resume_work':resume_work,'worker_completion_events':worker_events,'pending_count_trace':pending_trace,'unmatched_token_does_not_complete':bool(args.complete_gui_resume)})
    if args.dispatch_gui_resume:rows[-1]['native_gui_transition']={'before':gui_before,'after':gui_after}
    if args.activation_callback:rows[-1]['native_activation_callback_events']=activation_events
    if args.ordered_activation:rows[-1].update({'first_root_event_children':first_root_events,'gui_status_value_after':word(0x613f00+0x56d8),'unconsumed_aux_event':None if args.consume_battery_event else first_root_events[1]})
    if args.root_reactivation:rows[-1]['root_entry']={'event':'0x420023','initial_mode_state':[2,1],'after':list(u.mem_read(0x60013000,2))}
    if args.ack_activation:rows[-1].update({'apf_activation_packets':ack_packets,'main_after':main_after,'client_after':client_after,'virtual_manager_accepts':not args.reject_activation})
    if args.native_page_coordinator:
        expected_handles=[{'request':9,'handle':'0x75cf44'},{'request':49,'handle':'0x75cfac'}] if args.native_frame_factory else [{'request':9,'handle':'0x6001e000'},{'request':49,'handle':'0x6001e100'}]
        assert page_handles==expected_handles,page_handles
        assert word(0xe601e0+0x1304)==0x14a14 and word(0xe601e0+0x1308)==0x14b74
        expected_first=0 if args.frame_child_failure else int(expected_handles[0]['handle'],16)
        expected_second=0 if args.frame_child_failure else int(expected_handles[1]['handle'],16)
        assert word(0x613f00+0x5eb8)==expected_first and word(0x613f00+0x5ebc)==expected_second
        if args.native_frame_factory:assert word(0x75cf44+0x138)==(0 if args.frame_child_failure else 2)
        assert manager_open_requests==[0] and manager_capacity_requests==[383],(manager_open_requests,manager_capacity_requests)
        rows[-1].update({'native_page_services':page_services,'manager_open_modes':manager_open_requests,'manager_requested_capacities':manager_capacity_requests,'page_handles':page_handles,'registered_backend_callbacks':['0x14a14','0x14b74']})
    if args.native_frame_initializer:
        assert frame_resources==([0,1,2,3] if args.native_resource_register else [100,101,102,103]) and frame_controls==['0x61000000','0x61001348']
        assert word(0x75cf44)==0x61000000 and word(0x75cfac)==0x61001348 and word(0x6dfa18+0x788)==2
        rows[-1].update({'native_frame_controls':frame_controls,'virtual_frame_resources':frame_resources,'native_gui_pool_count':2})
    if args.native_frame_pixels:
        assert len(pixel_mappings)==4 and len(resource_headers)==4
        for header,pixels in zip(resource_headers,pixel_mappings):
            assert word(header)==240 and word(header+4)==432 and word(header+8)==2
            assert word(header+16)==pixels and word(header+40)==207360
            assert bytes(u.mem_read(pixels,207360))==bytes(207360)
        rows[-1]['native_pixel_buffers']={'count':4,'logical_bytes_each':207360,'mapped_bytes_each':208896,'resource_registration_still_virtual':not args.native_resource_register}
    if args.native_resource_register:
        assert word(0x7a0660+0x30294)==4 and word(0x7a0660+0x30298)==4
        assert len(resource_names)==4
        for resource in range(4):
            assert bytes(u.mem_read(0x7a0660+0x19290+88*resource,16))==hashlib.md5(resource_names[resource]).digest()
            assert word(0x7a0660+0x1928c+88*resource)==1 and word(0x7a0660+0x192a0+88*resource)==1
        rows[-1]['native_resource_registry']={'ids':frame_resources,'registered_count':4,'reference_counts':[1,1,1,1],'pool_capacity_fixture':4}
    if args.native_frame_base:
        for control in (0x61000000,0x61001348):
            assert word(control+0xae4)==21 and word(control+0x4b0)==0x112500
        rows[-1]['native_frame_base_callbacks']={'type':21,'destructor':'0x112500','set_by_native_constructor':True}
    if args.frame_child_failure:
        rows[-1]['frame_factory_attempts']=page_handles
        rows[-1]['page_handles']=[{'request':9,'handle':'0x0'},{'request':49,'handle':'0x0'}]
        rows[-1]['frame_failure_result']={'frame_count':word(0x75cf44+0x138),'slot_flags':[word(0x75cf44+0x4c+i*104) for i in range(3)],'input_after':word(0x6bafb8)}
        assert rows[-1]['frame_failure_result']['slot_flags']==[1,1,0]
    if args.native_resume_slot:
        assert word(0x6001b010)==1 and word(0x6001b00c)==5 and slot_services==[{'service':'0xddeb0','code':5}]
        rows[-1]['native_resume_slot_calls']=slot_services
    if args.native_resume_worker:
        expected=[0x3ce08,0x3d6dc,0xb4964]+([] if args.worker_error else [0xb4a54,0xb52dc])
        assert [int(x['pc'],16) for x in worker_services]==expected,worker_services
        rows[-1].update({'native_worker_service_boundaries':worker_services,'worker_service_error_fixture':args.worker_error,'completion_still_emitted':True})
    if args.finish_gui_transition:rows[-1].update({'native_gui_finished':gui_finished,'native_gui_entry_events':gui_entry_events})
    if pending == 'native-pcs':
        rows[-1]['native_cache_slots_cleared'] = 50
        rows[-1]['virtual_resource_release_calls'] = len(released)
        rows[-1]['pcs_refresh_helper'] = '0x21f30 (intercepted)'
report = {'scope': 'Original command7 coordinator/collector/completion branch; module and completion services mocked',
          'SpiderApp_sha256': digest, 'coordinator': '0x112fc', 'cases': rows,
          'final_subsystem_imports': ['pcs_channel_get_list', 'pcs_channel_set_accessed_flag'],
          'identity_correction': 'Final subsystem is PCS channel data; its 50-slot cleanup is not display-cache restoration evidence.',
          'limits': ['Subsystems are virtual; one PCS fixture executes 1fd30/1f02c/cache cleanup, but 21f30 and resource frees are intercepted.',
                     'Pending completion delivery and retry are not exercised.',
                     'This proves original coordination conditions, not real restoration or timing.']}
if args.native_gui_resume:
    report['scope']='Native command7 coordinator -> native GUI selector/producer/dispatcher/restore callback; page and auxiliary services virtual'
    report['limits']=['Initial GUI state2, owner inactive, saved input7 are fixtures.', 'Page rebuild and other GUI auxiliary services are mocked; no display or touch hardware.', 'Native tracker retains token0x207 and queues20670; async consumer and completion remain to be executed.', 'Other modules are virtual; no complete APF or hardware restoration proof.']
if args.consume_gui_resume:
    report['limits']=['GUI20670 handler5cf90 called directly; dispatcher selection checked separately, transition/entry not executed.', 'Native1402c requests worker13f38 with token207; thread creation virtual and worker scheduled manually after handler returns.', 'Worker11a04 and handler4e388 remain mocked; their actual UI/service work is unqualified.', 'Original worker emits20671 then420034(token207); tracker remains1 because completion event not consumed yet.', 'Other modules and page rebuild virtual; no physical hardware or complete APF restoration proof.']
if args.complete_gui_resume:
    report['limits']=['Native71ee4/11250/48a78 consume the actual worker token207 and remove pending1 to0.', 'PCS command7 and final completion helpers10e68/140b4 are mocked; native coordinator emits410009.', 'Worker manually scheduled; GUI state transition, page rebuild, worker11a04 and handler4e388 not qualified.', 'No actual APF completion acknowledgement or physical display/input restoration proof.']
if args.dispatch_gui_resume:
    report['limits'].append('Native GUI dispatch of20670 executes handler and transition [mode1,state2] to[mode1,state3]; this replaces direct-handler limitation for20670 only.')
if args.finish_gui_transition:
    report['limits'].append('Native20671 dispatch transitions3 to4 without additional queued events in this context fixture; entry5ce30 was not observed and is not claimed executed.')
if args.native_resume_worker:
    report['limits'].append('Worker11a04 executes stock orchestration and118a0 mapping;3ce08/3d6dc/b4964/b4a54/b52dc remain service mocks. Worker emits completion even with nonzero b4964, so completion does not prove service success.')
if args.ack_activation:
    report['limits'].append('Actual emitted410009 fed into native main dispatcher/activation ack; initial main2/2 and client1 supplied. IPC/locks virtual. Main becomes3/4 even when virtual manager rejects; client distinguishes acceptance.')
if args.root_reactivation:
    report['scope']='Original root420023 ->command7 ->GUI recovery and optional native completion/APF with virtual boundaries'
    report['limits']=['Root initial2/1, GUI1/2 inactive and saved input7 are fixtures; initial APF main/client also supplied.', 'Root event origin/actual manager IPC not executed; event itself supplied.', 'Other modules, page reconstruction, PCS and final auxiliary helpers remain mocked; no hardware qualification.']
    if args.consume_gui_resume:report['limits'].append('Original worker manually scheduled through virtual thread creation; services mocked.')
    if args.dispatch_gui_resume:report['limits'].append('Native20670 dispatch executes GUI2 to3.')
    if args.finish_gui_transition:report['limits'].append('Native20671 dispatch executes GUI3 to4; no entry5ce30 observed.')
    if args.complete_gui_resume:report['limits'].append('Actual worker token207 is consumed, unmatched999 cannot complete, tracker1 to0;410009 emitted.')
    if args.ack_activation:report['limits'].append('Actual410009 executes native APF ack request; manager reply/locks/transport virtual. Main3/4 does not alone prove acceptance.')
if args.activation_callback:
    report['limits'].append('Original activation callbackeaa0 generates420011/420023 with virtual argv and battery-query responses; only produced420023 consumed by root in this test.420011 consumer remains outside scope. APF receive/registration not integrated.')
if args.ordered_activation:
    report['limits'].append('Both callback events consumed by root in order;20303 child consumed by GUI before20670. Auxiliary580101 remains pending; no claim of fully drained event queue.')
if args.consume_battery_event:
    report['limits']=[x for x in report['limits'] if 'only produced420023' not in x and 'Auxiliary580101 remains pending' not in x]
    report['limits'].append('Callback420011/420023 root delivery and20303/580101 consumers execute in FIFO order before20670; battery object previous0 and module state1 supplied, no threshold-crossing branch. This does not establish global queue delivery or hardware battery refresh.')
if args.native_resume_slot:
    report['limits'].append('4e388 and slot wrappers execute natively; owner+48 points to supplied inactive object. Downstream manager getter/start/stop virtual; slot1 ends active with code5.')
if args.native_page_coordinator:
    report['limits'].append('Native12ef8/14d74 and119a0/11938 plus registry setters execute; backend callbacks registered but not invoked. Auxiliary page initialization, handle allocator and other listed services remain virtual; input restore still follows this coordinator.')
if args.native_frame_factory:
    report['limits'].append('Nativeb5f88/111ffc/112050 select two frame-pool records and increase count2; center120/216, dimensions240/432 andflags9/49 verified. Frame initializer112878 mocked; no image/control creation or actual rendering.')
if args.frame_child_failure:
    report['limits'].append('Native112878 executes with child allocator e9300 returningnull; both frame results0, successful count0, first two slot flags1. Despite this, original orchestration restores input and reaches APF request under other virtual services. Not actual successful UI restoration.')
if args.native_frame_initializer:
    report['limits'].append('Native112878 success path ande9300 GUI pool allocation execute; two controls allocated from capacity2 fixture. Resource allocation133028, base constructor21,memcpy and1334f8 remain virtual; no actual textures or drawing.')
if args.native_frame_base:
    report['limits'].append('Nativeedea8 executes for both type21 controls and installs destructor112500; auxiliary field initializers, resource allocation, memory services and1334f8 still virtual; no textures/drawing or actual device qualification.')
if args.native_frame_pixels:
    report['limits'].append('Native133028/11f4b8/120220/11fa18/132a78 create4 format2 buffers; virtual OS mmap backed by Unicorn memory. Resource registration11f18c still virtual, copied headers checked; no actual drawing or device mappings.')
if args.native_resource_register:
    report['limits'].append('Native11f18c/11ef8c resource registration,1329c0 pool and1326d0 digest execute; four actual resource records/IDs/refcounts verified. Capacity4 and formatting/memory/OS services virtual; no actual rendering or resource destruction yet.')
if args.native_frame_receiver:
    control=word(0x75cf44)
    assert control==0x61000000 and word(control+0x4a0)==0xecd6c
    # The supplied backing/pool capacity is two controls, not stock capacity384.
    put(0x6dfa18+0x378,2)
    frame_child_bridges=[];frame_child_trace=[]
    def child_bridge(uc,pc,size,data):
        frame_child_trace.append(hex(pc));del frame_child_trace[:-24]
        if args.native_attach_dispatch and pc in (0xe9690,0x1124b4):return
        if pc in (0xe9690,0x1124b4):
            frame_child_bridges.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    if args.native_frame_child:
        child_control=word(0x75cfac)
        bridge_hook=u.hook_add(UC_HOOK_CODE,child_bridge)
        invoke(0x112a8c,(0x75cf44,child_control,1,0));u.hook_del(bridge_hook)
        assert word(0x75cf44+0x44)==1 and word(0x75cf44+4)==child_control
    activation_services=[];activation_callbacks=[];nonempty_frame_branches=[];activation_pump_returns=[]
    def stop_after_activation(uc,pc,size,data):
        if args.native_frame_activation:
            if pc in (0xe8d5c,0x104a14,0x107514,0x104f64):
                activation_services.append(hex(pc))
                if args.native_activation_queues and pc!=0xe8d5c:return
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            elif pc in (0xef208,0x112560):activation_callbacks.append(hex(pc))
            elif pc==0x11259c:nonempty_frame_branches.append(hex(pc))
            elif args.native_activation_queues and pc==0x105538:activation_pump_returns.append(uc.reg_read(UC_ARM_REG_R0))
        elif pc==0xe8e58:uc.emu_stop()
    if args.native_activation_queues:
        assert word(0x732d3c+0x180)==0 and word(0x733208+0x1b00c)==0 and word(0x733208+0x1b010)==0
        assert word(0x7540a8+0xa0c)==0 and word(0x7540a8+0xa10)==0
    if args.native_processor_registration:
        invoke(0x1d374,(0,0,0,0))
        assert [word(0x732d3c+i) for i in (0,4,8,12,16)]==[0,0x1cdec,0x1cf58,0x1d27c,0x1d35c]
    if args.native_receiver_start:
        invoke(0x10490c,(0x732d3c,0,0,0))
        assert word(0x732d3c+0x180)==1 and word(0x74e22c)==0
        assert word(0x74e22c+0x5e74)==0x732d3c
    if args.native_upstream_message:
        payload=0x6001d100;header=0x6001d000
        u.mem_write(payload,bytes(272));raw_header=bytearray(84)
        struct.pack_into('<I',raw_header,64,payload)
        if args.native_upstream_reject:struct.pack_into('<I',raw_header,72,0x800)
        u.mem_write(header,bytes(raw_header))
        invoke(0x107034,(0x74e22c,header,0,0))
        assert word(0x74e22c)==1
        upstream_pumping=True
        upstream_states=[]
        for _ in range(4):
            invoke(0x104f64,(0x732d3c,1,0,0))
            upstream_states.append([word(0x74e22c),word(0x732d3c+0x180)])
            if upstream_states[-1]==[0,1]:break
        upstream_pumping=False
        if word(0x74e22c)!=0 or word(0x732d3c+0x180)!=1:
            evidence={'scope':'Unfinished native upstream message replay, not passing validation','states_count_receiver':upstream_states,'deliveries':upstream_deliveries,'receiver_slot0_words':[hex(word(0x732d3c+i)) for i in (0,4,8,12,16)],'limits':['Message header/payload supplied; zero processing function is not an asynchronous completion proof.','No forced state advance, completion bit or dequeue inserted.','Receiver remains state2 and count1, requiring a real processing/completion path.']}
            (ROOT/'sources/native-upstream-message-pending.json').write_text(json.dumps(evidence,indent=2)+'\n')
        assert word(0x74e22c)==0 and word(0x732d3c+0x180)==1,(word(0x74e22c),word(0x732d3c+0x180),upstream_deliveries)
        assert len(upstream_deliveries)==1,upstream_deliveries
        if args.native_upstream_reject:assert upstream_validation_returns==[10],upstream_validation_returns
    activation_hook=u.hook_add(UC_HOOK_CODE,stop_after_activation)
    u.reg_write(UC_ARM_REG_R0,0x6dfa18);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    u.emu_start(0xe8de8,0x50000000,count=10000);u.hook_del(activation_hook)
    assert u.reg_read(UC_ARM_REG_PC)==(0x50000000 if args.native_frame_activation else 0xe8e58)
    assert word(0x6dfa18+0x37c)==2 and word(0x6dfa18+0x788)==0
    if args.native_frame_activation:
        assert activation_callbacks==['0xef208','0x112560']*2,activation_callbacks
        assert activation_services==['0x104a14','0x107514','0x104f64'],activation_services
        assert word(0x75cf44+0x44)==int(args.native_frame_child) and word(0x75cfac+0x44)==0
        if args.native_frame_child:assert nonempty_frame_branches==['0x11259c'],nonempty_frame_branches
    if args.native_activation_queues:assert activation_pump_returns==([0] if args.native_receiver_start else [7]),activation_pump_returns
    envelope=bytearray(424);struct.pack_into('<I',envelope,60,control);struct.pack_into('<I',envelope,72,3)
    u.mem_write(0x6001e000,bytes(envelope))
    invoke(0x104c20,(0x732d3c,0x6001e000,0,0))
    assert frame_receiver_calls==['0xef1a0','0xecd6c','0xef5dc'],frame_receiver_calls
    if args.native_frame_child:
        bridge_hook=u.hook_add(UC_HOOK_CODE,child_bridge)
        invoke(0x112cc0,(0x75cf44,child_control,1,0));u.hook_del(bridge_hook)
        assert word(0x75cf44+0x44)==0 and word(0x75cf44+4)==0
        report['limits'].append('Frame-child mode supplies a topology of two constructed controls; original insertion/removal and nonempty handler branch execute, attach notification/invalidation bridges virtual. No actual Home widget or painting claim.')
        report['cases'][-1]['native_frame_child']={'insert':'0x112a8c','remove':'0x112cc0','count_roundtrip':[0,1,0],'nonempty_handler_branches':nonempty_frame_branches,'virtual_attach_bridges':frame_child_bridges,'topology_supplied':True}
    report['cases'][-1]['native_frame_receiver']={'receiver':'0x104c20','control':hex(control),'callback_from_native_constructor':hex(word(control+0x4a0)),'calls':frame_receiver_calls.copy(),'envelope_supplied':True,'activation_prefix':{'entry':'0xe8de8','stop_before':None if args.native_frame_activation else '0xe8e58','outer_function_returned':args.native_frame_activation,'virtual_services':[] if args.native_activation_queues else activation_services,'service_entries':activation_services,'pump_returns':activation_pump_returns,'callback_entries':activation_callbacks,'supplied_backing_capacity':2,'active_count_after':2,'pending_count_after':0}}
    report['limits'].append('Receiver dispatches to actual frame control created by112878/edea8; no host callback-pointer write. Original e8de8 activation prefix changes pending2/active0 to pending0/active2; prefix mode stops before render/queue flush; full activation mode executes outer suffix with explicit virtual refresh services; frame handlers see an empty list unless native-frame-child supplies a constructed child. Envelope supplied, default delegate empty, graphics/auxiliary constructor services virtual; no painting or OS event loop.')
if args.native_upstream_completion:
    assert upstream_completion_path==['0x104de8','0x104e94','0xe9690'],upstream_completion_path
    assert word(0x733208+0x1b00c)==0 and word(0x733208+0x1b010)==0
if args.native_upstream_reject:
    report['cases'][-1]['native_upstream_reject']={'operation':'slot0 memory-image request flag0x800, empty image descriptor','validation_returns':upstream_validation_returns,'queue_receiver_states':upstream_states,'completion_callbacks':upstream_deliveries,'completion_body_intercepted':not args.native_upstream_completion,'completion_path':upstream_completion_path,'internal_queue_counts':[word(0x733208+0x1b00c),word(0x733208+0x1b010)],'forced_completion_or_dequeue':False}
    report['limits'].append('Original image validator rejects empty descriptor with10; native pump emits error completion and returns queue0/receiver1. Completion104c20 body is intercepted unless native-upstream-completion is enabled. This is an error path, not successful image loading or rendering.')
if args.native_processor_registration:
    report['cases'][-1]['native_processor_registration']={'entry':'0x1d374','receiver_slot':0,'registered_words':['0x0','0x1cdec','0x1cf58','0x1d27c','0x1d35c'],'host_callback_pointer_writes':False}
    report['limits'].append('Original1d374 builds and registers slot0 processing descriptor through10597c/e8a8c/104960/105474; real stock operation payload not supplied yet, so no processing completion claim.')
if args.native_receiver_start and not args.native_upstream_reject:
    report['cases'][-1]['native_receiver_start']={'entry':'0x10490c','state_after':1,'input_queue_count':0,'pump_return':0,'actual_message_consumed':False,'upstream_receiver_binding':'0x732d3c','binding_written_by_original':'0xe8994','native_upstream_init':args.native_upstream_init}
    report['limits'].append('Original10490c/106110/105430 starts receiver state0->1. Native pump returns0 with empty upstream queue74e22c; no message delivery or thread scheduling proved.')
if args.native_activation_queues and not args.native_receiver_start:
    report['limits'].append('Original104a14/106830 and107514/107d04 process empty queue counters;104f64/105498 returns7 for receiver state0, so no running receiver or actual message consumption proved.')
if args.native_graphics_context:
    assert word(0x761394+0xc158)==0x76d4f0 and frame_child_bridges==[]
    report['cases'][-1]['native_graphics_context']={'initializer':'0x119258','context':'0x76d4f0','embedded_in_owner':True,'native_attach_dispatch':True,'qsort_counts':graphics_qsort_counts.copy(),'qsort_service_virtual_for_at_most_one_item':True}
    report['limits'].append('Original119258 initializes embedded graphics context and coordinate rectangles; attach e9690 executes. No driver mapping/hardware initialization; qsort virtual only for <=1 item, full display prelude and refresh services remain virtual.')
if args.home_state_transition:
    assert list(u.mem_read(0x60012000,2))==[1,4]
    before_home_events=len(events);home_running=True
    invoke(0x17c608,(0x60012000,0x20104,0,0));home_running=False
    assert list(u.mem_read(0x60012000,2))==[1,11]
    assert word(0x6001b010)==0
    home_events=[e.copy() for e in events[before_home_events:]]
    assert home_events==[[0x4a0116,0,0x20104,0],[0x570002,0,0,0],[0x20307,0,0,0]],home_events
    report['cases'][-1]['native_home_state_transition']={'request_fixture':'0x20104','before':[1,4],'after':[1,11],'slot_inactive_after':True,'events':home_events,'virtual_services':home_services}
    report['limits'].append('Home20104 supplied after activation; native55adc/a93c8/5ce30/5811c transition4 to11 and stop slot. Page preparationa9160,cleanup/input-mode services and entry helper virtual; no actual Home widgets or rendering. Queued Home event not consumed.')
if args.native_home_preparation:
    assert home_page_requests==[[33,0]],home_page_requests
    assert word(0x69c7cc+8)==1
    report['cases'][-1]['native_home_preparation']={'entry':'0xa9160','page_requests':home_page_requests,'page_construction_still_virtual':True}
    report['limits'].append('Nativea9160 preparation chooses page33 flags0 under virtual query results0; request14e20 and page-service4dd20 virtual. Real Home construction/input/rendering not proved.')
if args.release_frames:
    invoke(0x119a0,(0x613f00,0,0,0))
    assert word(0x613f00+0x5eb8)==0 and word(0x613f00+0x5ebc)==0
    assert word(0x75cf44+0x138)==0 and word(0x6dfa18+0x788)==0
    if args.native_frame_receiver:assert word(0x6dfa18+0x37c)==0
    assert word(0x7a0660+0x30294)==0 and word(0x7a0660+0x30298)==0
    assert sorted(pixel_unmaps)==sorted(pixel_mappings) and len(pixel_unmaps)==4,pixel_unmaps
    invoke(0x119a0,(0x613f00,0,0,0));assert len(pixel_unmaps)==4
    report['cases'][-1]['native_frame_release']={'entry':'0x119a0','frame_count_after':0,'gui_pool_count_after':0,'resource_count_after':0,'pixel_unmaps':4,'repeat_release_adds_no_unmaps':True}
    report['limits'].append('119a0 explicitly invoked after activation test; native frame/control destructors and image/pool releases execute, OS munmap virtual. Actual event triggering departure not integrated; no hardware qualification.')
if args.complete_registry_initialization:
    report['cases'][-1]['complete_registry_initialization']={'entry':'0x14d0c','module_count':16,'page_selection_bound':45,'other_config_count':81,'same_address_space_as_recovery':True}
    report['limits'].append('Complete14d0c including both config registrations executes before recovery in same address space; no state copied from independent checks. Home page construction14e20 still virtual if Home preparation enabled.')
if args.native_page_request:
    assert page_manager_requests==[[0xe601e0,33,0]]
    report['cases'][-1]['native_page_request']={'wrappers':['0x14e20','0xb6770','0xdef44'],'manager_requests':page_manager_requests,'manager_body_still_virtual':not args.native_page_manager}
    report['limits'].append('Native14e20/b6770/getter forward actual page33/flags0 into registrydf3b4; manager body intercepted returns0. Does not select or construct page33 or execute page-change callbacks.')
if args.native_page_manager:
    report['limits']=[x for x in report['limits'] if not x.startswith('Native14e20/b6770/getter')]
    assert word(0xe601e0+0x12f4)==33
    dispatches=[r for r in page_manager_services if r['pc']=='0xe0e00']
    assert len(dispatches)==81,len(dispatches)
    report['cases'][-1]['native_page_manager']={'entry':'0xdf3b4','selected_page_after':33,'interface_dispatches':len(dispatches),'inner_service_calls':page_manager_services}
    report['limits'].append('Nativedf3b4 accepts page33 and updates current page; template setup/transitione0170/e01a4/e02ec and81 interface dispatchese0e00 virtual. This is manager orchestration, not actual Home construction or rendering.')
if args.native_home_template:
    assert home_template_calls==[0x691b50]
    assert [word(0x691b50+off) for off in (8,12,16,20)]==[0,0,0,0xffffffff]
    report['cases'][-1]['native_home_template']={'record':'0xe60e98','configuration':'0x4e12dc','getter':'0xa93bc','initializer':'0xa953c','object':'0x691b50','native_initializer_calls':1}
    report['limits'].append('Nativee0170/e010c and real page33 configuration select/get/init a953c on691b50; aa994/aaa38/aab70 auxiliary services still virtual. Interface processing/template transition remain virtual; no Home widgets/rendering.')
if args.native_template_transition:
    assert len(template_packets)==2,template_packets
    assert word(0x6dfa18+4)&4
    report['cases'][-1]['native_template_transition']={'entry':'0xe02ec','config_flags':'0x22','packets':template_packets,'gui_flag4_set':True,'packet_dispatch_still_virtual':True}
    report['limits'].append('Nativee02ec and packet formatters execute for page33 flags22/current previous-1; emit2 GUI packets, sete87f4 GUI flag4. e9690 dispatch returns0 virtually, so no physical input/display effect or actual page construction.')
if args.native_template_dispatch:
    assert [p['words0_3'][1] for p in template_packets]==[3,2]
    assert template_dispatch_effects==[{'pc':'0x1160c8','argument':'0x806'},{'pc':'0xeb87c','target':'0x6dfa28','value':'0xffffc000'}],template_dispatch_effects
    assert int.from_bytes(u.mem_read(0x6dfa28+52,2),'little')==0xc000 and int.from_bytes(u.mem_read(0x6dfa28+88,2),'little')==0xc000
    report['cases'][-1]['native_template_dispatch']={'entry':'0xe9690','effects':template_dispatch_effects,'record_values_after':['0xc000','0xc000'],'graphics_service_still_virtual':True,'native_view_pool':args.native_view_pool,'native_view_startup_prefix':args.native_view_startup_prefix,'native_manager_init':args.native_manager_init,'native_receiver_init':args.native_receiver_init,'manager_init_virtual_services':manager_init_services if args.native_view_startup_prefix else [],'active_view_state':{'manually_supplied':not args.native_view_pool,'index':0,'record':'0x6dfa28','valid_flag_offset':108,'valid_flag':1,'original_manager_startup_executed':False,'outer_initializer_returned':args.native_manager_init,'view_pool_functions_executed':args.native_view_pool,'startup_prefix':{'entry':'0xe8800','stop_before':None if args.native_manager_init else '0xe8900','virtual_service':'0x115e28','allocated_views':2} if args.native_view_startup_prefix else None}}
    report['limits'].append('Nativee9690 consumes original message types3/2; type3 reaches1160c8(806) service virtual, type2 nativeeb87c stores16bit c000 into current record. Current view setup uses explicit native pool calls when native_view_pool is enabled, otherwise supplied index/valid-bit fixtures; Full original GUI-manager startup is unqualified: native_manager_init executes the outer initializer to return, with listed module/receiver services virtual; other modes stop earlier. No framebuffer rendering or actual graphics service effects qualified.')
(ROOT / ('sources/native-resume-upstream-completion.json' if args.native_upstream_completion else 'sources/native-resume-upstream-reject.json' if args.native_upstream_reject else 'sources/native-resume-upstream-message.json' if args.native_upstream_message else 'sources/native-resume-processor-registration.json' if args.native_processor_registration else 'sources/native-resume-upstream-init.json' if args.native_upstream_init else 'sources/native-resume-receiver-start.json' if args.native_receiver_start else 'sources/native-resume-activation-queues.json' if args.native_activation_queues else 'sources/native-resume-graphics-context.json' if args.native_graphics_context else 'sources/native-resume-attach-dispatch.json' if args.native_attach_dispatch else 'sources/native-resume-frame-child.json' if args.native_frame_child else 'sources/native-resume-frame-activation.json' if args.native_frame_activation else 'sources/native-resume-frame-receiver.json' if args.native_frame_receiver else 'sources/native-resume-receiver-init.json' if args.native_receiver_init else 'sources/native-resume-manager-init.json' if args.native_manager_init else 'sources/native-resume-view-startup-prefix.json' if args.native_view_startup_prefix else 'sources/native-resume-view-pool.json' if args.native_view_pool else 'sources/native-resume-template-dispatch.json' if args.native_template_dispatch else 'sources/native-resume-template-transition.json' if args.native_template_transition else 'sources/native-resume-home-template.json' if args.native_home_template else 'sources/native-resume-page-manager.json' if args.native_page_manager else 'sources/native-resume-page-request.json' if args.native_page_request else 'sources/native-resume-complete-registry.json' if args.complete_registry_initialization else 'sources/native-resume-home-preparation.json' if args.native_home_preparation else 'sources/native-resume-home-state.json' if args.home_state_transition else 'sources/native-resume-frame-release.json' if args.release_frames else 'sources/native-resume-resource-register.json' if args.native_resource_register else 'sources/native-resume-frame-pixels.json' if args.native_frame_pixels else 'sources/native-resume-frame-base.json' if args.native_frame_base else 'sources/native-resume-frame-initializer.json' if args.native_frame_initializer else 'sources/native-resume-frame-child-failure.json' if args.frame_child_failure else 'sources/native-resume-frame-factory.json' if args.native_frame_factory else 'sources/native-resume-page-coordinator.json' if args.native_page_coordinator else 'sources/native-resume-slot-integrated.json' if args.native_resume_slot else 'sources/native-ordered-battery-resume.json' if args.consume_battery_event else 'sources/native-ordered-callback-resume.json' if args.ordered_activation else ('sources/native-callback-resume-apf-rejected.json' if args.reject_activation else 'sources/native-callback-resume.json') if args.activation_callback else ('sources/native-root-resume-apf-rejected.json' if args.reject_activation else 'sources/native-root-resume.json') if args.root_reactivation else ('sources/native-command7-apf-rejected.json' if args.reject_activation else 'sources/native-command7-apf-accepted.json') if args.ack_activation else ('sources/native-command7-worker-error.json' if args.worker_error else 'sources/native-command7-worker-native.json') if args.native_resume_worker else 'sources/native-command7-gui-entry.json' if args.finish_gui_transition else 'sources/native-command7-gui-transition.json' if args.dispatch_gui_resume else 'sources/native-command7-gui-complete.json' if args.complete_gui_resume else 'sources/native-command7-gui-consumer.json' if args.consume_gui_resume else 'sources/native-command7-gui-resume.json' if args.native_gui_resume else 'sources/native-command7-coordinator.json')).write_text(json.dumps(report, indent=2) + '\n')
print('Native GUI resume restores input and registers pending0x207' if args.native_gui_resume else '13 command7 cases verify coordination; native PCS fixture clears 50 cache slots before channel-list helper')













