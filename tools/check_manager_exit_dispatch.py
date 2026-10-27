"""Replay original process-exit dispatcher, not the complete APF service.

REA procExitCb evidence is checked against original instructions. Helper calls,
state-machine delivery and callbacks are virtual. No device or Sony process runs.
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
rows = []
for state in range(7):
    for normal in (True, False):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(0x8000, 0x40000)
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                u.mem_write(segment['p_vaddr'], segment.data())
        u.mem_map(0x50000000, 4096)
        u.mem_map(0x60000000, 0x20000)
        ctx, app = 0x60010000, 0x30001
        def put(address, value):
            u.mem_write(address, struct.pack('<I', value))
        def word(address):
            return struct.unpack('<I', u.mem_read(address, 4))[0]
        put(ctx + 0x503c, state)
        put(ctx + 0x5144, app)
        put(ctx + 0x5148, 99)
        put(ctx + 0x51b4, 0x50000100)
        put(ctx + 0x51b8, 0x12345678)
        trace, events, notices = [], [], []
        fatal = False
        helpers = {0xa30c, 0xb1f8, 0xaa40, 0xaa74, 0xaaac, 0xaf54,
                   0xa780, 0xa714, 0xad84, 0xae68, 0xa188, 0x113e4,
                   0x169b0, 0x1c4d0, 0x1c5ac, 0x1e518, 0x1b594}
        def hook(uc, pc, size, data):
            global fatal
            args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if pc == 0x1c888:
                fatal = True
                uc.emu_stop()
                return
            if pc == 0x14758:
                events.append(args)
            elif pc == 0x50000100:
                notices.append(list(struct.unpack('<III', uc.mem_read(args[0], 12))))
                assert args[1] == 0x12345678
            elif pc in helpers:
                trace.append(hex(pc))
            else:
                return
            # Conservative fixture: predicates return zero; helper bodies do not run.
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, hook)
        u.reg_write(UC_ARM_REG_R0, app)
        u.reg_write(UC_ARM_REG_R1, int(normal))
        u.reg_write(UC_ARM_REG_R2, ctx)
        u.reg_write(UC_ARM_REG_SP, 0x60008000)
        u.reg_write(UC_ARM_REG_LR, 0x50000000)
        u.emu_start(0xb2f4, 0x50000000, count=20000)
        assert fatal == (not normal and state != 6)
        if not fatal:
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
            assert events == [[ctx + 0x4b88, 0, app]]
            assert notices == [[9, 3, app]]
            assert word(ctx + 0x5144) == (app if state == 6 else 0)
            assert word(ctx + 0x5148) == (99 if state == 6 else 0)
        else:
            assert not events and not notices
        if normal and state == 3:
            assert '0xb1f8' in trace and '0xaa40' in trace and '0xaa74' in trace
        rows.append({'state_value': state, 'normal_exit_flag': normal,
                     'fatal_path_reached': fatal, 'state_machine_deliveries': events,
                     'observer_packets': notices, 'mocked_helpers': trace})
report = {'scope': 'Original procExitCb instructions; helpers and state-machine delivery mocked',
          'sysmgrd_sha256': digest, 'procedure': '0xb2f4', 'cases': rows,
          'limits': ['State numbers are not assigned USB/sleep names by this test.',
                     'Normal exit is a dispatcher flag, not assumed to be child exit status zero.',
                     'Does not execute downstream state handlers, IPC, mounts or hardware restoration.',
                     'State 6 helper branches cover only zero-return predicate fixtures.']}
(ROOT / 'sources/native-manager-exit-dispatch.json').write_text(json.dumps(report, indent=2) + '\n')
print('14 dispatcher cases: normal exits deliver event 0; abnormal non-6 states reach original fatal path')
