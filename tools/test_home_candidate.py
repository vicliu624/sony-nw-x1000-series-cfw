"""Execute the patched ARM hook from the candidate ELF with native services mocked."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

ROOT = Path(__file__).resolve().parents[1]
area = ROOT / 'work/home-entry-candidate'
report = json.loads((area / 'candidate.json').read_text())
raw = (area / 'SpiderApp.analysis-only.elf').read_bytes()
assert hashlib.sha256(raw).hexdigest() == report['candidate_sha256']
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
saved_regs = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
              UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]
rows = []
for mode, count in [(1, 10), (2, 9), (0, 0), (3, 0)]:
    if count:
        cases = [(index, 'stock') for index in range(count)]
        cases += [(count, name) for name in ('launch', 'state-machine-launch', 'lookup-error', 'wrong-class', 'change-error', 'null-context')]
        cases += [(count + 1, 'out-of-range'), (0xffffffff, 'out-of-range')]
    else:
        cases = [(0, 'unsupported-mode'), (0xffffffff, 'unsupported-mode')]
    for index, case in cases:
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(low, high - low)
        for s in segments:
            u.mem_write(s['p_vaddr'], s.data())
        u.mem_map(0x50000000, 4096)
        u.mem_map(0x60000000, 0x30000)
        u.mem_write(0x613e4c, struct.pack('<I', mode))
        calls = []
        def word(address):
            return struct.unpack('<I', u.mem_read(address, 4))[0]
        def cstring(address):
            result = bytearray()
            for i in range(256):
                c = u.mem_read(address + i, 1)[0]
                if not c:
                    return result.decode()
                result.append(c)
            raise AssertionError('unterminated string')
        def hook(uc, pc, size, data):
            if pc in (0xb00bc, 0x33b83c):
                uc.reg_write(UC_ARM_REG_R0, 0)
            elif pc == 0x265510:
                assert uc.reg_read(UC_ARM_REG_LR) == 0xb047c
                calls.append('context')
                uc.reg_write(UC_ARM_REG_R0, 0 if case == 'null-context' else 0x60021000)
            elif pc == 0x2664d0:
                assert uc.reg_read(UC_ARM_REG_LR) == 0xb0504
                assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
                assert uc.reg_read(UC_ARM_REG_R0) == 0x60021000
                assert cstring(uc.reg_read(UC_ARM_REG_R1)) == '/contents/HOMEBREW/launcher/app'
                uc.mem_write(uc.reg_read(UC_ARM_REG_R2), struct.pack('<I', 0x20001 if case == 'wrong-class' else 0x30001))
                calls.append('lookup')
                uc.reg_write(UC_ARM_REG_R0, 123 if case == 'lookup-error' else 0)
            elif pc == 0x2681e8:
                assert uc.reg_read(UC_ARM_REG_LR) == 0xb0558
                assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0
                assert [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)] == [0x60021000, 0x30001, 0, 0]
                calls.append('change')
                uc.reg_write(UC_ARM_REG_R0, 456 if case == 'change-error' else 0)
            elif pc == 0x737f0:
                # Stop before any stock feature/device code. Restore exactly the
                # displaced native push, and supply a distinctive native result.
                assert index < count
                assert [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)] == [0x60022000, 0x4a0111, index, 0x1234]
                sp = uc.reg_read(UC_ARM_REG_SP)
                for reg, offset in zip(saved_regs[:4], (0, 4, 8, 12)):
                    uc.reg_write(reg, word(sp + offset))
                target = word(sp + 16)
                uc.reg_write(UC_ARM_REG_SP, sp + 20)
                uc.reg_write(UC_ARM_REG_R0, 0x3401)
                uc.reg_write(UC_ARM_REG_PC, target)
                calls.append('stock-continuation')
                return
            else:
                return
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, hook)
        for reg, value in [(UC_ARM_REG_R0, 0x60022000), (UC_ARM_REG_R1, 0x4a0111),
                           (UC_ARM_REG_R2, index), (UC_ARM_REG_R3, 0x1234),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        for i, reg in enumerate(saved_regs):
            u.reg_write(reg, 0x11220000 + i)
        if case == 'state-machine-launch':
            context = bytearray(32)
            context[0], context[1], context[13] = 0x33, 2, 4
            struct.pack_into('<I', context, 4, 0x3f55d8)
            u.mem_write(0x60022000, bytes(context))
        u.emu_start(0x17c608 if case == 'state-machine-launch' else 0x737ec,
                    0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert u.reg_read(UC_ARM_REG_SP) == 0x60008000
        assert [u.reg_read(reg) for reg in saved_regs] == [0x11220000 + i for i in range(8)]
        assert u.reg_read(UC_ARM_REG_R0) == (0x3401 if case == 'stock' else 0)
        expected = (['stock-continuation'] if case == 'stock' else
                    ['context', 'lookup', 'change'] if case in ('launch', 'state-machine-launch', 'change-error') else
                    ['context', 'lookup'] if case in ('lookup-error', 'wrong-class') else
                    ['context'] if case == 'null-context' else [])
        assert calls == expected, (mode, index, case, calls)
        if case == 'state-machine-launch':
            assert bytes(u.mem_read(0x60022000, 2)) == b'\x33\x02'
        rows.append({'mode': mode, 'index': index, 'case': case, 'calls': calls,
                     'stack_and_callee_saved_restored': True})
result = {'scope': 'Actual modified ELF branch and leaf adapters; original b0464 service call sites executed; APF/log/feature continuation mocked',
          'candidate_sha256': report['candidate_sha256'], 'cases': rows,
          'physical_device_access': False,
          'limits': ['Does not prove the real Home touch event reaches this handler.',
                     'Native feature execution and complete APF/USB/sleep lifecycle are not run.',
                     'ELF mapping is provided by Unicorn, not the Sony device loader.']}
(ROOT / 'sources/native-home-candidate-tests.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'{len(rows)} patched ARM selection cases passed; native services mocked')
