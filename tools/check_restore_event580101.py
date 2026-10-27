"""Replay original event580101 state dispatch and field/helper effects.

Only the two-word provider at 0x33c528 is virtual. No actual system calls,
display or input operation is permitted by this fixture.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
u.mem_map(0x8000, 0x900000)
for segment in elf.iter_segments():
    if segment['p_type'] == 'PT_LOAD':
        u.mem_write(segment['p_vaddr'], segment.data())
u.mem_map(0x50000000, 4096)
u.mem_map(0x60000000, 0x20000)
object_address = 0x671c40
hits, providers = [], []
def hook(uc, pc, size, data):
    if pc == 0x9b814:
        hits.append(pc)
    elif pc == 0x33c528:
        address = uc.reg_read(UC_ARM_REG_R0)
        assert address == object_address + 16
        providers.append(address)
        uc.mem_write(address, struct.pack('<II', 123, 456))
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
def interrupt(uc, number, data):
    raise AssertionError('Unexpected system call in bounded event consumer')
u.hook_add(UC_HOOK_CODE, hook)
u.hook_add(UC_HOOK_INTR, interrupt)
rows = []
for state in range(1, 5):
    for previous in (0, 6, 7, 8):
        for incoming in (0, 6, 7, 8):
            context = bytearray(32)
            context[0], context[1], context[13] = 1, state, 24
            struct.pack_into('<I', context, 4, 0x412b70)
            u.mem_write(0x60010000, bytes(context))
            u.mem_write(object_address, bytes(64))
            u.mem_write(object_address + 16, struct.pack('<II', 111, 222))
            u.mem_write(object_address + 32, struct.pack('<I', previous))
            hits.clear()
            providers.clear()
            for reg, value in [(UC_ARM_REG_R0, 0x60010000), (UC_ARM_REG_R1, 0x580101),
                               (UC_ARM_REG_R2, incoming), (UC_ARM_REG_R3, 0),
                               (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            u.emu_start(0x17c608, 0x50000000, count=20000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and u.reg_read(UC_ARM_REG_R0) == 0
            expected_provider = previous in (6, 7) and incoming not in (6, 7)
            assert hits == [0x9b814] and len(providers) == int(expected_provider)
            assert struct.unpack('<I', u.mem_read(object_address + 32, 4))[0] == incoming
            assert struct.unpack('<II', u.mem_read(object_address + 16, 8)) == ((123, 456) if expected_provider else (111, 222))
            rows.append({'state_fixture': state, 'previous_field32': previous,
                         'incoming_field32': incoming, 'provider_called': expected_provider})
report = {'scope': 'Original dispatcher/action/helper effects; two-word service output virtual',
          'SpiderApp_sha256': digest, 'descriptor_table': '0x412b70', 'action': '0x9b814',
          'singleton': '0x671c40', 'cases': rows,
          'limits': ['State and object values are fixtures, not assigned physical mode names.',
                     'The provider output and clock/hardware semantics are not qualified.',
                     'No screen redraw, touch acquisition or other restoration is proved by this consumer.']}
(ROOT / 'sources/native-restore-event580101.json').write_text(json.dumps(report, indent=2) + '\n')
print('64 original event580101 cases: field update and conditional helper effects verified; no syscalls')
