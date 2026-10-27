"""Replay stock GUI-to-Home event forwarding, stopping before feature execution."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
rows = []
for index in (0, 4, 8):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for s in segments:
        u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    queued, selected = [], []
    def hook(uc, pc, size, data):
        if pc == 0xa57f0:
            queued.append([uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)])
            uc.reg_write(UC_ARM_REG_R0, 1)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif pc == 0x737ec:
            selected.append(uc.reg_read(UC_ARM_REG_R2))
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def event(mode, state, table, number, arg1, arg2):
        context = bytearray(32)
        context[0] = mode
        context[1] = state
        struct.pack_into('<I', context, 4, table)
        context[13] = 10
        u.mem_write(0x60010000, bytes(context))
        for reg, value in [(UC_ARM_REG_R0, 0x60010000), (UC_ARM_REG_R1, number),
                           (UC_ARM_REG_R2, arg1), (UC_ARM_REG_R3, arg2),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0x17c608, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert u.reg_read(UC_ARM_REG_R0) == 0
    event(1, 11, 0x3ea150, 0x2010b, index, 0)
    assert queued == [[0x4a0111, 0, index, 0]], queued
    event(0x33, 2, 0x3f55d8, queued[0][0], queued[0][2], queued[0][3])
    assert selected == [index]
    rows.append({'index': index, 'queued_event': hex(queued[0][0]),
                 'selection_handler': '0x737ec', 'received_index': selected[0]})
result = {
    'scope': 'Original state-machine and GUI forwarding instructions; queue and final feature handler intercepted; no touch/UI hardware',
    'SpiderApp_sha256': digest,
    'gui_context': {'mode': 1, 'state': 11, 'event': '0x2010b'},
    'home_context': {'mode': '0x33', 'state': 2, 'event': '0x4a0111'},
    'rows': rows,
    'limits': ['Contexts are constructed fixtures, not a complete UI startup.',
               'Does not identify the actual widget producing 0x2010b.',
               'No new index is passed to the unbounded stock Home lookup.',
               'Does not validate a new launcher button or physical device input.'],
}
(ROOT / 'sources/native-home-dispatch.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
