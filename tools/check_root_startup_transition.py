"""Execute stock constructor, completion barrier and Root mode transition."""
from pathlib import Path
import contextlib, hashlib, io, json, runpy, struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_PC, UC_ARM_REG_LR
if not __debug__: raise RuntimeError('Run without Python optimization')
ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'tools/check_spider_restore_dispatch.py'
with contextlib.redirect_stdout(io.StringIO()): model = runpy.run_path(str(base))
call = model['call']; g = call.__globals__; u = g['u']
g['intercept_actions'] = False
g['deactivate_probe'] = False
admit, condition = 1, 1
services = []
upstream_probe = False
def boundary(uc, pc, size, data):
    if upstream_probe and pc in (0xac9ec, 0xad270, 0x17acc, 0x181f8,
                                 0x38404, 0x4aaa8, 0xae634, 0xaeb4c, 0x50000100,
                                 0x11a04, 0xb13fc, 0xff5c):
        services.append({'pc': hex(pc), 'mocked_upstream_service': True})
        if pc == 0x181f8:
            uc.mem_write(uc.reg_read(UC_ARM_REG_R1), bytes(4))
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        return
    if pc in (0x104c4, 0xf674, 0xe600):
        services.append({'pc': hex(pc), 'r0': uc.reg_read(UC_ARM_REG_R0),
                         'r1': uc.reg_read(UC_ARM_REG_R1), 'original_body_executed': True})
        return
    if pc not in (0x17c42c, 0x33b918): return
    services.append({'pc': hex(pc), 'r0': uc.reg_read(UC_ARM_REG_R0),
                     'r1': uc.reg_read(UC_ARM_REG_R1)})
    uc.reg_write(UC_ARM_REG_R0, 0)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
handle = u.hook_add(UC_HOOK_CODE, boundary)
rows = []
for admit in (0, 1):
    condition = 1
    assert call(0x714c4, (0, 0, 0, 0)) == 0
    before = bytes(u.mem_read(0x6833dc, 32))
    completion = [0, 1, 1, 1, 1, admit]
    u.mem_write(0x613e60 + 0x4c, struct.pack('<6I', *completion))
    u.mem_write(0x613e2c + 4, struct.pack('<I', condition))
    u.mem_write(0x613e2c + 24, struct.pack('<I', 0))
    services.clear(); g['queued'].clear()
    assert call(0x17c608, (0x6833dc, 0x420102, 0, 0)) == 0
    after = bytes(u.mem_read(0x6833dc, 32))
    assert list(after[:2]) == ([2, 1] if admit else [1, 1])
    assert g['queued'] == ([[0x42001a, 0, 0, 0]] if admit else [])
    assert after[13] == 5
    completion_after = list(struct.unpack('<6I', u.mem_read(0x613e60 + 0x4c, 24)))
    assert completion_after == [1, 1, 1, 1, 1, admit]
    assert struct.unpack('<I', u.mem_read(0x613e2c + 24, 4))[0] == admit
    rows.append({'completion_slots_before_fixture': completion,
                 'completion_slots_after': completion_after,
                 'state_field_plus4_fixture': condition,
                 'before_mode_state': list(before[:2]),
                 'after_mode_state': list(after[:2]),
                 'service_boundaries': services.copy(),
                 'queued': [e.copy() for e in g['queued']]})
sequences = []
for order in ([0, 1, 2, 3, 4, 5], [5, 4, 3, 2, 1, 0], [0, 0, 1, 2, 3, 4, 5]):
    assert call(0x714c4, (0, 0, 0, 0)) == 0
    u.mem_write(0x613e60 + 0x4c, bytes(24))
    u.mem_write(0x613e2c + 4, struct.pack('<I', 1))
    u.mem_write(0x613e2c + 24, bytes(4))
    seen = set(); steps = []
    for slot in order:
        g['queued'].clear(); services.clear()
        assert call(0x17c608, (0x6833dc, 0x420102, slot, 0)) == 0
        seen.add(slot)
        slots = list(struct.unpack('<6I', u.mem_read(0x613e60 + 0x4c, 24)))
        assert slots == [int(i in seen) for i in range(6)]
        state = list(u.mem_read(0x6833dc, 2))
        assert state == ([2, 1] if len(seen) == 6 else [1, 1])
        assert g['queued'] == ([[0x42001a, 0, 0, 0]] if len(seen) == 6 else [])
        steps.append({'notification_slot': slot, 'completion_slots': slots,
                      'mode_state': state, 'queued': [e.copy() for e in g['queued']]})
    sequences.append({'order': order, 'steps': steps})
