"""Actual mode adapter and original queue/settings instructions; no physical device."""
import hashlib
import io
import json
import struct
import subprocess
import time
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from app_registry import ROOT

out = ROOT / 'work/stock-mode-control' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['runtime/platform/player/stock_gui.c', 'runtime/platform/player/stock_image.c',
           'runtime/native/sha256.c', 'tools/fixtures/stock_mode_control.c']
binary = out / 'adapter.arm'
subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
                '-Wno-misleading-indentation', '-march=armv5te', '-marm', '-mfloat-abi=soft',
                '-ffreestanding', '-fno-builtin', '-fno-pie', '-fno-stack-protector', '-nostdlib',
                '-no-pie', '-Wl,--build-id=none,-Ttext=0x50000000,-e,_start', *sources,
                '-lgcc', '-o', str(binary)], cwd=ROOT, check=True)
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
program = binary.read_bytes()
elf = ELFFile(io.BytesIO(program))
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
cases = [(mode, 'accepted') for mode in range(5)]
cases += [(4, name) for name in ('paused', 'unbound', 'busy', 'wrong-thread', 'changed-settings',
                                'inactive', 'transition', 'no-actor', 'no-controller', 'no-service',
                                'bad-session', 'unaligned-controller', 'allocation', 'post-session',
                                'post-actor', 'settings-open-failure', 'same-target')]
cases += [(-1, 'invalid'), (5, 'invalid')]
results = []
for canonical, case in cases:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for image in (raw, program):
        for segment in ELFFile(io.BytesIO(image)).iter_segments():
            if segment['p_type'] != 'PT_LOAD':
                continue
            start = int(segment['p_vaddr'])
            base = start & ~4095
            cpu.mem_map(base, (start - base + int(segment['p_memsz']) + 4095) & ~4095)
            cpu.mem_write(start, segment.data())
    area = 0x71000000
    cpu.mem_map(area, 0x20000)
    audio, handle, service, request = 0x6922d8, area + 0x1000, area + 0x2000, area + 0x3000
    actor, end = area + 0xa000, area + 0x1ff00
    put = lambda a, v: cpu.mem_write(a, struct.pack('<I', v & 0xffffffff))
    get = lambda a: struct.unpack('<I', cpu.mem_read(a, 4))[0]
    native = (0, 1, 2, 3, 5)[canonical] if 0 <= canonical < 5 else 0
    mode, state = (2, 2) if case == 'paused' else (1, 1 if case == 'transition' else 5)
    put(0x6831dc, 0 if case == 'no-actor' else actor)
    cpu.mem_write(actor, bytes((mode, state)))
    cpu.mem_write(actor + 8, b'\xff\xff')
    put(audio, 0 if case == 'no-controller' else handle + int(case == 'unaligned-controller'))
    put(audio + 0x44, native if case == 'same-target' else 99)
    put(handle, 0 if case == 'no-service' else service)
    put(handle + 4, 0xffffffff if case == 'bad-session' else 0x1234)
    put(service + 0x10, 6)
    put(service + 0x2c, service + 0x28)
    cpu.mem_write(0x65e810, bytes([native if case == 'same-target' else 3]))
    calls = []
    allocations = []
    gui = symbols['xw_mode_test_gui']
    def finish(value=0):
        cpu.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
    def hook(uc, pc, size, ignored):
        if pc == end:
            cpu.emu_stop()
            return
        args = tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3))
        if pc == symbols['xw_stock_gui_read']:
            if case == 'no-actor':
                finish(-2)
            else:
                for index, value in enumerate((mode, state, int(case != 'inactive'))):
                    put(args[1] + index * 4, value)
                finish()
        elif pc == 0xae0ec:
            assert args[:2] == (audio, native) and get(gui + 4) == 1
            calls.append('apply')
        elif pc == 0x27d78c:
            assert args[:3] == (handle, native, 0)
            calls.append('engine')
        elif pc == 0x27c378:
            allocations.append(args)
            if case == 'allocation':
                finish(0x2604)
            else:
                put(request + 0xc, 2)
                put(args[3], request)
                if case == 'post-session':
                    put(handle + 4, 0x4321)
                finish()
        elif pc == 0x38a18:
            assert args[:3] == (1, 0x100, native) and get(gui + 4) == 1
            calls.append('settings')
        elif pc == 0x269434:
            if case == 'post-actor':
                put(0x6831dc, actor + 0x100)
            if case == 'settings-open-failure':
                finish(0x1d19)
            else:
                put(args[2], area + 0x9000)
                finish()
        elif pc == 0x26a6e0:
            calls.append('store-value')
            assert args[3] == native
            finish()
        elif pc in (0x26ae04, 0x116d4, 0x285d24, 0x33b83c, 0x335788,
                    0x3357e4, 0x3354f4, 0x3365d8):
            finish()
    cpu.hook_add(UC_HOOK_CODE, hook)
    def call(name, *arguments):
        cpu.reg_write(UC_ARM_REG_SP, area + 0x1f000)
        cpu.reg_write(UC_ARM_REG_LR, end)
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), arguments):
            cpu.reg_write(reg, value & 0xffffffff)
        cpu.emu_start(symbols[name], end + 4, count=20000000)
        assert cpu.reg_read(UC_ARM_REG_PC) == end
        answer = cpu.reg_read(UC_ARM_REG_R0)
        return answer if answer < 0x80000000 else answer - 0x100000000
    if case != 'unbound':
        assert call('test_bind') == 0
    if case == 'changed-settings':
        cpu.mem_write(0x38a18, b'\x00')
    if case == 'wrong-thread':
        put(symbols['xw_test_thread'], 18)
    if case == 'busy':
        put(gui + 4, 1)
    answer = call('test_set_mode', canonical)
    expected = (1 if case in ('accepted', 'paused', 'same-target', 'settings-open-failure') else
                -9 if case in ('allocation', 'post-session', 'post-actor') else
                -1 if case == 'invalid' else -7 if case == 'unbound' else
                -3 if case == 'changed-settings' else -8 if case == 'unaligned-controller' else
                -2 if case in ('no-actor', 'no-controller', 'no-service', 'bad-session') else -4)
    assert answer == expected, (canonical, case, answer, calls)
    mutated = case in ('accepted', 'paused', 'same-target', 'settings-open-failure',
                       'allocation', 'post-session', 'post-actor')
    if mutated:
        assert calls[:3] == ['apply', 'engine', 'settings'] and len(allocations) == 1
        assert get(audio + 0x44) == native and bytes(cpu.mem_read(0x65e810, 1)) == bytes([native])
        assert ('store-value' in calls) == (case != 'settings-open-failure')
    else:
        assert not calls and not allocations
    assert get(gui + 4) == int(case == 'busy')
    results.append(dict(canonical=canonical, case=case, result=answer, calls=calls))
headers = ['runtime/platform/player/stock_gui.h', 'runtime/platform/player/stock_mode_binding.h',
           'runtime/platform/player/stock_controller_binding.h', 'runtime/platform/player/player.h',
           'tools/fixtures/stock_host_image.c', 'tools/test_stock_mode_control.py']
report = dict(passed=True, cases=results, original_mode_instructions=True, physical_device_accessed=False,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources + headers},
              limits=['GUI observation, source allocation, queue synchronization and persistence primitives are modeled.',
                      'Original native apply, queue construction, settings setter and cached getter execute.',
                      'ACCEPTED is admission and observed cached preference, not physical engine completion or durable save.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, cases=len(results), report=str(out / 'report.json')), indent=2))
