"""Capture original Responder op10 request; virtual IPC/mutex only, no device."""
from pathlib import Path
import argparse, hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--operation',type=int,choices=(10,11),default=10,help='Original USB allow(10) or restore-mount(11) client.')
parser.add_argument('--restore-followup-caller',action='store_true',help='Execute originalff5c: op11 wrapper then original11f20/op19 argument2; semantics not labelled.')
parser.add_argument('--restore-followup-dispatch',action='store_true',help='Use original state initializer/setter and event410008 dispatch to selectff5c.')
parser.add_argument('--wrapper', action='store_true', help='Include original12b94 caller and its logging; context getter virtual.')
parser.add_argument('--outer-caller', action='store_true', help='Include originalfa3c caller; do not interpret its0x203 return as USB success.')
parser.add_argument('--state-dispatch', action='store_true', help='Construct original state machine and dispatch event410002 through its real tables.')
parser.add_argument('--activate-first', action='store_true', help='For active cases execute original182a24 from state1 using virtual query/IPC, then issue op10.')
parser.add_argument('--consume-manager-reply', action='store_true', help='Use captured stock-manager success reply in the active-success case.')
parser.add_argument('--usb-cycle',action='store_true',help='One positive same-object activation/op10/event410008/op11/op19 sequence; virtual IPC.')
options = parser.parse_args()
if options.usb_cycle:
    if options.restore_followup_caller or options.restore_followup_dispatch or options.operation!=10 or options.consume_manager_reply:
        parser.error('--usb-cycle requires the op10 path without separate restore or manager-reply modes')
    options.activate_first=options.state_dispatch=True
if options.restore_followup_dispatch:options.restore_followup_caller=True
if options.restore_followup_caller:
    options.operation=11;options.wrapper=True
if options.operation==11 and (options.outer_caller or options.state_dispatch or options.consume_manager_reply):
    parser.error('Operation11 currently supports direct/wrapper/activate-first modes only.')
manager_input = None
if options.consume_manager_reply:
    options.activate_first = options.state_dispatch = True
    manager_path = 'sources/native-contents-service-op10.json'
    manager_raw = (ROOT / manager_path).read_bytes()
    manager = json.loads(manager_raw)
    assert manager['sysmgrd_sha256'] == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
    assert manager['all_passed']
    success = next(row for row in manager['cases'] if row['case'] == 'success')
    assert success['service_replies'] == [[16, 56, 10, 0]]
    manager_input = {'path': manager_path, 'sha256': hashlib.sha256(manager_raw).hexdigest(),
                     'reply': success['service_replies'][0]}
if options.state_dispatch:
    options.outer_caller = True
if options.outer_caller:
    options.wrapper = True
entry = 0x9f2d4 if options.restore_followup_dispatch else 0xff5c if options.restore_followup_caller else (0x12c10 if options.wrapper else 0x182008) if options.operation==11 else 0x9f2d4 if options.state_dispatch else 0xfa3c if options.outer_caller else 0x12b94 if options.wrapper else 0x1820d8
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
    binary = tar.extractfile('./usr/local/bin/Responder').read()
