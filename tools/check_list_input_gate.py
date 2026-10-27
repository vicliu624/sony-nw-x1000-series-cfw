"""Replay original list state-difference gate; managers are virtual, no device I/O."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
rows = []
for group, globally_set, locally_set, expected in ((0, 1, 0, 0x100), (2, 1, 0, 0x200), (2, 0, 0, 0), (2, 1, 1, 0)):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for s in elf.iter_segments():
        if s['p_type'] == 'PT_LOAD':
            u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x80000)
    source, output, widget, global_state = 0x60001000, 0x60002000, 0x60003000, 0x60004000
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    put(source + 0x3c, widget)
    put(source + 0x50, 0xffffffff)
    put(widget + 0x4d0, 74)
    visited = []
    def hook(uc, pc, size, data):
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc in (0x108bec, 0x108c78, 0x108bc8, 0x104870):
            result = 0
        elif pc == 0x108994:
            result = global_state
        elif pc == 0x10899c:
            result = 1
        elif pc == 0x111d74:
            assert a[2] == 0 and a[0] in (global_state, source + 0x44)
            result = (globally_set if a[0] == global_state else locally_set) if a[1] == group else 0
        elif pc == 0x104abc:
            result = 0xffffffff
        elif pc == 0xf933c:
            visited.append('group0-state-update')
            result = 0
        elif pc == 0x104aa4:
            result = 0
        else:
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def interrupt(uc, number, data):
        raise AssertionError(f'Unexpected syscall/interrupt {number}')
    u.hook_add(UC_HOOK_CODE, hook)
    u.hook_add(UC_HOOK_INTR, interrupt)
    for reg, value in ((UC_ARM_REG_R0, source), (UC_ARM_REG_R1, output), (UC_ARM_REG_SP, 0x60078000), (UC_ARM_REG_LR, 0x50000000)):
        u.reg_write(reg, value)
    u.emu_start(0xf9c54, 0x50000000, count=10000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    flags = struct.unpack('<I', u.mem_read(output + 0x3c, 4))[0]
    assert flags == expected, (group, globally_set, locally_set, flags)
    rows.append(dict(group=group, global_state=globally_set, local_state=locally_set, output_flags=flags, helper_calls=visited))
report = dict(input_sha256=digest, procedure='0xf9c54', cases=rows,
              limits=['Original gate instructions execute; style/global/local managers and group0 helper responses are virtual.',
                      'Group numbers are not assigned to physical touch or keys; group1 and the full action producer are not covered.',
                      'No physical hardware, syscalls, firmware generation or source-binary changes.'])
(ROOT / 'sources/native-list-input-gate.json').write_text(json.dumps(report, indent=2) + '\n')
print('Four original list state-difference gate cases passed; no hardware qualification')