producer_cases = []
for signals in ([0], [1], [0, 1], [1, 0]):
    producer = 0x60015000
    u.mem_write(producer, bytes(0x54))
    assert call(0x714c4, (0, 0, 0, 0)) == 0
    u.mem_write(0x613e60 + 0x4c, bytes(24))
    u.mem_write(0x613e2c + 4, struct.pack('<I', 1))
    # The other five notifications are harness-delivered; slot4 must come
    # from the stock producer, never from a synthetic success packet.
    for slot in (0, 1, 2, 3, 5):
        assert call(0x17c608, (0x6833dc, 0x420102, slot, 0)) == 0
    g['queued'].clear()
    for signal in signals:
        call(0x177f8, (producer, signal, 0, 0))
    packets = [e.copy() for e in g['queued']]
    expected = [[0x420102, 0, 4, 0]] if len(signals) == 2 else []
    assert packets == expected
    for packet in packets:
        g['queued'].clear()
        assert call(0x17c608, (0x6833dc, packet[0], packet[2], packet[3])) == 0
        assert g['queued'] == [[0x42001a, 0, 0, 0]]
    final = list(u.mem_read(0x6833dc, 2))
    assert final == ([2, 1] if packets else [1, 1])
    producer_cases.append({'producer_entry': '0x177f8', 'signals': signals,
                           'packets': packets, 'root_after_delivery': final,
                           'other_five_notifications_harness_delivered': True})
