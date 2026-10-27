"""Bounded stock slot6/Root dispatch; does not derive the initial Root state."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR

if not __debug__:
    raise RuntimeError('Run without Python optimization')
ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(base))
call = model['call']
g = call.__globals__
u = g['u']
g['intercept_actions'] = False
g['deactivate_probe'] = True

def logger_stub(uc, pc, size, data):
    if pc in (0xe5ac, 0x33b918):
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

handle = u.hook_add(UC_HOOK_CODE, logger_stub)
# Original constructor, not a synthesized context. Its entry callbacks are null
# for the observed initial branch; interception remains disabled throughout.
assert call(0x714c4, (0, 0, 0, 0)) == 0
root_pointer = struct.unpack('<I', u.mem_read(0x6833d8, 4))[0]
assert root_pointer == 0x6833dc
initialized = bytes(u.mem_read(root_pointer, 32))
assert initialized[:3] == bytes((1, 1, 2))
assert initialized[13] == 5
assert struct.unpack_from('<I', initialized, 4)[0] == 0x3f4f18
assert call(0x71488, (root_pointer, 0, 0, 0)) == 0
reset_context = bytes(u.mem_read(root_pointer, 32))
assert reset_context == initialized
g['queued'].clear()
call(0xeb9c, (0, 0, 0, 0))
assert g['queued'] == [[0x420024, 0, 0, 0]]
callback_packet = g['queued'][0].copy()
rows = []
for state in range(1, 6):
    context = bytearray(32)
    context[0], context[1], context[13] = 2, state, 10
    struct.pack_into('<I', context, 4, 0x3f4f18)
    u.mem_write(0x60010000, bytes(context))
    u.mem_write(0x613e64, struct.pack('<I', 0))
    g['queued'].clear()
    assert call(0x17c608, (0x60010000, callback_packet[0], 0, 0)) == 0
    after = bytes(u.mem_read(0x60010000, 32))
    expected = [[0x430113, 0, 6, 0]] if state in (1, 3, 4) else []
    assert g['queued'] == expected
    assert after[:2] == context[:2], (state, list(after))
    changed = [i for i, (a, b) in enumerate(zip(context, after)) if a != b]
    command = struct.unpack('<I', u.mem_read(0x613e64, 4))[0]
    assert command == (6 if expected else 0)
    rows.append({'initial_mode_state_fixture': [2, state],
                 'final_mode_state': list(after[:2]),
                 'mode_state_unchanged': True,
                 'changed_context_byte_offsets': changed,
                 'context_after_hex': after.hex(),
                 'queued': [p.copy() for p in g['queued']],
                 'coordinator_command': command})
u.hook_del(handle)
inputs = [Path(__file__), base, ROOT / 'work/targets-jp/SpiderApp']
report = {
    'all_bounded_checks_passed': True,
    'scope': 'Original slot6 callback and Root dispatcher/action instructions only',
    'callback': '0xeb9c', 'callback_packet': callback_packet,
    'original_constructor': {'entry': '0x714c4', 'root_pointer': hex(root_pointer),
                             'initial_mode_state': list(initialized[:2]),
                             'context_hex': initialized.hex(),
                             'reset_entry': '0x71488',
                             'reset_matches_constructor': True},
    'root_descriptor': '0x3f4f18', 'cases': rows,
    'root_2_1_derived_from_deactivation': False,
    'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    'limits': ['Constructor/reset execute, but the full startup and transition to mode2 do not.',
               'Deactivation matrix initial mode/state supplied, not derived from constructor.',
               'Logger mocked; queue captured, no real scheduling or IPC.',
               '430113 is not delivered here; Main and Root are separate state machines.',
               'No firmware package, device execution or hardware qualification.']}
(ROOT / 'sources/native-root-deactivation-state.json').write_text(json.dumps(report, indent=2) + '\n')
print('Stock Root constructor/reset produce1/1; slot6 and five mode2 branches passed without deriving2/1')
