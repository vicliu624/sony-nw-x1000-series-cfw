"""Replay original proxy monitor, stop dispatch and SIGCHLD/quit ordering.

An already-active child is a fixture. IPC, signals, waitpid, pipes and threads
are virtual; no real process, APF manager or storage is touched.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
import argparse
from itertools import product
from elftools.elf.elffile import ELFFile
from evidence_checks import verify_report
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--frontend-exit-report')
parser.add_argument('--proxy-argument-report',help='Validated actual-ELF argv entry report for --actual-workflow-report.')
parser.add_argument('--actual-workflow-report',help='Current actual-ELF workflow aggregate; requires explicit --report, preserves legacy evidence.')
parser.add_argument('--exec-failure-report')
parser.add_argument('--registration-report',default='sources/native-manager-proxy-exec-request.json')
parser.add_argument('--second-entry',action='store_true',help='Use second-entry native registration/exec evidence and child PID433 fixture.')
parser.add_argument('--report',help='Distinct report under sources/, leaving standard evidence unchanged.')
options=parser.parse_args()
registration_path=(ROOT/options.registration_report).resolve();assert registration_path.is_relative_to(ROOT/'sources')
registration_bytes=registration_path.read_bytes()
registration=json.loads(registration_bytes)
if options.second_entry:
    verify_report(ROOT,options.registration_report)
    assert registration['second_proxy_registration']['ports']==[644,645]
    assert registration['second_proxy_activation']['proxy_state']==2
    native_ports={'reply_address':644,'reply_handle':500,'event_address':645,'event_handle':501}
else:
    native_ports=registration['cases'][0]['proxy_registration']['native_ports']
    assert native_ports=={'reply_address':642,'reply_handle':500,'event_address':643,'event_handle':501}
child_pid=433 if options.second_entry else 321
frontend_input=None
statuses=(0,127<<8,15)
if options.frontend_exit_report:
    path=(ROOT/options.frontend_exit_report).resolve();assert path.is_relative_to(ROOT/'sources')
    content=path.read_bytes();frontend=json.loads(content)
    binary=(ROOT/frontend.get('artifact','work/x1000-homebrew-frontend')).resolve();assert binary.is_relative_to(ROOT/'work')
    actual=binary.read_bytes()
    assert frontend['program_sha256']==hashlib.sha256(actual).hexdigest()
    captured=[row for row in frontend['cases'] if 'captured_argv' in row]
    expected_count=0
    for item in frontend['proxy_capture_inputs']:
        body=(ROOT/item['path']).read_bytes();assert hashlib.sha256(body).hexdigest()==item['sha256']
        expected_count+=1 if options.second_entry and 'second_proxy_activation' in json.loads(body) else len(json.loads(body)['cases'])
    assert len(captured)==expected_count and expected_count>0
    assert {'path':options.registration_report,'sha256':hashlib.sha256(registration_bytes).hexdigest()} in frontend['proxy_capture_inputs']
    assert all(row['all_handles_closed'] and row['maps']==row['unmaps'] for row in captured)
    assert all(isinstance(row['exit'],int) and 0<=row['exit']<=255 for row in captured)
    statuses=tuple(sorted({row['exit']<<8 for row in captured}))
    frontend_input={'path':options.frontend_exit_report,'sha256':hashlib.sha256(content).hexdigest(),
                    'frontend_sha256':frontend['program_sha256'],'captured_exit_codes':[row['exit'] for row in captured]}
if options.actual_workflow_report:
    assert not options.frontend_exit_report and options.report and not options.second_entry
    workflow=verify_report(ROOT,options.actual_workflow_report);assert workflow['passed'] is True
    composition=(ROOT/workflow['composition']).resolve();assert composition.is_relative_to(ROOT/'work')
    artifact=composition/'external/HOMEBREW/launcher/app';artifact_relative=str(artifact.relative_to(ROOT));artifact_sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
    def scenario_report(script):
        rows=[row for row in workflow['scenarios'] if row['script']==script];assert len(rows)==1
        relative=rows[0]['report'];path=(ROOT/relative).resolve();assert path.is_relative_to(ROOT/'sources')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==rows[0]['sha256']
        return relative
    actual_cases=[]
    for script,field in (('test_libc_production_ui.py','actual_ELF_UI_return_exit'),('test_production_store_stop.py','parent_exit')):
        report_relative=scenario_report(script)
        observation=verify_report(ROOT,report_relative);assert observation['passed'] is True
        assert observation['source_hashes'][artifact_relative]==artifact_sha
        assert (ROOT/observation['composition']).resolve()==composition
        code=observation[field];assert isinstance(code,int) and 0<=code<=255
        if field=='parent_exit':assert observation['no_parent_device_reacquire_after_stop'] and observation['parent_and_child_device_cleanup_observed']
        actual_cases.append({'report':report_relative,'sha256':hashlib.sha256((ROOT/report_relative).read_bytes()).hexdigest(),'exit':code})
    verify_report(ROOT,options.registration_report)
    argument_report=options.proxy_argument_report or scenario_report('test_libc_proxy_entry.py');argument_evidence=verify_report(ROOT,argument_report)
    assert argument_evidence['passed'] and argument_evidence['source_hashes'][options.registration_report]==hashlib.sha256(registration_bytes).hexdigest()
    assert argument_evidence['actual_candidate_sha256']==artifact_sha,'Parameter capture belongs to a different frontend ELF'
    assert (ROOT/argument_evidence['composition']).resolve()==composition
    statuses=tuple(sorted({row['exit']<<8 for row in actual_cases}))
    frontend_input={'mode':'actual-workflow-exits','composition':str(composition.relative_to(ROOT)),'path':options.actual_workflow_report,'sha256':hashlib.sha256((ROOT/options.actual_workflow_report).read_bytes()).hexdigest(),'frontend_sha256':artifact_sha,'artifact':artifact_relative,'observations':actual_cases,'proxy_argument_report':argument_report,'proxy_argument_report_sha256':hashlib.sha256((ROOT/argument_report).read_bytes()).hexdigest()}
raw = (ROOT / 'work/targets-jp/appproxy').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
exec_failure_input=None
if options.exec_failure_report:
    path=(ROOT/options.exec_failure_report).resolve();assert path.is_relative_to(ROOT/'sources')
    content=path.read_bytes();failure=json.loads(content)
    assert failure['appproxy_sha256']==digest and len(failure['cases'])==6
    statuses=tuple(sorted(set(statuses)|{row['child_wait_status'] for row in failure['cases']}))
    exec_failure_input={'path':options.exec_failure_report,'sha256':hashlib.sha256(content).hexdigest()}
elf = ELFFile(io.BytesIO(raw))
syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for event, child_status, late_stop in product((4, 6, None), statuses, (False, True)):
    if event is None and late_stop:continue
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x20000)
    for s in elf.iter_segments():
        if s['p_type'] == 'PT_LOAD':
            u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x30000)
    ctx = 0x1ca5c
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    put(ctx + 4, 2)
    put(ctx + 0x24, 1)
    put(ctx + 0x28, 77)
    put(ctx + 0x10, 500)
    put(ctx + 0x0c,native_ports['reply_address'])
    put(ctx + 0x18,native_ports['event_address'])
    put(ctx + 0x1c, 501)
    put(ctx + 0x20, 1234)
    put(0x1c834, child_pid)
    put(0x60022000, 0x60023000)
    put(0x60022004, 0x60023020)
    put(0x60022008, 0)
    u.mem_write(0x60023000, b'appproxy\0')
    u.mem_write(0x60023020, b'/contents/HOMEBREW/launcher/app\0')
    trace, pipe = [], bytearray()
    quit_wire_requests=[]
    monitor_signal_handlers = []
    received, exited, reaped = 0, False, False
    late_delivery_attempted=False
    waiting = []
    def hook(uc, pc, size, data):
        global received, reaped
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        if pc in (0x9970, 0xcdec, 0xea80, 0xeae8, 0xe5e0, 0x9a0c, 0xcfbc, 0xd1ac, 0xdc1c, 0xf148):
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == syms['pipe']:
            uc.mem_write(args[0], struct.pack('<II', 101, 102))
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc in (syms['fcntl'], syms['signal']):
            if pc == syms['signal']:
                monitor_signal_handlers.append(args[:2])
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == syms['read']:
            assert args[0] == 101 and args[2] == 8
            if len(pipe) < 8:
                waiting.append('child-pipe')
                trace.append('monitor-waits-child')
                uc.emu_stop()
                return
            assert reaped
            uc.mem_write(args[1], bytes(pipe[:8]))
            del pipe[:8]
            trace.append('monitor-received-exit')
            uc.reg_write(UC_ARM_REG_R0, 8)
        elif pc == 0xd36c:
            if received:
                waiting.append('next-APF-event')
                trace.append('stop-callback-returned-no-ack')
                uc.emu_stop()
                return
            packet = struct.pack('<IIII', 16, 0, event, 0)
            uc.mem_write(args[1], packet)
            uc.mem_write(uc.reg_read(UC_ARM_REG_R3), struct.pack('<I', len(packet)))
            received += 1
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == syms['kill']:
            assert args[:2] == [child_pid, 15]
            trace.append('SIGTERM-requested')
            uc.reg_write(UC_ARM_REG_R0, 0xffffffff if reaped else 0)
        elif pc == syms['waitpid']:
            if exited and not reaped:
                put(args[1], child_status)
                reaped = True
                trace.append('child-reaped')
                uc.reg_write(UC_ARM_REG_R0, child_pid)
            else:
                uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == syms['writev']:
            assert reaped and args[0] == 102 and args[2] == 2
            total = 0
            for i in range(2):
                pointer, count = struct.unpack('<II', uc.mem_read(args[1] + i * 8, 8))
                pipe.extend(uc.mem_read(pointer, count))
                total += count
            assert bytes(pipe) == struct.pack('<II', child_pid, child_status)
            trace.append('exit-record-written')
            uc.reg_write(UC_ARM_REG_R0, total)
        elif pc == syms['close']:
            trace.append('close-' + str(args[0]))
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == 0xd2c0:
            assert reaped and 'monitor-received-exit' in trace
            assert args[:2]==[native_ports['reply_handle'],native_ports['event_address']]
            assert struct.unpack('<II', uc.mem_read(args[2], 8)) == (8, 3)
            if late_stop and not late_delivery_attempted:
                trace.append('termination-message-before-late-event')
                uc.emu_stop();return
            trace.append('proxy-termination-message')
            quit_wire_requests.append({'source_handle':args[0],'destination':args[1],'payload':list(struct.unpack('<II',uc.mem_read(args[2],8))),'payload_bytes':8})
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc in (0xfbf8, 0xfc38):
            raise AssertionError('Unexpected native panic')
        else:
            return
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def call(address, stack, arg0=0, arg1=0):
        for reg, value in [(UC_ARM_REG_R0, arg0), (UC_ARM_REG_R1, arg1),
                           (UC_ARM_REG_SP, stack), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(address, 0x50000000, count=100000)
    call(0x96a0, 0x60008000, 2, 0x60022000)
    assert monitor_signal_handlers == [[17, 0x94e8]]
    assert waiting == ['child-pipe']
    monitor = u.context_save()
    if event is not None and not late_stop:
        call(0x9b40, 0x60010000, ctx)
        assert waiting[-1] == 'next-APF-event' and 'SIGTERM-requested' in trace
    else:
        assert 'SIGTERM-requested' not in trace
    assert not pipe and 'proxy-termination-message' not in trace
    call(0x94e8, 0x60018000)
    assert not pipe and not reaped
    exited = True
    call(0x94e8, 0x60018000)
    assert reaped and len(pipe) == 8
    u.context_restore(monitor)
    u.emu_start(u.reg_read(UC_ARM_REG_PC), 0x50000000, count=100000)
    if late_stop:
        assert u.reg_read(UC_ARM_REG_PC)==0xd2c0 and 'termination-message-before-late-event' in trace
        pending_quit=u.context_save()
        call(0x9b40,0x60010000,ctx)
        assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and received==0
        trace.append('late-stop-not-read-receiver-already-stopped')
        late_delivery_attempted=True
        u.context_restore(pending_quit)
        u.emu_start(u.reg_read(UC_ARM_REG_PC),0x50000000,count=100000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    assert u.reg_read(UC_ARM_REG_R0) == 0, 'Proxy propagated child failure status'
    assert trace.index('child-reaped') < trace.index('monitor-received-exit') < trace.index('proxy-termination-message')
    rows.append({'stop_event': event, 'child_wait_status': child_status,
                 'captured_quit_wire_requests':quit_wire_requests,
                 'late_stop_offered_after_reap_and_quit_request':late_stop,
                 'late_stop_consumed':bool(received) if late_stop else None,
                 'monitor_signal_handlers': monitor_signal_handlers,
                 'monitor_return': u.reg_read(UC_ARM_REG_R0), 'trace': trace,
                 'quit_after_reaped_child': True,
                 'stop_callback_did_not_ack_early': True if event is not None and not late_stop else None})
result = {'scope': 'Original proxy monitor/dispatch/SIGCHLD/finalizer instructions; active-child fixture, registration/IPC/syscalls mocked',
          'appproxy_sha256': digest, 'cases': rows,
          'limits': ['No real child, signal, pipe, thread or APF manager ran.',
                     'Does not prove manager timeouts, USB unmount/export order or pathological child cleanup.',
                     'Server reply/wakeup and final thread join are mocked.']}
result['frontend_exit_input']=frontend_input
result['exec_failure_input']=exec_failure_input
result['quit_wire_to_manager_op3_verified']=False
result['self_event_shutdown_not_manager_op3']=True
result['native_registration_ports']=native_ports
result['child_pid_fixture']=child_pid
result['registration_report_sha256']=hashlib.sha256(registration_bytes).hexdigest()
result['limits'].append(f'Captured8-byte[8,3] message goes to native own event address{native_ports["event_address"]}, not manager55. It is receiver shutdown/wakeup, not the24-byte managerf89c request. OS transport/thread join virtual.')
output=ROOT/('sources/native-frontend-proxy-exit.json' if frontend_input else 'sources/native-proxy-stop-order.json')
if options.report:
    output=(ROOT/options.report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
    result['all_bounded_checks_passed']=True
    result['source_hashes']={options.registration_report:hashlib.sha256(registration_bytes).hexdigest(),'tools/check_proxy_stop_order.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if frontend_input:
        result['source_hashes'][frontend_input['path']]=frontend_input['sha256']
        if options.actual_workflow_report:
            result['source_hashes'][frontend_input['artifact']]=frontend_input['frontend_sha256']
            for observation in frontend_input['observations']:result['source_hashes'][observation['report']]=observation['sha256']
            result['source_hashes'][frontend_input['proxy_argument_report']]=frontend_input['proxy_argument_report_sha256']
            result['limits'].append('Exit codes originate from actual QEMU launcher workflows; proxy wait/IPC/registration remain virtual, joined at captured status only.')
output.write_text(json.dumps(result, indent=2) + '\n')
print(str(len(rows))+' proxy cases: quit follows child reap; frontend input='+str(bool(frontend_input)))