rows = []
for name, state, reply, send_error, receive_error in [
        ('inactive-state0', 0, 0, 0, 0), ('inactive-state1', 1, 0, 0, 0),
        ('active-success', 2, 0, 0, 0), ('manager-error', 2, 0x1d08, 0, 0),
        ('send-error', 2, 0, 0x301, 0), ('receive-error', 2, 0, 0, 0x302)]:
    if options.usb_cycle and name!='active-success':continue
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0xc00000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x2000000, 0x10000)
    ctx, end, machine = 0x6b2ccc, 0x2001000, 0x2002000
    write = lambda address, value: u.mem_write(address, struct.pack('<I', value))
    for offset, value in ((0, 2), (4, 1 if options.activate_first and state == 2 else state), (12, 66), (16, 77), (20, 55), (40, 88)):
        write(ctx + offset, value)
    captures, receives, logs, actions = [], [], [], []
    activation_requests = []
    followup_requests=[];followup_replies=[];pending_opcode=[options.operation];request_order=[]
    cycle_requests=[];cycle_replies=[]
    phase = 'activation' if options.activate_first and state == 2 else 'usb'
    def hook(uc, pc, size, unused):
        if pc == end:
            uc.emu_stop()
            return
        if (options.state_dispatch and pc == 0xfa3c) or ((options.restore_followup_dispatch or options.usb_cycle) and pc==0xff5c):
            actions.append(hex(pc))
            return
        extras = (0x11d1c, 0x1f3bf0, 0x1f3b14) if options.wrapper else ()
        if options.activate_first:
            extras += (0x18017c, 0x17fc14, 0x1f3b14)
        if options.state_dispatch or options.restore_followup_dispatch:
            extras += (0x9f0f8,)
        if pc not in (0x1f0068, 0x1f00d0, 0x183618, 0x1836c4) + extras:
            return
        result = 0
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x183618:
            assert args[0] == 77 and args[1] == 55
            if phase == 'activation':
                packet = list(struct.unpack('<6I', uc.mem_read(args[2], 24)))
                assert args[3] == 24 and packet == [24, 55, 2, 1, 66, 2]
                activation_requests.append(packet)
                uc.reg_write(UC_ARM_REG_R0, 0)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
                return
            if phase=='restore-cycle':
                packet=list(struct.unpack('<'+'I'*(args[3]//4),uc.mem_read(args[2],args[3])))
                assert packet==([20,57,2,11,66] if not cycle_requests else [24,58,2,19,66,2])
                cycle_requests.append(packet)
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            if options.restore_followup_caller and args[3]==24:
                packet=list(struct.unpack('<6I',uc.mem_read(args[2],24)))
                assert packet==[24,56,2,19,66,2]
                followup_requests.append(packet);pending_opcode[0]=19;request_order.append(19)
                uc.reg_write(UC_ARM_REG_R0,send_error)
                uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            assert args[3] == 20
            packet = list(struct.unpack('<5I', uc.mem_read(args[2], 20)))
            assert packet == [20, 56 if options.activate_first and state == 2 else 55, 2, options.operation, 66]
            captures.append({'port': args[0], 'destination': args[1], 'words': packet})
            request_order.append(options.operation)
            result = send_error
        elif pc == 0x1836c4:
            assert args[0] == 77 and args[2] == 16
            if phase=='restore-cycle':
                packet=cycle_requests[-1];response=[16,packet[1],packet[3],0]
                uc.mem_write(args[1],struct.pack('<4I',*response));write(args[3],16)
                cycle_replies.append(response)
                uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
            response = [16, 55, 1, 0] if phase == 'activation' else [16, 56 if options.activate_first and state == 2 else 55, options.operation, reply]
            if options.restore_followup_caller and pending_opcode[0]==19:
                response=[16,56,19,reply]
            if manager_input and phase == 'usb' and name == 'active-success':
                response = manager_input['reply']
            uc.mem_write(args[1], struct.pack('<4I', *response))
            write(args[3], 16)
            if phase != 'activation':
                (followup_replies if options.restore_followup_caller and pending_opcode[0]==19 else receives).append(response)
                result = receive_error
        elif pc == 0x18017c:
            write(args[1], 1)  # original current-mode query boundary
        elif pc in (0x1f3bf0, 0x1f3b14):
            logs.append({'function': hex(pc), 'arguments': args})
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, ctx)
    u.reg_write(UC_ARM_REG_SP, 0x200f000)
    u.reg_write(UC_ARM_REG_LR, end)
    if phase == 'activation':
        u.reg_write(UC_ARM_REG_R1, 0)
        u.emu_start(0x182a24, end, count=3000)
        assert u.reg_read(UC_ARM_REG_PC) == end and u.reg_read(UC_ARM_REG_R0) == 0
        assert struct.unpack('<I', u.mem_read(ctx + 4, 4))[0] == 2
        assert activation_requests == [[24, 55, 2, 1, 66, 2]]
        phase = 'usb'
        logs.clear()
        u.reg_write(UC_ARM_REG_R0, ctx)
        u.reg_write(UC_ARM_REG_LR, end)
    if options.state_dispatch or options.restore_followup_dispatch:
        u.reg_write(UC_ARM_REG_R0, machine)
        u.emu_start(0xf8b0, end, count=3000)
        assert u.reg_read(UC_ARM_REG_PC) == end and bytes(u.mem_read(machine, 2)) == b'\x01\x01'
        if options.restore_followup_dispatch:
            for reg,value in ((UC_ARM_REG_R0,machine),(UC_ARM_REG_R1,2),(UC_ARM_REG_R2,3),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
            u.emu_start(0x9f700,end,count=1000)
            assert u.reg_read(UC_ARM_REG_PC)==end and bytes(u.mem_read(machine,2))==b'\x02\x03'
        for reg, value in ((UC_ARM_REG_R0, machine), (UC_ARM_REG_R1, 0x410008 if options.restore_followup_dispatch else 0x410002),
                           (UC_ARM_REG_R2, 0), (UC_ARM_REG_R3, 0), (UC_ARM_REG_LR, end)):
            u.reg_write(reg, value)
    u.emu_start(entry, end, count=10000)
    assert u.reg_read(UC_ARM_REG_PC) == end
    expected = 0x1d09 if state < 2 else send_error or receive_error or reply
    actual = u.reg_read(UC_ARM_REG_R0)
    assert actual == (0 if options.restore_followup_dispatch else 6 if options.restore_followup_caller else 0 if options.state_dispatch else 0x203 if options.outer_caller else expected)
    if options.wrapper:
        assert len(logs) == (2 if expected else 1) * (2 if options.restore_followup_caller else 1) + (1 if options.state_dispatch or options.restore_followup_dispatch else 0),(name,logs,actions)
    if options.state_dispatch:
        assert actions == ['0xfa3c'] and bytes(u.mem_read(machine, 2)) == b'\x02\x03'
    if options.restore_followup_dispatch:
        assert actions==['0xff5c'] and bytes(u.mem_read(machine,2))==b'\x02\x06'
    assert len(captures) == (0 if state < 2 else 1)
    assert len(receives) == (1 if state >= 2 and not send_error else 0)
    if options.restore_followup_caller:
        assert len(followup_requests)==(1 if state>=2 else 0)
        assert len(followup_replies)==(1 if state>=2 and not send_error else 0)
        assert request_order==([11,19] if state>=2 else [])
    if options.usb_cycle:
        phase='restore-cycle'
        before_restore=list(u.mem_read(machine,2))
        for reg,value in ((UC_ARM_REG_R0,machine),(UC_ARM_REG_R1,0x410008),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
        u.emu_start(0x9f2d4,end,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
        assert before_restore==[2,3] and bytes(u.mem_read(machine,2))==b'\x02\x06'
        assert actions==['0xfa3c','0xff5c'] and len(cycle_requests)==len(cycle_replies)==2
        assert struct.unpack('<I',u.mem_read(ctx+20,4))[0]==59
    rows.append({'case': name, 'supplied_client_state': state, 'captured_requests': captures,
                 'supplied_replies': receives, 'client_expected_return': hex(expected),
                 'return': hex(actual), 'logs': logs, 'selected_actions': actions,
                 'state_bytes': list(u.mem_read(machine, 2)) if options.state_dispatch or options.restore_followup_dispatch else None,
                 'activation_requests': activation_requests,'followup_requests':followup_requests,
                 'followup_replies':followup_replies,'request_order':request_order,
                 'cycle_restore_requests':cycle_requests,'cycle_restore_replies':cycle_replies,
                 'cycle_states':[[1,1],before_restore,list(u.mem_read(machine,2))] if options.usb_cycle else None,
                 'cycle_all_requests':activation_requests+[r['words'] for r in captures]+cycle_requests if options.usb_cycle else None})
report = {'responder_sha256': hashlib.sha256(binary).hexdigest(), 'entry': hex(entry),
          'cases': rows, 'all_passed': True, 'physical_device_access': False,
          'limits': ['Client state, ports, sequence, mutex behavior and IPC results are fixtures.',
                     'Actual original client constructs request; IPC transport and requesting UI state transition are not executed.',
                     'Client state2 does not prove all other applications have exited.']}
if options.wrapper:
    report['limits'].append('Original12b94, getter17fe8c and optionalfa3c execute; logging remains virtual. Outer return0x203 is not a USB success result.')
if options.state_dispatch:
    report['limits'].append('Originalf8b0 initialization and9f2d4 dispatch execute; event410002 is delivered by fixture, not actual IPC.')
if options.activate_first:
    report['limits'].append('Active cases start in client state1; original182a24 writes state2 after supplied current-mode query and successful virtual manager reply.')
if manager_input:
    report['manager_reply_input'] = manager_input
filename = 'native-responder-manager-usb-reply.json' if manager_input else 'native-responder-activation-usb-request.json' if options.activate_first else 'native-responder-usb-state-dispatch.json' if options.state_dispatch else 'native-responder-usb-outer-caller.json' if options.outer_caller else 'native-responder-usb-wrapper.json' if options.wrapper else 'native-responder-usb-request.json'
report['operation']=options.operation
if options.operation==11:
    filename='native-responder-usb-restore-request.json'
if options.restore_followup_caller:
    filename='native-responder-restore-followup.json'
    report['limits'].append('Originalff5c/12c10/11f20/182008/1826cc execute; callback selection/event source and op19 server semantics are not validated.')
if options.restore_followup_dispatch:
    filename='native-responder-restore-followup-dispatch.json'
    report['limits'][-1]='Originalf8b0 initialization,9f700 setter and9f2d4 dispatch selectff5c. Initial group2/state3 and event410008 are explicit fixtures, not physical disconnection evidence; op19 server semantics are not validated.'
if options.usb_cycle:
    filename='native-responder-usb-cycle.json'
    report['limits'].append('Same original state object goes1/1 ->2/3 ->2/6 without setter/reset between events. Original client seq55 activation,56 op10,57 op11,58 op19. Events/replies remain fixtures; no physical USB or op19 server execution.')
(ROOT / 'sources' / filename).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
