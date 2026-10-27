"""Replay stock RUN-state exit handling with launch/activate/existence mocked."""
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
raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf = ELFFile(io.BytesIO(raw))
cases = []
for running, exiting in [(True, 0x30001), (False, 0x30001), (True, 0x30002)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    context = 0x60010000
    state = bytearray(0x500)
    struct.pack_into('<III', state, 0, 0, 0x30001, 0x30001)
    for offset, callback in [(0x494, 0x50000100), (0x49c, 0x50000200), (0x4a4, 0x50000300)]:
        struct.pack_into('<I', state, offset, callback)
    u.mem_write(context, bytes(state))
    calls = []
    def hook(uc, pc, size, data):
        if pc in (0x50000100, 0x50000200, 0x50000300):
            target = uc.reg_read(UC_ARM_REG_R0)
            operation = {0x50000100: 'launch', 0x50000200: 'activate', 0x50000300: 'exists'}[pc]
            calls.append({'operation': operation, 'target': target})
            uc.reg_write(UC_ARM_REG_R0, int(running) if operation == 'exists' else 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif pc == 0x1485c:
            calls.append({'operation': 'set_state', 'table': hex(uc.reg_read(UC_ARM_REG_R1))})
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif pc in (0x1c888, 0x1c8c8):
            raise AssertionError('stock panic path reached')
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, 0)
    u.reg_write(UC_ARM_REG_R1, exiting)
    u.reg_write(UC_ARM_REG_R2, context)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0x1538c, 0x50000000, count=10000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    target = struct.unpack('<I', u.mem_read(context + 8, 4))[0]
    if exiting == 0x30001:
        assert target == 1
        assert calls == [
            {'operation': 'exists', 'target': 1},
            {'operation': 'activate' if running else 'launch', 'target': 1},
            {'operation': 'set_state', 'table': '0x34bec' if running else '0x34c40'},
        ], calls
    else:
        assert target == 0x30001 and calls == []
    cases.append({'default_running': running, 'exiting_id': hex(exiting),
                  'next_target': target, 'calls': calls})
result = {
    'scope': 'Original sysmgrd RUN-state EXIT instructions; service callbacks mocked; no physical device',
    'sysmgrd_sha256': digest, 'procedure': '0x1538c', 'cases': cases,
    'conclusion': 'A matching RUN-state exit chooses ID 1, activates it if running or requests its launch.',
    'limits': [
        'Does not prove appproxy exit reaches this state in every lifecycle path.',
        'Launch/active acknowledgement, SpiderApp hardware reacquisition, USB and sleep remain unqualified.',
        'Successful mocked callbacks are not a real Walkman return test.',
    ],
}
(ROOT / 'sources/native-return-replay.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
