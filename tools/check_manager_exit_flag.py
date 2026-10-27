"""Replay stock process-reaper classification from virtual wait records.

This is the managed process (appproxy for class 3), not its game child's status.
Registry predicates, pipe, locking and callback delivery are simulated.
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
raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf = ELFFile(io.BytesIO(raw))
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for status, expected_signal, expected_flag in [(0, 0, 1), (0x100, 0, 0),
        (0x7f00, 0, 0), (15, 0, 0), (15, 15, 1), (0x8f, 15, 1),
        (9, 15, 0), (0x7f, 15, 0), (0x137f, 19, 0)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    ctx, app, pid = 0x60010000, 0x30001, 321
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    put(ctx + 0x41c4, 1)
    put(ctx + 0x41c0, 77)
    put(ctx + 0x41b0, 0x50000100)
    put(ctx + 0x41b4, ctx)
    put(0x60002008, app)
    lookups, callbacks = [], []
    removed = []
    def hook(uc, pc, size, data):
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        result = 0
        if pc == 0x19ef4:
            result = 1
        elif pc == 0x16028:
            result = 101
        elif pc == symbols['read']:
            assert args[0] == 101 and args[2] == 8
            uc.mem_write(args[1], struct.pack('<II', pid, status))
            result = 8
        elif pc == 0x16510:
            assert args[0] == ctx + 8
            key = struct.unpack('<I', uc.mem_read(args[2], 4))[0]
            lookups.append((args[1], key))
            result = 0x60002000
        elif pc == 0x16720:
            result = expected_signal
        elif pc == 0x163dc:
            removed.append(struct.unpack('<I', uc.mem_read(args[2], 4))[0])
        elif pc == 0x50000100:
            callbacks.append(args)
        elif pc not in (0xa188, 0x1c4d0, 0x16578):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, ctx)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0x11998, 0x50000000, count=20000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    assert lookups == [(0x16740, pid), (0x16728, app)]
    assert removed == [app] and callbacks == [[app, expected_flag, ctx]]
    rows.append({'managed_wait_status': status, 'registry_expected_signal': expected_signal,
                 'callback_app_id': hex(app), 'callback_normal_flag': expected_flag})
report = {'scope': 'Original sysmgrd 0x11998 with virtual wait record and process registry',
          'sysmgrd_sha256': digest, 'cases': rows,
          'limits': ['The expected-signal registry getter is mocked, not assigned meaning from its name.',
                     'Does not prove how APF unregister and native process death are ordered.',
                     'The status is that of the managed proxy, not the proxy child game.',
                     'No kernel waitpid, actual pipes, IPC or physical hardware ran.']}
(ROOT / 'sources/native-manager-exit-flag.json').write_text(json.dumps(report, indent=2) + '\n')
print('Nine original reaper classifications and callback app IDs verified')
