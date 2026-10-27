"""Trace stock root-state activation events and bounded forwarding handlers.

Mode/state contexts are fixtures. Action selection executes stock instructions;
selected actions are intercepted, then four forwarding bodies run separately.
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
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
u.mem_map(0x8000, 0x900000)
for segment in elf.iter_segments():
    if segment['p_type'] == 'PT_LOAD':
        u.mem_write(segment['p_vaddr'], segment.data())
u.mem_map(0x50000000, 4096)
u.mem_map(0x60000000, 0x20000)
def word(address):
    return struct.unpack('<I', u.mem_read(address, 4))[0]
handlers = set()
for index, descriptor in enumerate((0x3f4f20, 0x3f5198)):
    assert word(0x3f4f18 + index * 4) == descriptor
    count = struct.unpack('<H', u.mem_read(descriptor + 4, 2))[0]
    handlers.update(word(word(descriptor + 12) + i * 4) for i in range(count))
gui_descriptor = 0x3ea1dc
gui_count = struct.unpack('<H', u.mem_read(gui_descriptor + 4, 2))[0]
handlers.update(word(word(gui_descriptor + 12) + i * 4) for i in range(gui_count))
hits, queued, gui_calls = [], [], []
intercept_actions = True
gui_effects = False
deactivate_probe = False
deactivate_commands = []
deactivate_gate = 0
deactivate_busy = 0
def hook(uc, pc, size, data):
    if deactivate_probe and pc == 0x112fc:
        deactivate_commands.append([uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)])
        u.mem_write(uc.reg_read(UC_ARM_REG_R2), struct.pack('<I', 0))
    elif deactivate_probe and pc in (0xf680, 0x10dec, 0xe5f4):
        value = deactivate_gate if pc == 0xf680 else deactivate_busy if pc == 0x10dec else 0
        uc.reg_write(UC_ARM_REG_R0, value)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        return
    elif intercept_actions and pc in handlers:
        hits.append(pc)
    elif pc == 0xa57f0:
        queued.append([uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)])
    elif gui_effects and pc in (0x141e0, 0x29010):
        gui_calls.append((pc, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))
    else:
        return
    uc.reg_write(UC_ARM_REG_R0, 0)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE, hook)
def call(pc, values):
    for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), values):
        u.reg_write(reg, value)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(pc, 0x50000000, count=20000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    return u.reg_read(UC_ARM_REG_R0)
rows = []
for mode, states in ((1, 3), (2, 5)):
    for state in range(1, states + 1):
        for event in (0x420011, 0x420023, 0x420036, 0x420015, 0x420024):
            if event == 0x420024:
                expected = 0x71ce8 if mode == 2 and state in (1,3,4) else 0x71570
            elif event == 0x420015:
                expected = (0x718c0 if state == 1 else 0x71570) if mode == 1 else (0x71570 if state == 2 else 0x71a3c)
            elif mode == 1:
                expected = (0x715b4, 0x7160c, 0x71664)[state - 1] if event == 0x420011 else 0x71570
            elif event == 0x420011:
                expected = 0x718f0
            elif event == 0x420023:
                expected = 0x71570 if state == 2 else 0x71cb8
            else:
                expected = 0x71570 if state in (2, 5) else 0x722c0
            context = bytearray(32)
            context[0], context[1], context[13] = mode, state, 10
            struct.pack_into('<I', context, 4, 0x3f4f18)
            u.mem_write(0x60010000, bytes(context))
            hits.clear()
            assert call(0x17c608, (0x60010000, event, 7, 0)) == 0
            assert hits == [expected]
            rows.append({'mode': mode, 'state': state, 'event': hex(event), 'action': hex(expected)})
gui_rows = []
for state in range(1, 40):
    context = bytearray(32)
    context[0], context[1], context[13] = 1, state, 10
    struct.pack_into('<I', context, 4, 0x3ea150)
    u.mem_write(0x60010000, bytes(context))
    hits.clear()
    expected = {2: 0x5c748, 3: 0x5d140, 38: 0x550b0, 39: 0x5d2dc}.get(state, 0x55340)
    assert call(0x17c608, (0x60010000, 0x20303, 7, 0)) == 0
    assert hits == [expected]
    gui_rows.append({'state': state, 'event': '0x20303', 'action': hex(expected)})
intercept_actions = False
forwarding = []
for action, expected_return in ((0x715b4, 1), (0x7160c, 2), (0x71664, 3), (0x718f0, 0)):
    queued.clear()
    assert call(action, (0x60010000, 0x420011, 7, 0)) == expected_return
    assert queued == [[0x20303, 0, 7, 0], [0x580101, 0, 7, 0]], queued
    forwarding.append({'action': hex(action), 'return': expected_return,
                       'queued': [q.copy() for q in queued]})
gui_effects = True
gui_effect_rows = []
for previous in (0, 5, 6):
    for incoming in (1, 6):
        for flag in (0, 1):
            u.mem_write(0x613f00 + 8, struct.pack('<I', 0x60012000))
            u.mem_write(0x613f00 + 0x56d8, struct.pack('<I', previous))
            u.mem_write(0x60012004, struct.pack('<I', flag))
            gui_calls.clear()
            assert call(0x55340, (0x60010000, 0x20303, incoming, 0)) == 0
            assert word(0x613f00 + 0x56d8) == incoming
            reset_calls = [c for c in gui_calls if c[0] == 0x141e0]
            bridge_calls = [c for c in gui_calls if c[0] == 0x29010]
            assert len(reset_calls) == int(previous <= 5 and incoming > 5)
            assert bridge_calls == ([(0x29010, 0x60012000, incoming)] if flag else [])
            gui_effect_rows.append({'previous': previous, 'incoming': incoming,
                                    'object_flag4': flag, 'reset_requested': bool(reset_calls),
                                    'bridge_requested': bool(bridge_calls)})
gui_effects = False
deactivate_probe = True
deactivate_rows = []
for action, deactivate_gate, deactivate_busy in ((0x718c0,0,0),(0x71a3c,0,0),(0x71a3c,1,1),(0x71a3c,1,0)):
    deactivate_commands.clear()
    queued.clear()
    assert call(action, (0x60010000,0x420015,0,0)) == 0
    deferred = action == 0x71a3c and deactivate_gate == 1 and deactivate_busy == 0
    assert deactivate_commands == ([] if deferred else [[0x613e60,3]])
    assert queued == ([[0x430113,0,3,0]] if deferred else [])
    deactivate_rows.append({'action':hex(action),'gate_fixture':deactivate_gate,'busy_fixture':deactivate_busy,'coordinator_commands':deactivate_commands.copy(),'queued':queued.copy()})
queued.clear()
assert call(0x71ce8,(0x60010000,0x420024,0,0)) == 0
assert word(0x613e60+4)==6 and queued==[[0x430113,0,6,0]]
intercept_actions = True
consume_routes = []
for state in range(1,40):
    context = bytearray(32)
    context[0],context[1],context[13] = 1,state,10
    struct.pack_into('<I',context,4,0x3ea150)
    u.mem_write(0x60010000,bytes(context));hits.clear()
    expected = 0x55024 if state <= 4 else 0x550b0 if state in (9,38) else 0x5d2dc if state == 39 else 0x57d50
    assert call(0x17c608,(0x60010000,0x20111,0,0)) == 0 and hits == [expected]
    consume_routes.append({'state_fixture':state,'action':hex(expected),'classification':'fatal-handler-selected-not-executed' if state <= 4 else 'cleanup-action' if expected == 0x57d50 else 'noop'})
report = {'scope': 'Original root state dispatcher plus bounded forwarding bodies; no queue consumers/hardware',
          'SpiderApp_sha256': digest, 'descriptor_table': '0x3f4f18',
          'dispatch_cases': rows, 'forwarding_cases': forwarding,
          'gui_dispatch_cases': gui_rows, 'gui_effect_cases': gui_effect_rows,
          'deactivation_action_cases': deactivate_rows,
          'slot6_action': {'action':'0x71ce8','context_command_after':6,'queued':queued.copy()},
          'gui_command6_consumer_routes': consume_routes,
          'limits': ['Mode/state contexts are fixtures, not a complete root startup or named power states.',
                     'Action selection uses intercepted action returns; separate forwarding tests do not prove full state transitions.',
                     'GUI actions selected in 39 fixtures are intercepted; default 0x55340 effects separately cover 12 service-mocked cases.',
                     'GUI service bridges and 0x71cb8 command path do not execute their real services.',
                     '420015 deactivation routes added;718c0/71a3c bodies execute with command coordinator and gate/busy helper responses mocked. Deferred430113 event not consumed here.',
                     'No display, touch, audio, USB or physical player restoration is qualified.']}
(ROOT / 'sources/native-spider-restore-dispatch.json').write_text(json.dumps(report, indent=2) + '\n')
print('40 root + 39 GUI dispatches, slot4 command3 and slot6 queued command6 distinguished; bounded effects verified')
