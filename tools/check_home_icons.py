"""Replay stock Home icon lookup and bounds; graphics services are mocked."""
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
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', action='store_true', help='Use the analysis-only patched ELF')
args = parser.parse_args()
candidate = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text()) if args.candidate else None
raw = (ROOT / (candidate['artifact'] if candidate else 'work/targets-jp/SpiderApp')).read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == (candidate['candidate_sha256'] if candidate else '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85')
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
expected = {1: list(range(54, 64)), 2: [62, 54, 56, 57, 58, 59, 63, 61, 60], 0: []}
if candidate:
    expected[1].append(63)
    expected[2].append(63)
rows = []
for mode, table in expected.items():
    for index in range(max(len(v) for v in expected.values()) + 1):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(low, high - low)
        for s in segments:
            u.mem_write(s['p_vaddr'], s.data())
        u.mem_map(0x50000000, 4096)
        u.mem_map(0x60000000, 0x20000)
        calls = []
        def hook(uc, pc, size, data):
            if pc == 0x10a118:
                uc.mem_write(uc.reg_read(UC_ARM_REG_R1), bytes(60))
            elif pc == 0xb19e4:
                uc.reg_write(UC_ARM_REG_R0, mode)
            elif pc == 0xf6c58:
                calls.append([uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2)])
                uc.mem_write(uc.reg_read(UC_ARM_REG_R3), struct.pack('<I', 0x60012000))
                uc.reg_write(UC_ARM_REG_R0, 0)
            elif pc in (0xf647c, 0x1094f0, 0xf6ec8, 0xe87f4, 0xe9690):
                uc.reg_write(UC_ARM_REG_R0, 0x60012000)
            else:
                return
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, hook)
        for reg, value in [(UC_ARM_REG_R0, 0x60010000), (UC_ARM_REG_R1, 0x60011000),
                           (UC_ARM_REG_R2, 0x60011100), (UC_ARM_REG_R3, 0x60011200),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.mem_write(0x60008000, struct.pack('<I', index))
        u.emu_start(0xb5898, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert calls == ([[0, table[index]]] if index < len(table) else []), (mode, index, calls)
        rows.append({'mode': mode, 'index': index, 'resource_requests': calls})
result = {
    'scope': ('Patched' if candidate else 'Original') + ' icon selection instructions with mode/graphics services mocked; no actual rendering',
    'SpiderApp_sha256': digest, 'procedure': '0xb5898', 'caller': '0x2d26c',
    'tables': {'1': {'address': hex(candidate['symbols']['hb_home_icons_10']) if candidate else '0x41669c', 'texture_ids': expected[1]},
               '2': {'address': hex(candidate['symbols']['hb_home_icons_9']) if candidate else '0x416678', 'texture_ids': expected[2]}},
    'texture_group': 0, 'cases': rows,
    'limits': ['Mode values do not identify a qualified physical model.',
               'No additional item or texture has been installed on a device.',
               'The original ten/nine bounds must not be bypassed without extending the associated structures.',
               'Does not validate widget geometry, touch selection or real framebuffer presentation.'],
}
(ROOT / ('sources/native-home-candidate-icons.json' if candidate else 'sources/native-home-icons.json')).write_text(json.dumps(result, indent=2) + '\n')
print(f'{len(rows)} ' + ('patched' if candidate else 'original') + ' Home icon lookup/bounds cases passed; graphics mocked')
