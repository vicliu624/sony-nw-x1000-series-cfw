"""Original Spider callback registration and APF activation -> application events.

Callbacks and the APF op7 query roundtrip execute original ARM code. Battery
refresh, transport, argv, queue, locks and service helpers are fixtures.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
manager_raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
manager_hash = hashlib.sha256(manager_raw).hexdigest()
assert manager_hash == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
manager_elf = ELFFile(io.BytesIO(manager_raw))
expected = {0: 0xe68c, 1: 0xe884, 2: 0xf090, 3: 0xecb8, 4: 0xea18,
            5: 0xeaa0, 6: 0xeb9c, 7: 0xebec, 8: 0xec3c, 9: 0xef20, 10: 0xf004}
rows = []
for initial_state, query_value, argument in [(1, 0, None), (1, 2, None),
                                             (1, 0, 'stock-special-argument'), (2, 0, None)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    ctx = 0x820f68
    m = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    m.mem_map(0x8000, 0x40000)
    for segment in manager_elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            m.mem_write(segment['p_vaddr'], segment.data())
    m.mem_map(0x50000000, 4096)
    m.mem_map(0x60000000, 0x20000)
    manager_context, ipc = 0x60010000, 0x60001000
    for address, value in [(manager_context + 0x503c, 2), (ipc, manager_context), (ipc + 4, 44),
                            (manager_context + 0x41c8 + 20, query_value)]:
        m.mem_write(address, struct.pack('<I', value))
    query_replies, query_packets = [], []
    def manager_hook(uc, pc, size, data):
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x12034:
            assert a[0] == manager_context + 0x41c8
            # Battery-status refresh excluded; cached status fields supplied above.
        elif pc == 0x16d18:
            assert a[:2] == [44, 55] and a[3] == 24
            query_replies.append(bytes(uc.mem_read(a[2], 24)))
        else:
            return
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    m.hook_add(UC_HOOK_CODE, manager_hook)
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    def cstr(address):
        result = bytearray()
        while True:
            c = bytes(u.mem_read(address, 1))
            if c == b'\0':
                return bytes(result)
            result.extend(c)
            address += 1
    special = cstr(0x3e3c88)
    received, returned_to_receive = 0, False
    events, flag_requests = [], []
    def hook(uc, pc, size, data):
        global received, returned_to_receive
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x268c9c:
            assert a[:2] == [500, 55] and a[3] == 20
            packet = bytes(uc.mem_read(a[2], 20))
            assert struct.unpack('<5I', packet) == (20, 0, 1, 7, 55)
            query_packets.append(list(struct.unpack('<5I', packet)))
            m.mem_write(0x60003000, packet)
            for reg, value in [(UC_ARM_REG_R0, ipc), (UC_ARM_REG_R1, 0x60003000),
                               (UC_ARM_REG_SP, 0x60018000), (UC_ARM_REG_LR, 0x50000000)]:
                m.reg_write(reg, value)
            m.emu_start(0xfb1c, 0x50000000, count=10000)
            assert m.reg_read(UC_ARM_REG_PC) == 0x50000000
        elif pc == 0x268d48 and a[0] == 500:
            assert len(query_replies) == 1 and a[2] == 24
            uc.mem_write(a[1], query_replies[0])
            put(a[3], 24)
        elif pc == 0x268d48:
            if received:
                returned_to_receive = True
                uc.emu_stop()
                return
            uc.mem_write(a[1], struct.pack('<5I', 20, 0, 5, 0, 0))
            put(a[3], 20)
            received += 1
        elif pc == 0xb07e8:
            put(a[0], 0)
            put(a[0] + 4, 0x60002000 if argument else 0)
            if argument:
                uc.mem_write(0x60002000, special + b'\0')
        elif pc == 0xa57f0:
            events.append(a + [word(uc.reg_read(UC_ARM_REG_SP))])
        elif pc == 0xda0c:
            assert cstr(a[0]) == cstr(a[1]) == special
        elif pc == 0xe600:
            flag_requests.append(a[:2])
        elif pc not in (0x337a80, 0x337ae8, 0xe5ac, 0xb00bc, 0x33b918, 0x3b2b8):
            return
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    # Exact registration block: wrappers and APF slot setters are not mocked.
    u.reg_write(UC_ARM_REG_SP, 0x60018000)
    u.reg_write(UC_ARM_REG_R7, 0x60010000)
    u.emu_start(0xfcb4, 0xfd68, count=10000)
    for event, callback in expected.items():
        assert word(ctx + 0x2c + event * 4) == callback
        assert word(ctx + 0x58 + event * 4) == 0
    put(ctx + 4, initial_state)
    put(ctx + 0x24, 1)
    put(ctx + 0x1c, 501)
    put(ctx, 1)
    put(ctx + 0x10, 500)
    put(ctx + 0xc, 55)
    u.reg_write(UC_ARM_REG_R0, ctx)
    u.reg_write(UC_ARM_REG_SP, 0x60018000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0x26551c, 0x50000000, count=100000)
    assert returned_to_receive and received == 1
    if initial_state == 2:
        assert not events and not flag_requests and not query_packets
    else:
        assert events[0] == [0x420011, 0, query_value or 1, 0, 0]
        assert events[1] == [0x420036 if argument else 0x420023, 0, 0, 0, 0]
        assert len(events) == 2 and len(flag_requests) == 1 and flag_requests[0][1] == 1
        assert len(query_replies) == 1
        assert struct.unpack('<6I', query_replies[0]) == (24, 0, 7, 0, query_value, 0)
    rows.append({'initial_client_state': initial_state, 'query_fixture': query_value,
                 'argument': special.decode('ascii') if argument else None,
                 'query_requests': query_packets,
                 'query_replies': [list(struct.unpack('<6I', reply)) for reply in query_replies],
                 'application_events': events, 'returned_to_receive': returned_to_receive})
report = {'scope': 'Original Spider registration/activation and op7 battery-query roundtrip; hardware refresh/app-event delivery mocked',
          'SpiderApp_sha256': digest, 'sysmgrd_sha256': manager_hash,
          'callbacks': {str(k): hex(v) for k, v in expected.items()},
          'cases': rows,
          'query_operation': {'operation': 7, 'meaning': 'battery status',
                              'evidence': 'sysmgrd 0x12034 diagnostic apf_battStatus / unknown battery status'},
          'limits': ['Registered/inactive APF context, cached battery fields and argument payload are fixtures.',
                     'Original op7 request/reply helpers and manager getter execute; hardware refresh 0x12034 is intercepted.',
                     'Application events are captured before queue/state-machine/hardware consumers.',
                     'No display refresh, touch ownership, audio, USB, sleep or actual device restoration is proved.']}
(ROOT / 'sources/native-spider-reactivation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Eleven original callback slots and four activation/duplicate-filter cases verified')