upstream_probe = True
upstream_cases = []
for order in ([0x68df0, 0x6a6bc], [0x6a6bc, 0x68df0]):
    assert call(0x714c4, (0, 0, 0, 0)) == 0
    u.mem_write(0x613e60 + 0x4c, bytes(24))
    u.mem_write(0x613e2c + 4, struct.pack('<I', 1))
    u.mem_write(0x619ef8 + 0x4c, bytes(8))
    for slot in (0, 1, 2):
        assert call(0x17c608, (0x6833dc, 0x420102, slot, 0)) == 0
    g['queued'].clear(); services.clear()
    call(0xffb0, (0, 0, 0, 0))
    slot3_packets = [e.copy() for e in g['queued']]
    slot3_notifications = [e for e in slot3_packets if e[0] == 0x420102]
    assert slot3_notifications == [[0x420102, 0, 3, 0]]
    g['queued'].clear()
    slot3 = slot3_notifications[0]
    assert call(0x17c608, (0x6833dc, slot3[0], slot3[2], slot3[3])) == 0
    assert list(u.mem_read(0x6833dc, 2)) == [1, 1]
    assert g['queued'] == []
    slot3_mocked = [s.copy() for s in services if s.get('mocked_upstream_service')]
    obj = bytearray(32)
    struct.pack_into('<I', obj, 0, 0x50000100)
    struct.pack_into('<I', obj, 20, 0x60016100)
    u.mem_write(0x60016000, bytes(obj))
    u.mem_write(0x60016100, struct.pack('<I', 1))
    g['queued'].clear(); services.clear()
    for entry in order:
        assert call(entry, (0, 0, 0x60016000, 0)) == 3
    packets = [e.copy() for e in g['queued']]
    assert packets == [[0x420102, 0, 4, 0]]
    assert list(struct.unpack('<2I', u.mem_read(0x619ef8 + 0x4c, 8))) == [1, 1]
    g['queued'].clear()
    assert call(0x17c608, (0x6833dc, packets[0][0], packets[0][2], 0)) == 0
    assert list(u.mem_read(0x6833dc, 2)) == [1, 1]
    assert g['queued'] == []
    assert call(0x13ec0, (0, 0, 0, 0)) == 0
    slot5_packets = [e.copy() for e in g['queued']]
    assert slot5_packets == [[0x20671, 0, 0, 0], [0x420102, 0, 5, 0]]
    g['queued'].clear()
    notification = slot5_packets[1]
    assert call(0x17c608, (0x6833dc, notification[0], notification[2], 0)) == 0
    assert list(u.mem_read(0x6833dc, 2)) == [2, 1]
    assert g['queued'] == [[0x42001a, 0, 0, 0]]
    mocked = slot3_mocked + [s.copy() for s in services if s.get('mocked_upstream_service')]
    # Keep the constructor's actual context. Do not replace it with a2/1
    # fixture between startup, deactivation and reactivation.
    root_before_stop = bytes(u.mem_read(0x6833dc, 32))
    g['queued'].clear()
    assert call(0x17c608, (0x6833dc, 0x420024, 0, 0)) == 0
    stop_packets = [e.copy() for e in g['queued']]
    assert stop_packets == [[0x430113, 0, 6, 0]]
    root_after_stop = bytes(u.mem_read(0x6833dc, 32))
    assert root_after_stop == root_before_stop
    g['queued'].clear()
    assert call(0x17c608, (0x6833dc, 0x420011, 1, 0)) == 0
    forwarding_packets = [e.copy() for e in g['queued']]
    assert forwarding_packets == [[0x20303, 0, 1, 0], [0x580101, 0, 1, 0]]
    g['deactivate_probe'] = True
    g['deactivate_commands'].clear()
    assert call(0x17c608, (0x6833dc, 0x420023, 0, 0)) == 0
    resume_commands = [e.copy() for e in g['deactivate_commands']]
    assert resume_commands == [[0x613e60, 7]]
    assert bytes(u.mem_read(0x6833dc, 32)) == root_before_stop
    g['deactivate_probe'] = False
    upstream_cases.append({'handler_order': [hex(e) for e in order],
                           'packets': packets, 'root_after_delivery': [2, 1],
                           'root_after_slot4': [1, 1],
                           'slot5_producer': '0x13ec0', 'slot5_packets': slot5_packets,
                           'slot3_producer': '0xffb0', 'slot3_packets': slot3_packets,
                           'slot3_unconsumed_packets': [e for e in slot3_packets if e[0] != 0x420102],
                           'unconsumed_event': '0x20671',
                           'other_three_notifications_harness_delivered': True,
                           'same_root_context_stop_resume': {
                               'address': '0x6833dc', 'root_context_hex': root_before_stop.hex(),
                               'context_rebuilt_between_phases': False,
                               'stop_packets': stop_packets,
                               'activation_forwarding_packets': forwarding_packets,
                               'resume_coordinator_calls': resume_commands,
                               'coordinator_intercepted': True,
                               'startup42001a_and_stop430113_unconsumed': True},
                           'mocked_services': mocked})
u.hook_del(handle)
inputs = [Path(__file__), base, ROOT/'work/targets-jp/SpiderApp']
report = {'all_bounded_checks_passed': True, 'event': '0x420102',
          'constructor': '0x714c4', 'dispatcher': '0x17c608',
          'action': '0x71724', 'cases': rows, 'zero_initialized_sequences': sequences,
          'native_slot4_producer_cases': producer_cases,
          'native_slot4_upstream_handler_cases': upstream_cases,
          'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
          'limits': ['Slot4 handlers68df0/6a6bc invoke original1542c/177f8; resource helpers and object callback mocked.',
                     'Slot3 producerffb0 executes with input0 and b13fc/ff5c mocked; its other events left unconsumed.',
                     'Slot5 producer13ec0 executes with thread-registration11a04 mocked;20671 left unconsumed.',
                     'Handler scheduling and other event producers/timing not connected.',
                     'Two branch cases prefill completion slots; three sequences start slots at zero and deliver notifications.',
                     'State field+4 supplied; zero state-field branches not executed.',
                     '104c4/f674/e5f4/e600 original bodies execute, diagnostic getter17c42c and logger33b918 mocked.',
                     'Queue captured, not consumed.',
                     'Same initialized Root continues through420024/420011/420023; events supplied, coordinator7 intercepted.',
                     'No full startup, real IPC, device execution or hardware qualification.']}
(ROOT/'sources/native-root-startup-transition.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original barrier: two branches, three sequences, four producer cases and two upstream handler orders passed')
