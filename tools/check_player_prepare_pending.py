"""Replay original shutdown preparation; component callbacks are modeled."""
import hashlib
import io
import json
import struct
import time
import subprocess
import sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from app_registry import ROOT

raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
callbacks = [0x16b74, 0x143c0, 0xf32c, 0x3b498, 0x37f08,
             0x49d6c, 0x4492c, 0x499f8, 0x4f3dc]
sdk_native = '--sdk-native' in sys.argv
native_subsystem = '--native-subsystem' in sys.argv
native_basics = '--native-basics' in sys.argv or native_subsystem
assert not (sdk_native and native_basics)
helper = None
sources = []
symbols = {}
if sdk_native:
    build = ROOT / 'work/player-prepare-sdk' / str(time.time_ns())
    build.mkdir(parents=True)
    sources = ['runtime/platform/player/' + n + '.c' for n in ('client', 'service_drain', 'deferred_prepare')]
    sources += ['runtime/platform/services/session.c', 'tools/fixtures/player_deferred_native.c']
    binary = build / 'prepare.arm'
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                    '-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie',
                    '-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',
                    *sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
    helper = ELFFile(io.BytesIO(binary.read_bytes()))
    symbols = {s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
rows = []
profiles=('sdk-deferred','sdk-context-lost','sdk-owner-loop') if sdk_native else ('subsystem-immediate','subsystem-delayed','subsystem-unresponsive') if native_subsystem else ('native-environment1','native-environment2') if native_basics else ('synchronous', 'all-pending', 'already-pending', 'pcs-pending', 'deferred-action')
for mode in profiles:
    command=6 if native_basics else 3
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for segment in ELFFile(io.BytesIO(raw)).iter_segments():
        if segment['p_type'] != 'PT_LOAD':
            continue
        address = int(segment['p_vaddr'])
        base = address & ~4095
        cpu.mem_map(base, (address - base + int(segment['p_memsz']) + 4095) & ~4095)
        cpu.mem_write(address, segment.data())
    if helper:
        for segment in helper.iter_segments():
            if segment['p_type'] != 'PT_LOAD':continue
            address=int(segment['p_vaddr']);base=address&~4095
            cpu.mem_map(base,(address-base+int(segment['p_memsz'])+4095)&~4095)
            cpu.mem_write(address,segment.data())
    area = 0x71000000
    cpu.mem_map(area, 65536)
    root, tracker, output, done = area, area + 0x1000, area + 0x2000, area + 0xff00
    put = lambda address, value: cpu.mem_write(address, struct.pack('<I', value))
    get = lambda address: struct.unpack('<I', cpu.mem_read(address, 4))[0]
    put(root + 0x2c, tracker)
    put(output, 0x5a5a5a5a)
    auxiliary=area+0x5000
    if native_basics:put(auxiliary+0x48c,1)
    subsystem=0x7dcc84;waits=[];requests=[]
    if native_subsystem:
        put(subsystem+4,1);put(subsystem+0x14,0);put(subsystem+0x1f4,0x123)
        assert raw[0x444b94-0x8000:].startswith(b'Asv1SegCtrlPlayer.c\0')
    if mode == 'already-pending':
        put(tracker, 1)
        put(tracker + 4, 0x777)
    observed, finalizers, pcs = [], [], []
    held = []
    defer = [mode == 'deferred-action']
    subsystem_release=[]
    owner_loop=[False];owner_trace=[];owner_selects=[]
    stock_symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(raw)).get_section_by_name('.dynsym').iter_symbols()}
    gui=0x73000000;timing=gui+0x2c000;input_state=gui+0x2d000

    def hook(machine, pc, size, context):
        if pc == done:
            machine.emu_stop()
            return
        result = 0
        if native_subsystem:
            if pc==0x17de74:return
            if pc in (0x17f2b4,0x335788,0x3357e4,0x18c89c,0x33761c,0x181bbc,0x17e51c,0x33d8c0):
                if pc in (0x335788,0x3357e4):assert machine.reg_read(UC_ARM_REG_R0)==1
                elif pc==0x18c89c:
                    assert machine.reg_read(UC_ARM_REG_R0)==1 and get(subsystem+0x14)&0x100
                    requests.append(1)
                    if mode=='subsystem-immediate':put(subsystem+0x14,0)
                elif pc==0x33761c:
                    assert machine.reg_read(UC_ARM_REG_R0)==1
                    waits.append(1)
                    if mode=='subsystem-delayed' and len(waits)==2:put(subsystem+0x14,0)
                    if mode=='subsystem-unresponsive' and len(waits)==3:machine.emu_stop();return
                elif pc==0x181bbc:assert machine.reg_read(UC_ARM_REG_R0)==0x123
                machine.reg_write(UC_ARM_REG_R0,0);machine.reg_write(UC_ARM_REG_PC,machine.reg_read(UC_ARM_REG_LR));return
        if owner_loop[0]:
            if pc==0xff40 and get(symbols['test_forwards']):
                machine.emu_stop();return
            if pc==0xa6968:
                owner_trace.append('sdk-step')
                if owner_trace.count('sdk-step')==3:put(symbols['test_readers'],0)
                else:assert not observed and not finalizers
                machine.reg_write(UC_ARM_REG_PC,symbols['test_step']);return
            if pc==stock_symbols['memcpy']:
                dst,src,n=(machine.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
                assert n==128;machine.mem_write(dst,bytes(machine.mem_read(src,n)));result=dst
            elif pc==stock_symbols['select']:
                pointer=get(machine.reg_read(UC_ARM_REG_SP));owner_selects.append(struct.unpack('<2i',machine.mem_read(pointer,8)));owner_trace.append('select')
            elif pc==0xe18d8:result=input_state
            elif pc==0xe1b90:put(machine.reg_read(UC_ARM_REG_R1),0);put(machine.reg_read(UC_ARM_REG_R2),0)
            elif pc in (0x109ec,0x121c0,0x106c8,0x105f4,0x10620,0x10640,0x1063c,0x121ec,0x12128,0x51570,0x51828):pass
            else:result=None
            if result is not None:
                machine.reg_write(UC_ARM_REG_R0,result);machine.reg_write(UC_ARM_REG_PC,machine.reg_read(UC_ARM_REG_LR));return
            result=0
        if sdk_native and pc == 0x112fc and get(symbols['test_forwards']) == 0:
            machine.reg_write(UC_ARM_REG_PC,symbols['test_defer'])
            return
        if native_basics and pc in (0xe5f4,0xf6c0,0xbab4c,0x17de74):
            if pc==0xe5f4:result=area+0x3000
            elif pc==0xf6c0:result=2 if mode=='native-environment2' else 1
            elif pc==0xbab4c:result=auxiliary
            else:subsystem_release.append(machine.reg_read(UC_ARM_REG_R0))
        elif pc == 0xffa4:
            result = root
        elif pc == 0x112fc and defer[0]:
            # Candidate boundary only: do not preserve the caller's stack output
            # pointer or execute native preparation before a modeled drain.
            held.append((machine.reg_read(UC_ARM_REG_R0), machine.reg_read(UC_ARM_REG_R1)))
        elif pc in callbacks:
            assert machine.reg_read(UC_ARM_REG_R1) == command
            observed.append(pc)
            if native_basics and pc in (0x16b74,0xf32c):return
            token = callbacks.index(pc) + 0x900 if mode == 'all-pending' else 0
            put(machine.reg_read(UC_ARM_REG_R2), token)
        elif pc == 0x1fd30:
            pcs.append(pc)
            put(machine.reg_read(UC_ARM_REG_R2), 0xaaa if mode == 'pcs-pending' else 0)
        elif pc == 0x109a8:
            result = 1  # Original preflight effects are outside this replay.
        elif pc == 0x10ee4:
            finalizers.append(pc)  # Never release real native state in this test.
        elif pc not in (0xff5c, 0x33b83c, 0x33b918):
            return
        machine.reg_write(UC_ARM_REG_R0, result)
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    def helper_call(name):
        cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,done)
        cpu.emu_start(name if isinstance(name,int) else symbols[name],done+4,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==done
        value=cpu.reg_read(UC_ARM_REG_R0)
        return value if value<0x80000000 else value-0x100000000
    if sdk_native:
        assert helper_call('test_init')==0
        before=bytes(cpu.mem_read(root,0x100))
        cpu.reg_write(UC_ARM_REG_R0,area+0x3000)
        cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,done)
        cpu.emu_start(0x718c0,done+4,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==done and cpu.reg_read(UC_ARM_REG_R0)==0
        assert not observed and not finalizers and bytes(cpu.mem_read(root,0x100))==before
        assert helper_call('test_accepting')==0
        # A repeated original exit action must not replace/restart the drain.
        cpu.reg_write(UC_ARM_REG_R0,area+0x3000)
        cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,done)
        cpu.emu_start(0x718c0,done+4,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==done and not observed
        if mode=='sdk-context-lost':
            put(symbols['test_context_valid'],0)
            assert helper_call('test_step')==-2 and helper_call('test_step')==-2
            assert not observed and not finalizers and get(symbols['test_forwards'])==0
            rows.append(dict(case=mode,real_sdk_drain_and_native_prepare=True,forward_count=0,context_loss_refused=True))
            continue
        if mode=='sdk-owner-loop':
            cpu.mem_map(gui,0x40000)
            put(0x4f7820,timing);put(input_state+0x78,0xffffffff)
            put(root+0x10,gui);put(gui+0x56f8,0xffffffff)
            cpu.reg_write(UC_ARM_REG_R0,200000);assert helper_call(0xe44a4)==0
            owner_loop[0]=True
            cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,done)
            cpu.emu_start(0xff04,done+4,count=1000000)
            assert cpu.reg_read(UC_ARM_REG_PC)==0xff40
            assert owner_trace==['select','sdk-step']*3 and owner_selects==[(0,200000)]*3
            assert observed==callbacks and len(finalizers)==1 and get(symbols['test_forwards'])==1
            owner_loop[0]=False;assert helper_call('test_step')==0 and get(symbols['test_forwards'])==1
            rows.append(dict(case=mode,original_loop_with_real_sdk=True,forward_count=1,trace=owner_trace,select_timevals=owner_selects))
            continue
        assert helper_call('test_step')==-4 and helper_call('test_step')==-4
        assert not observed and get(symbols['test_forwards'])==0
        put(symbols['test_readers'],0)
        assert helper_call('test_step')==0 and helper_call('test_step')==0
        assert observed==callbacks and len(finalizers)==1 and get(symbols['test_forwards'])==1
        rows.append(dict(case=mode,real_sdk_drain_and_native_prepare=True,forward_count=1,
                         pending_steps=2,callbacks=[hex(a) for a in observed]))
        continue
    if mode == 'deferred-action':
        before = bytes(cpu.mem_read(root, 0x100))
        cpu.reg_write(UC_ARM_REG_R0, area + 0x3000)
        cpu.reg_write(UC_ARM_REG_SP, area + 0xf000)
        cpu.reg_write(UC_ARM_REG_LR, done)
        cpu.emu_start(0x718c0, done + 4, count=100000)
        assert cpu.reg_read(UC_ARM_REG_PC) == done
        assert cpu.reg_read(UC_ARM_REG_R0) == 0
        assert held == [(root, 3)] and not observed and not finalizers
        assert bytes(cpu.mem_read(root, 0x100)) == before
        # Restore is modeled, not a qualified GUI/USB/event-loop postponement.
        defer[0] = False
    cpu.reg_write(UC_ARM_REG_R0, root)
    cpu.reg_write(UC_ARM_REG_R1, command)
    cpu.reg_write(UC_ARM_REG_R2, output)
    cpu.reg_write(UC_ARM_REG_SP, area + 0xf000)
    cpu.reg_write(UC_ARM_REG_LR, done)
    cpu.emu_start(0x112fc, done + 4, count=100000)
    if native_subsystem:
        assert requests==[1]
        if mode=='subsystem-unresponsive':
            assert cpu.reg_read(UC_ARM_REG_PC)==0x33761c and get(subsystem+0x14)&0x100
            assert not finalizers and len(waits)==3
            rows.append(dict(case=mode,still_waiting=True,waits_observed=3,observation_stopped_by_fixture=True))
            continue
        assert waits==([] if mode=='subsystem-immediate' else [1,1]) and not get(subsystem+0x14)&0x100
    assert cpu.reg_read(UC_ARM_REG_PC) == done
    expected_count = 9 if mode == 'all-pending' else 1 if mode in ('already-pending', 'pcs-pending') else 0
    assert get(tracker) == expected_count, (mode, get(tracker))
    assert observed == ([] if mode == 'already-pending' else callbacks), (mode, observed)
    assert len(finalizers) == int(mode in ('synchronous', 'deferred-action') or native_basics)
    assert len(pcs) == int(mode in ('synchronous', 'pcs-pending', 'deferred-action') or native_basics)
    if native_basics:
        assert subsystem_release==([] if native_subsystem or mode=='native-environment2' else [8])
        assert get(auxiliary+0x48c)==(1 if mode=='native-environment2' else 0)
    if mode == 'all-pending':
        assert [get(tracker + 4 + 4 * index) for index in range(9)] == list(range(0x900, 0x909))
    if mode == 'already-pending':
        assert get(tracker + 4) == 0x777 and get(output) == 0x5a5a5a5a
    rows.append(dict(case=mode, callbacks=[hex(a) for a in observed], pending=expected_count,
                     finalizer_calls=len(finalizers), pcs_calls=len(pcs), output=get(output),
                     command=command,subsystem_release_arguments=subsystem_release,
                     deferred_action=bool(held), caller_stack_pointer_retained=False))

