"""Replay the subtype-1 count route selected by stock Home descriptors.

Slot creation/removal is intercepted: this proves count routing, not allocation,
widget layout or real slot allocation.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
rows = []
for requested, expected in [(9, 9), (10, 11), (11, 11), (12, 13), (49, 49), (50, 49)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for s in segments:
        u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    slots = []
    def hook(uc, pc, size, data):
        if pc == 0xf808c:
            pass
        elif pc == 0xf80dc:
            slots.append(1)
        else:
            return
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    root, child, cache = 0x60012000, 0x60014000, 0x60010000
    u.mem_write(root + 0xb34, struct.pack('<I', 1))
    u.mem_write(root + 0xb68, struct.pack('<I', child))
    u.mem_write(child + 0xae8, struct.pack('<I', cache))
    u.reg_write(UC_ARM_REG_R0, root)
    u.reg_write(UC_ARM_REG_R1, requested)
    u.reg_write(UC_ARM_REG_R2, 0)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0xf2cc8, 0x50000000, count=10000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    count = struct.unpack('<I', u.mem_read(cache, 4))[0]
    assert count == expected and len(slots) == expected
    rows.append({'requested': requested, 'stored_slots': count, 'slot_create_calls': len(slots)})
result = {
    'scope': 'Original cache-count instructions; slot helpers mocked; no hardware or real allocations',
    'procedure': '0xf8f30', 'subtype': 1,
    'original_route': ['0xf2cc8', '0xfe9c0', '0xf8f30'], 'cases': rows,
    'limits': ['49 is a cache-helper limit, not a promised Home menu or app limit.',
               'Subtype selected by factory was separately replayed; live widget geometry, event bounds and labels remain unqualified.',
               'No firmware changes or physical device execution.'],
}
(ROOT / 'sources/native-home-cache.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
