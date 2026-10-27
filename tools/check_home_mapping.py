"""Replay the stock Home mapping getter; no patches, device IO or Sony services."""
from pathlib import Path
import hashlib
import io
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
expected = {
    1: [0x300000, 0x200000, 0x100000, 0x400000, 0x500000,
        0x600000, 0xa00000, 0x800000, 0x900000, 0xf00000],
    2: [0x900000, 0x300000, 0x100000, 0x400000, 0x500000,
        0x600000, 0xf00000, 0x800000, 0xa00000],
}
cases = []
for mode in [0, 1, 2, 3]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for segment in segments:
        u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    def hook(uc, pc, size, data):
        if pc in (0xe5f4, 0xf6c0):
            uc.reg_write(UC_ARM_REG_R0, mode if pc == 0xf6c0 else 0x60011000)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, 0x33)
    u.reg_write(UC_ARM_REG_R1, 0x60010000)
    u.reg_write(UC_ARM_REG_R2, 0x60010004)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0x751ec, 0x50000000, count=10000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    ptr, count = struct.unpack('<II', u.mem_read(0x60010000, 8))
    items = list(struct.unpack('<' + str(count) + 'I', u.mem_read(ptr, count * 4))) if count else []
    assert items == expected.get(mode, [])
    cases.append({'mode': mode, 'count': count, 'table': hex(ptr),
                  'items': [hex(item) for item in items]})
result = {
    'scope': 'Original 0x751ec instructions; mode getters mocked; no UI or hardware qualification',
    'SpiderApp_sha256': digest,
    'home_state': '0x33', 'state_table': '0x3f611c', 'state_rows': 95,
    'cases': cases,
    'limits': [
        'Mode values are not yet mapped to physical model/region settings.',
        '0x74634 and 0x3cf64 index the table without bounds checks.',
        '0x9e544 separately loops over nine indices; extending count alone is insufficient.',
        'No Home widget extension or firmware modification is performed.',
    ],
}
(ROOT / 'sources/native-home-mapping.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
