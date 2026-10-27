"""Original completion-event dispatch and bounded native APF activation ack.

Mode/state fixtures do not establish the real current mode. IPC/locks/logging
are virtual; there are no real Sony processes or hardware operations.
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
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
def machine():
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    return u
def word(u, address):
    return struct.unpack('<I', u.mem_read(address, 4))[0]
def put(u, address, value):
    u.mem_write(address, struct.pack('<I', value))
def returned(u, value=0):
    u.reg_write(UC_ARM_REG_R0, value)
    u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
def call(u, address, values):
    for r, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), values):
        u.reg_write(r, value)
    u.reg_write(UC_ARM_REG_SP, 0x60018000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    try:
        u.emu_start(address, 0x50000000, count=100000)
    except Exception as exc:
        raise AssertionError(f'Unmodeled execution at {u.reg_read(UC_ARM_REG_PC):#x}, lr={u.reg_read(UC_ARM_REG_LR):#x}') from exc
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    return u.reg_read(UC_ARM_REG_R0)

u = machine()
actions = set()
for descriptor in (0x3ef68c, 0x3ef780, 0x3ef8d4):
    count = struct.unpack('<H', u.mem_read(descriptor + 4, 2))[0]
    actions.update(word(u, word(u, descriptor + 12) + i * 4) for i in range(count))
hits = []
def selection_hook(uc, pc, size, data):
    if pc in actions:
        hits.append(pc)
        returned(uc)
u.hook_add(UC_HOOK_CODE, selection_hook)
dispatches = []
for mode, states in ((1, 1), (2, 2), (3, 7)):
    for state in range(1, states + 1):
        context = bytearray(32)
        context[0], context[1], context[13] = mode, state, 6
        struct.pack_into('<I', context, 4, 0x3ef680)
        u.mem_write(0x60010000, bytes(context))
        hits.clear()
        expected = (0x61414 if state == 1 else 0x614b0) if mode == 2 else 0x613cc
        assert call(u, 0x17c608, (0x60010000, 0x410009, 0, 0)) == 0
        assert hits == [expected]
        dispatches.append({'mode_fixture': mode, 'state_fixture': state, 'action': hex(expected)})

acks = []
for reply_status in (0, 0x1d04):
    u = machine()
    ctx = 0x820f68
    for offset, value in [(0, 1), (4, 1), (12, 55), (16, 500)]:
        put(u, ctx + offset, value)
    packets, trace = [], []
    def ack_hook(uc, pc, size, data):
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x268c9c:
            assert a[:2] == [500, 55] and a[3] == 24
            packet = list(struct.unpack('<6I', uc.mem_read(a[2], 24)))
            assert packet == [24, 0, 1, 1, 55, 2]
            packets.append(packet)
            trace.append('activation-op1-value2')
        elif pc == 0x268d48:
            assert a[0] == 500 and a[2] == 16
            uc.mem_write(a[1], struct.pack('<4I', 16, 0, 1, reply_status))
            put(uc, a[3], 16)
            trace.append('reply')
        elif pc not in (0x337a80, 0x337ae8, 0xb00bc, 0x265298, 0x33b918, 0x33b83c):
            return
        returned(uc)
    u.hook_add(UC_HOOK_CODE, ack_hook)
    result = call(u, 0x614b0, (0, 0x410009, 0, 0))
    assert result == 0x304 and len(packets) == 1
    assert word(u, ctx + 4) == (2 if reply_status == 0 else 1)
    acks.append({'reply_status': reply_status, 'requests': packets, 'handler_return': hex(result),
                 'client_state': word(u, ctx + 4), 'trace': trace})
u = machine()
ctx, main_context = 0x820f68, 0x60010000
for offset, value in [(0, 1), (4, 2), (12, 55), (16, 500)]:
    put(u, ctx + offset, value)
context = bytearray(32)
context[0], context[1], context[13] = 3, 4, 6
struct.pack_into('<I', context, 4, 0x3ef680)
u.mem_write(main_context, bytes(context))
cycle_packets, cycle_states = [], []
def cycle_hook(uc, pc, size, data):
    a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
    if pc == 0x268c9c:
        packet = list(struct.unpack('<6I', uc.mem_read(a[2], 24)))
        sequence = len(cycle_packets)
        assert a[:2] == [500, 55] and a[3] == 24
        assert packet == [24, sequence, 1, 1, 55, (1, 2)[sequence]]
        cycle_packets.append(packet)
    elif pc == 0x268d48:
        assert a[0] == 500 and a[2] == 16
        uc.mem_write(a[1], struct.pack('<4I', 16, len(cycle_packets) - 1, 1, 0))
        put(uc, a[3], 16)
    elif pc not in (0x337a80, 0x337ae8, 0xb00bc, 0x265298, 0x17c42c, 0x33b918, 0x33b83c):
        return
    returned(uc)
u.hook_add(UC_HOOK_CODE, cycle_hook)
for event, expected_mode, expected_state, expected_client in [(0x41000a, 2, 2, 1), (0x410009, 3, 4, 2)]:
    assert call(u, 0x17c608, (main_context, event, 0, 0)) == 0
    mode, state = bytes(u.mem_read(main_context, 2))
    assert (mode, state, word(u, ctx + 4)) == (expected_mode, expected_state, expected_client)
    cycle_states.append({'event': hex(event), 'mode': mode, 'state': state,
                         'client_state': word(u, ctx + 4)})
report = {'scope': 'Original main completion selection, standalone ack and bounded completion-cycle instructions',
          'SpiderApp_sha256': digest, 'descriptor_table': '0x3ef680',
          'dispatch_cases': dispatches, 'ack_cases': acks,
          'completion_cycle': {'initial_fixture': {'mode': 3, 'state': 4, 'client_state': 2},
                               'requests': cycle_packets, 'states': cycle_states},
          'limits': ['Mode/state contexts are fixtures; actual Home departure/return transitions are not combined.',
                     'Action selection intercepts bodies; standalone ack does not execute subsequent state transitions.',
                     'Completion cycle executes native state transitions, but injects completion events with successful virtual replies; departure/activation notification and subsystem work are not combined.',
                     'Manager reply is virtual. Failure still returns 0x304; do not equate that value with accepted activation.',
                     'No display/touch reacquisition or real IPC/scheduling is proved.']}
(ROOT / 'sources/native-main-activation-ack.json').write_text(json.dumps(report, indent=2) + '\n')
print('Ten dispatches, two ack outcomes and original main/APF completion-state roundtrip verified')