output_path = (build if sdk_native else ROOT / ('work/player-prepare-subsystem' if native_subsystem else 'work/player-prepare-basics' if native_basics else 'work/player-prepare-pending') / str(time.time_ns())) / 'report.json'
output_path.parent.mkdir(parents=True,exist_ok=True)
report = dict(passed=True, device_accessed=False, original_prepare_and_tracker_executed=True,
              cases=rows, stock_sha256=hashlib.sha256(raw).hexdigest(),
              script_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
              limits=['Component token outputs and preflight are modeled; finalizer body intercepted.',
                      'Nine pending tokens describe this command3 callback path, not a global capacity bound.',
                      'Deferred action is a boundary model; no actual SDK drain, intervening events, native lifetime guarantee or installed hook.',
                      'No SDK token allocation, native hook, concurrent worker or hardware qualification.'])
if sdk_native:
    report['limits']=['Worker readiness and context validity are models; component callbacks and finalizer effects are intercepted.',
                      'No real threads in this combined instruction replay; actual reader drain has a separate original-LinuxThreads test.',
                      'No installed hook, intervening-event ordering, manager timeout or physical USB/sleep qualification.']
    report['source_hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/check_player_prepare_pending.py','tools/fixtures/stock_info_host.c','tools/fixtures/stock_host_image.c','runtime/platform/player/deferred_prepare.h','runtime/platform/player/service_drain.h']}
    report['limits'].append('Real SDK deferred/drain/session/client code executes with original action/prepare; broker worker readiness, identity validation, component cleanup and finalizer effects are modeled.')
    report['limits'].append('Owner-loop case executes original input wait path and loop; select returns, other loop stages and worker readiness remain modeled, not wall-clock timing or full event dispatch.')
if native_basics:
    report['limits']=['Command6 root preparation plus callbacks16b74/f32c and wrappers5433c/bae24 execute; other component callbacks, environment/power-object getters, PM release, PCS and completion effects are models.',
                      'Environment getter values1/2 select different branches; these numbers do not identify a region/model or qualify audio/controller/media lifetime or physical power behavior.']
if native_subsystem:
    report['limits']=['Original command6 preparation,16b74/5433c/bae24,17de74/17d358/181294 execute; log literal identifies Asv1SegCtrlPlayer.c.',
                      'State getter, mutexes, request trigger, wait completion and lower release effects are models; other component callbacks and finalization remain intercepted.',
                      'Unresponsive case stops observation after three waits; it is not a real timeout and does not establish a physical device hang or cause of any earlier incident.']
output_path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
