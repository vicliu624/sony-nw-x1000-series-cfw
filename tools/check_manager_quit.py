"""Replay stock op3 handler through expected-signal recording and reap classification.

Original table initialization instructions select the handler. IPC, registry,
kill and wait records are virtual. No real signal or device operation occurs.
"""
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
raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf = ELFFile(io.BytesIO(raw))
syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for state, record_flag in [(1, 0), (2, 0), (3, 0), (6, 0), (1, 1), (2, 2), (4, 0), (5, 0), (0, 0)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    ctx, ipc, request, record = 0x60010000, 0x60001000, 0x60003000, 0x60002000
    app, pid = 0x30001, 321
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    # Execute the actual straight-line dispatch-table initializer, excluding its services.
    u.emu_start(0xecc0, 0xee34, count=1000)
    handler = word(0x31868 + 3 * 4)
    assert handler == 0xf89c
    put(ctx + 0x503c, state)
    put(ipc, ctx)
    put(ipc + 4, 44)
    u.mem_write(request, struct.pack('<6I', 24, 55, 0, 3, 66, app))
    u.mem_write(record, struct.pack('<5I', 0, pid, app, record_flag, 0))
    put(ctx + 0x51bc, 0x50000200)
    put(ctx + 0x51c0, 0x1234)
    put(ctx + 0x41b0, 0x50000100)
    put(ctx + 0x41b4, ctx)
    put(ctx + 0x41c4, 1)
    put(ctx + 0x41c0, 77)
    put(0x327f8, 101)
    signal = word(0x2b910)
    assert 0 < signal < 32
    trace, replies, callbacks, notices = [], [], [], []
    fatal = False
    def hook(uc, pc, size, data):
        global fatal
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc == 0x1c888:
            fatal = True
            uc.emu_stop()
            return
        if pc == 0x110ac:
            result = 1
        elif pc == 0x14944:
            result = 0
        elif pc == 0x1493c:
            result = app
        elif pc == 0x16510:
            result = record
        elif pc == syms['kill']:
            assert args[:2] == [pid, signal]
            assert word(record + 16) == signal, 'Signal not recorded before kill'
            trace.append('signal-recorded-then-kill-requested')
        elif pc == 0x16d18:
            assert args[0] == 44 and args[1] == 66 and args[3] == 16
            replies.append(list(struct.unpack('<4I', uc.mem_read(args[2], 16))))
            trace.append('reply')
        elif pc == 0x50000200:
            notices.append(list(struct.unpack('<3I', uc.mem_read(args[0], 12))))
            assert args[1:3] == [app, 0x1234]
        elif pc == 0x19ef4:
            result = 1
        elif pc == syms['read']:
            assert args[0] == 101 and args[2] == 8
            uc.mem_write(args[1], struct.pack('<II', pid, signal))
            result = 8
        elif pc == 0x50000100:
            callbacks.append(args[:3])
            trace.append('normal-reap-callback')
        elif pc not in (0xa188, 0x1c4d0, 0x1c5ac, 0x1e518, 0x1b594, 0x16578, 0x163dc, 0x16b7c):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def call(pc, arg0, arg1=0, arg2=0):
        u.reg_write(UC_ARM_REG_R0, arg0)
        u.reg_write(UC_ARM_REG_R1, arg1)
        u.reg_write(UC_ARM_REG_R2, arg2)
        u.reg_write(UC_ARM_REG_SP, 0x60008000)
        u.reg_write(UC_ARM_REG_LR, 0x50000000)
        u.emu_start(pc, 0x50000000, count=30000)
        if not fatal:
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    # Original parent-launch code calls this constructor at 0x111b8.
    instruction = word(0x111b8)
    displacement = instruction & 0xffffff
    if displacement & 0x800000:
        displacement -= 0x1000000
    assert instruction >> 24 == 0xeb and 0x111c0 + displacement * 4 == 0x165fc
    call(0x165fc, record, pid, app)
    assert list(struct.unpack('<5I', u.mem_read(record + 4, 20))) == [pid, app, 0, 0, 0]
    if record_flag == 2:
        # Activation op1 value2 goes through this core function and real setter.
        call(0xc86c, ctx, app, 2)
        assert word(record + 12) == 2
    else:
        # Value1 remains an explicit branch fixture, not the launch default.
        put(record + 12, record_flag)
    call(handler, ipc, request)
    assert fatal == (state == 0)
    if state in (4, 5):
        assert replies == [[16, 55, 3, 0x1d03]] and trace == ['reply']
    elif state == 0:
        assert not replies
    elif record_flag:
        assert notices == [[4, 0, 0]] and trace == ['reply']
        assert replies == [[16, 55, 3, 0]]
    else:
        assert replies == [[16, 55, 3, 0]] and not notices
        call(0x11998, ctx)
        assert callbacks == [[app, 1, ctx]]
        assert trace == ['signal-recorded-then-kill-requested', 'reply', 'normal-reap-callback']
    rows.append({'state_value': state, 'registry_field12': record_flag, 'fatal': fatal,
                 'original_stop_signal': signal, 'trace': trace, 'replies': replies,
                 'observer_packets': notices, 'reaper_callbacks': callbacks})
report = {'scope': 'Original op3 table/handler/core/stop helper/reaper instructions; virtual services',
          'sysmgrd_sha256': digest, 'record_constructor': '0x165fc',
          'parent_launch_constructor_call': '0x111b8', 'cases': rows,
          'limits': ['No real IPC, kill, waitpid, scheduling or device ran.',
                     'Reap record is injected after handler reply; real scheduling order is not proved.',
                     'Registry field12 nonzero observer path is not named or fully delivered.',
                     'Full receive-loop validation and downstream RUN/USB/sleep handlers are not combined here.']}
(ROOT / 'sources/native-manager-quit.json').write_text(json.dumps(report, indent=2) + '\n')
print('Nine op3 cases; activated value2 takes observer path, zero records use expected-signal termination')
