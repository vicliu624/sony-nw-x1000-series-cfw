"""Actual ARM select wrapper/stock callsite guard; readiness/owner ports are modeled."""
import hashlib
import io
import json
import struct
import subprocess
import time
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from build_player_host import ROOT, CORE_SOURCES

out = ROOT / 'work/owner-wait-anchor' / str(time.time_ns())
out.mkdir(parents=True)
sources = [*CORE_SOURCES, 'runtime/platform/player/owner_wait.c',
           'tools/fixtures/player_host_anchor.c', 'tools/fixtures/owner_wait_ports.c']
binary = out / 'anchor.arm'
subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
    '-Wno-misleading-indentation', '-DXW_PLAYER_REMOTE_FACTORY', '-march=armv5te', '-marm',
    '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin', '-fno-pie', '-fno-stack-protector',
    '-nostdlib', '-no-pie', '-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',
    *sources, '-lgcc', '-o', str(binary)], cwd=ROOT, check=True)
stock_bytes = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(stock_bytes).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
stock = ELFFile(io.BytesIO(stock_bytes))
helper = ELFFile(io.BytesIO(binary.read_bytes()))
symbols = {s.name: s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
scenarios = ['private-only', 'original-only', 'both', 'wrong-thread', 'foreign-caller',
             'wrong-image', 'busy', 'unbound', 'writable', 'native-input-loop', 'private-write', 'queued-ui', 'queued-ui-native-loop', 'queued-foreign',
             'transition', 'transition-input-loop', 'transition-short-wait', 'transition-foreign',
             'native-worker-query', 'native-worker-notice', 'native-worker-write']
for scenario in scenarios:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    segments = [s for image in (stock, helper) for s in image.iter_segments() if s['p_type'] == 'PT_LOAD']
    ranges = sorted((s['p_vaddr'] & ~4095, (s['p_vaddr'] + s['p_memsz'] + 4095) & ~4095)
                    for s in segments)
    merged = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in merged:
        cpu.mem_map(start, end - start)
    for segment in segments:
        cpu.mem_write(segment['p_vaddr'], segment.data())
    area = 0x70000000
    cpu.mem_map(area, 0x10000)
    put = lambda address, value: cpu.mem_write(address, struct.pack('<I', value & 0xffffffff))
    get = lambda address: struct.unpack('<I', cpu.mem_read(address, 4))[0]
    for name, value in [('host_ready', scenario != 'unbound'), ('host_owner', 17),
                        ('host_busy', scenario == 'busy'), ('xw_test_thread', 18 if scenario == 'wrong-thread' else 17),
                        ('test_wait_native', not scenario.startswith('native-worker-') and scenario not in ('private-only', 'native-input-loop', 'private-write', 'queued-ui', 'queued-ui-native-loop', 'transition-input-loop')),
                        ('test_wait_native_ipc', {'native-worker-query':1,'native-worker-notice':2,'native-worker-write':3}.get(scenario,0)),
                        ('test_wait_writer', scenario == 'private-write'),
                        ('test_wait_local_ready', scenario.startswith('queued-')),
                        ('test_wait_handoff_pending', scenario.startswith('transition')),
                        ('test_wait_no_private_fds', scenario.startswith(('queued-', 'transition', 'native-worker-'))),
                        ('test_wait_private', scenario not in ('original-only', 'queued-ui', 'queued-ui-native-loop')), ('test_errno', 1234)]:
        put(symbols[name], int(value))
    if scenario == 'wrong-image':
        put(0xe1b18, 0)
    readable, timeout, stack = area, area + 0x100, area + 0xf000
    put(readable, 8)
    put(timeout, 60)
    put(timeout + 4, 0)
    if scenario == 'transition-short-wait':
        put(timeout, 0)
        put(timeout + 4, 10000)
    put(stack, timeout)
    caller = area + 0xff00 if scenario in ('foreign-caller', 'native-input-loop', 'queued-ui-native-loop', 'queued-foreign', 'transition-input-loop', 'transition-foreign') else 0xe1b1c
    native_flags = []
    def stop(uc, pc, size, data):
        if pc == caller:
            uc.emu_stop()
        elif scenario in ('native-input-loop', 'queued-ui-native-loop', 'transition-input-loop'):
            if pc == 0xd85c:
                uc.reg_write(UC_ARM_REG_PC, symbols['memcpy'])
            elif pc == 0xe0fc:
                uc.reg_write(UC_ARM_REG_PC, symbols['select'])
            elif pc == 0xe2efc or pc == area + 0xfe00:
                if pc == area + 0xfe00:
                    native_flags.append(uc.reg_read(UC_ARM_REG_R0))
                uc.reg_write(UC_ARM_REG_R0, 0)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    cpu.hook_add(UC_HOOK_CODE, stop)
    for reg, value in [(UC_ARM_REG_R0, 4), (UC_ARM_REG_R1, readable),
                       (UC_ARM_REG_R2, area + 0x200 if scenario == 'writable' else 0),
                       (UC_ARM_REG_R3, 0), (UC_ARM_REG_SP, stack), (UC_ARM_REG_LR, caller)]:
        cpu.reg_write(reg, value)
    if scenario in ('native-input-loop', 'queued-ui-native-loop', 'transition-input-loop'):
        put(0x4f7820, area + 0x2000)
        cpu.reg_write(UC_ARM_REG_R0, 60000000)
        cpu.reg_write(UC_ARM_REG_LR, caller)
        cpu.emu_start(0xe44a4, caller + 4, count=200000)
        state = area + 0x400
        put(state + 0x78, 3)
        put(state + 0x58, area + 0xfe00)
        put(state + 0x5c, 3)
        put(state + 0xfc, 8)
        cpu.reg_write(UC_ARM_REG_R0, state)
        cpu.reg_write(UC_ARM_REG_SP, stack)
        cpu.reg_write(UC_ARM_REG_LR, caller)
        cpu.emu_start(0xe1aa0, caller + 4, count=2000000)
        assert cpu.reg_read(UC_ARM_REG_PC) == caller and native_flags == [0]
        assert get(symbols['test_wait_nfds']) == (42 if scenario == 'native-input-loop' else 4) and get(symbols['test_wait_collects']) == 3
        assert get(symbols['test_wait_timeout']) == (60 if scenario == 'native-input-loop' else 0), scenario
        assert get(symbols['test_wait_timeout'] + 4) == (200000 if scenario == 'transition-input-loop' else 0), scenario
        continue
    cpu.emu_start(symbols['select'], caller + 4, count=2000000)
    assert cpu.reg_read(UC_ARM_REG_PC) == caller, scenario
    extended = scenario.startswith('native-worker-') or scenario in ('private-only', 'original-only', 'both', 'private-write', 'queued-ui', 'transition', 'transition-short-wait')
    expected_nfds = 44 if scenario == 'native-worker-notice' else 43 if scenario.startswith('native-worker-') else 42 if scenario in ('private-only', 'original-only', 'both', 'private-write') else 4
    assert get(symbols['test_wait_nfds']) == expected_nfds, scenario
    assert get(symbols['test_wait_collects']) == (3 if extended else 0), scenario
    assert get(symbols['test_wait_calls']) == 1, scenario
    assert get(symbols['test_wait_entry_errno']) == 1234 and get(symbols['test_errno']) == 77, scenario
    expected = 0 if scenario.startswith('native-worker-') or scenario in ('private-only', 'private-write', 'queued-ui') else 1
    assert cpu.reg_read(UC_ARM_REG_R0) == expected and get(readable) == (8 if expected else 0), scenario
    assert get(readable + 4) == 0, scenario
    if scenario.startswith('queued-'):
        assert get(symbols['test_wait_timeout']) == (0 if scenario == 'queued-ui' else 60), scenario
    if scenario.startswith('transition'):
        assert get(symbols['test_wait_timeout']) == (60 if scenario == 'transition-foreign' else 0), scenario
        assert get(symbols['test_wait_timeout'] + 4) == (0 if scenario == 'transition-foreign' else 10000 if scenario == 'transition-short-wait' else 200000), scenario
    if scenario in ('private-write', 'native-worker-write'):
        assert get(symbols['test_wait_writable']) != 0
    else:
        assert get(symbols['test_wait_writable']) == (area + 0x200 if scenario == 'writable' else 0), scenario
report = dict(passed=True, scenarios=scenarios, actual_arm_wrapper=True,
              original_instruction_guard=True, readiness_ports_modeled=True,
              device_accessed=False, firmware_created=False,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                             for p in [*sources, 'runtime/platform/player/owner_wait.h',
                                       'tools/test_owner_wait_anchor.py']})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
print('Report:', out / 'report.json')
