"""Differentially replay original b0464 selectors in stock and candidate ELFs."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
                              UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
                              UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(stock).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
manifest = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text())
candidate = (ROOT / manifest['artifact']).read_bytes()
assert hashlib.sha256(candidate).hexdigest() == manifest['candidate_sha256']
saved_regs = [UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
              UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11]


def replay(raw, selector, error):
    elf = ELFFile(io.BytesIO(raw))
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
    low = min(s['p_vaddr'] for s in segments) & ~4095
    high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for s in segments:
        u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x30000)
    u.mem_write(0x60022000, b'about:blank\0')
    u.mem_write(0x693398, struct.pack('<II', 0x60022000, 0))
    trace = []
    def text_at(address):
        result = bytearray()
        for i in range(256):
            c = u.mem_read(address + i, 1)[0]
            if not c:
                return result.decode()
            result.append(c)
        raise AssertionError('Unterminated argument')
    def hook(uc, pc, size, data):
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x265510:
            assert uc.reg_read(UC_ARM_REG_LR) == 0xb047c
            uc.reg_write(UC_ARM_REG_R0, 0x60021000)
        elif pc == 0xb00bc:
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == 0x33b83c:
            trace.append({'log_stage': args[2], 'value': args[3]})
            uc.reg_write(UC_ARM_REG_R0, 0x99)
        elif pc == syms['memcpy']:
            uc.mem_write(args[0], bytes(uc.mem_read(args[1], args[2])))
        elif pc == 0x2664d0:
            assert args[0] == 0x60021000
            assert uc.reg_read(UC_ARM_REG_LR) == 0xb0504
            name = text_at(args[1])
            trace.append({'lookup': name})
            app = {'SpiderApp': 1, 'Responder': 2, 'netfront': 0x20001}[name]
            uc.mem_write(args[2], struct.pack('<I', app))
            uc.reg_write(UC_ARM_REG_R0, 123 if error == 'lookup' else 0)
        elif pc == 0x2681e8:
            assert uc.reg_read(UC_ARM_REG_LR) == 0xb0558
            strings = []
            if args[2]:
                for i in range(8):
                    p = struct.unpack('<I', uc.mem_read(args[2] + i * 4, 4))[0]
                    if not p:
                        break
                    strings.append(text_at(p))
            trace.append({'change_id': args[1], 'args_null': args[2] == 0,
                          'args': strings, 'flag': args[3]})
            uc.reg_write(UC_ARM_REG_R0, 456 if error == 'change' else 0)
        else:
            return
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, selector)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    for i, reg in enumerate(saved_regs):
        u.reg_write(reg, 0x11220000 + i)
    u.emu_start(0xb0464, 0x50000000, count=100000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    assert u.reg_read(UC_ARM_REG_SP) == 0x60008000
    assert [u.reg_read(reg) for reg in saved_regs] == [0x11220000 + i for i in range(8)]
    return {'trace': trace, 'return_register': u.reg_read(UC_ARM_REG_R0)}


rows = []
for selector in (0, 1, 2, 3, 5, 0xffffffff):
    for error in ('none', 'lookup', 'change'):
        before, after = replay(stock, selector, error), replay(candidate, selector, error)
        assert before == after, (selector, error, before, after)
        rows.append({'selector': selector, 'error': error, 'stock_equals_candidate': True,
                     'observed': after})
result = {'scope': 'Original switcher instructions; APF, diagnostics and libc simulated; no physical device',
          'candidate_sha256': manifest['candidate_sha256'], 'cases': rows,
          'limits': ['Does not execute real browser/USB/SpiderApp services.',
                     'Service return PCs are original b0464 addresses; actual exception unwinding is not exercised.']}
(ROOT / 'sources/native-switcher-candidate-tests.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'{len(rows)} stock/candidate switcher comparisons passed, including UsbMode arguments')
