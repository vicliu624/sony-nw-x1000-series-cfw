"""Stock observer queue -> event packet -> proxy dispatch/finalizer replay.

Virtual locks/queue/transport and cooperative scheduling only.
The child is already reaped; no real processes, signals or hardware run.
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
def machine(name, expected):
    raw = (ROOT / 'work/targets-jp' / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    elf = ELFFile(io.BytesIO(raw))
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x30000)
    return u, {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def put(u, address, value):
    u.mem_write(address, struct.pack('<I', value))
def word(u, address):
    return struct.unpack('<I', u.mem_read(address, 4))[0]
def args(u):
    return [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
def returned(u, result=0):
    u.reg_write(UC_ARM_REG_R0, result)
    u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
def call(u, pc, stack, a=0, b=0, c=0):
    for reg, value in [(UC_ARM_REG_R0, a), (UC_ARM_REG_R1, b), (UC_ARM_REG_R2, c),
                       (UC_ARM_REG_SP, stack), (UC_ARM_REG_LR, 0x50000000)]:
        u.reg_write(reg, value)
    u.emu_start(pc, 0x50000000, count=100000)

mgr_hash = '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
proxy_hash = '57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
m, _ = machine('sysmgrd', mgr_hash)
app, ipc = 0x30001, 0x60010000
put(m, ipc + 0x1b0, 77)
put(m, ipc + 4, 44)
m.mem_write(0x60001000, struct.pack('<3I', 4, 0, 0))
queue, events, lookups, ports = [], [], [], []
expected_ports = [501]
def manager_hook(uc, pc, size, data):
    a = args(uc)
    if pc == 0x1967c:
        assert a[0] == 77 and a[2:] == [52, 0]
        queue.append(bytes(uc.mem_read(a[1], 52)))
    elif pc == 0x1978c:
        if not queue:
            uc.emu_stop()
            return
        uc.mem_write(a[1], queue.pop(0))
    elif pc == 0x16498:
        assert a[0] == ipc + 8
        lookups.append(None if a[1] == 0 else word(uc, a[2]))
        return  # Execute the real linked-list traversal and predicate.
    elif pc == 0x16d18:
        assert a[0] == 44 and a[1] in expected_ports and a[3] == 20
        ports.append(a[1])
        events.append(bytes(uc.mem_read(a[2], 20)))
    elif pc not in (0x1a458, 0x1a4f0, 0x1a508, 0x16b7c):
        return
    returned(uc)
m.hook_add(UC_HOOK_CODE, manager_hook)
call(m, 0x162b4, 0x60008000, ipc + 8)
for record, owner, port in [(0x60002000, 0x30002, 502),
                             (0x60002040, app, 501), (0x60002080, 0x30003, 503)]:
    # Original constructor puts owner at +4 and event port at +8.
    call(m, 0x1679c, 0x60008000, record, port, owner)
    call(m, 0x1633c, 0x60008000, ipc + 8, record)
    assert m.reg_read(UC_ARM_REG_R0) == 0
call(m, 0xf314, 0x60008000, 0x60001000, app, ipc)
assert len(queue) == 1 and struct.unpack('<5I', queue[0][:20]) == (app, 0, 4, 0, 0)
call(m, 0xf0fc, 0x60008000, ipc)
assert lookups == [app] and len(events) == 1
assert struct.unpack('<5I', events[0]) == (20, 0, 4, 0, 0)
assert ports == [501]
target_event = events[0]
recipient_cases = [{'kind': 'targeted', 'owner': hex(app), 'ports': ports.copy()}]
for owner, expected_ports, kind in [(0x39999, [], 'unregistered'),
                                    (0xffffffff, [503, 501, 502], 'broadcast')]:
    ports.clear()
    events.clear()
    call(m, 0xf314, 0x60008000, 0x60001000, owner, ipc)
    call(m, 0xf0fc, 0x60008000, ipc)
    assert ports == expected_ports
    recipient_cases.append({'kind': kind, 'owner': hex(owner), 'ports': ports.copy()})
events = [target_event]

rows = []
for reply_before_event in (False, True):
    p, syms = machine('appproxy', proxy_hash)
    ctx = 0x1ca5c
    for offset, value in [(0x24, 1), (0x10, 500), (0x18, 0x37), (0x1c, 501), (0x20, 1234),
                          (0x2c + 4 * 4, 0x95c0)]:
        put(p, ctx + offset, value)
    put(p, 0x1c834, 321)
    put(p, 0x60002000, 3)  # ESRCH for an already-reaped child.
    trace, join_wait = [], []
    deliver, dispatch_done = False, False
    def proxy_hook(uc, pc, size, data):
        a = args(uc)
        if pc == 0xd36c:
            if not deliver:
                trace.append('dispatch-blocked')
                uc.emu_stop()
                return
            uc.mem_write(a[1], events[0])
            put(uc, a[3], 20)
            trace.append('observer-event-received')
        elif pc == 0xd2c0:
            assert word(uc, ctx + 0x24) == 0
            assert struct.unpack('<2I', uc.mem_read(a[2], 8)) == (8, 3)
            if not reply_before_event and not dispatch_done:
                trace.append('quit-awaiting-reply')
                uc.emu_stop()
                return
            trace.append('quit-reply')
        elif pc == 0xe5e0:
            if not dispatch_done:
                join_wait.append(True)
                trace.append('join-waits-dispatch')
                uc.emu_stop()
                return
            trace.append('join-completed')
        elif pc == syms['kill']:
            assert a[:2] == [321, 15]
            trace.append('stale-child-kill-ESRCH')
            returned(uc, 0xffffffff)
            return
        elif pc == syms['__errno_location']:
            returned(uc, 0x60002000)
            return
        elif pc in (0xfbf8, 0xfc38):
            raise AssertionError('Native panic reached')
        elif pc not in (0xea80, 0xeae8, 0x9a0c, 0xcfbc, 0xd1ac, 0xdc1c, 0xf148):
            return
        returned(uc)
    p.hook_add(UC_HOOK_CODE, proxy_hook)
    call(p, 0x9b40, 0x60008000, ctx)
    dispatch_context = p.context_save()
    assert trace == ['dispatch-blocked']
    call(p, 0x9a50, 0x60018000)
    finalizer_context = p.context_save()
    assert word(p, ctx + 0x24) == 0
    assert (bool(join_wait)) == reply_before_event
    p.context_restore(dispatch_context)
    deliver = True
    p.emu_start(p.reg_read(UC_ARM_REG_PC), 0x50000000, count=100000)
    assert p.reg_read(UC_ARM_REG_PC) == 0x50000000 and p.reg_read(UC_ARM_REG_R0) == 0
    dispatch_done = True
    trace.append('dispatch-returned')
    p.context_restore(finalizer_context)
    p.emu_start(p.reg_read(UC_ARM_REG_PC), 0x50000000, count=100000)
    assert p.reg_read(UC_ARM_REG_PC) == 0x50000000 and word(p, 0x1ca54) == 0
    assert trace.index('observer-event-received') < trace.index('dispatch-returned') < trace.index('join-completed')
    rows.append({'reply_before_observer': reply_before_event, 'trace': trace})
report = {'scope': 'Original observer producer/event encoder/proxy dispatcher and finalizer; virtual scheduling',
          'sysmgrd_sha256': mgr_hash, 'appproxy_sha256': proxy_hash,
          'observer_packet': [4, 0, 0], 'event_packet': [20, 0, 4, 0, 0], 'cases': rows,
          'recipient_cases': recipient_cases,
          'rea_boundary_correction': '0x167bc pseudocode incorrectly resolves to 0x1e6bc; excluded. Exact objdump instructions and replay used.',
          'limits': ['Records/linked-list insertion/predicate/traversal execute original instructions; live registration and allocation do not.',
                     'Queue, transport, locks, thread join and signals are virtual; no real kernel scheduling ran.',
                     'Frontend/child already exited; observer producer called directly, not through op3 in this test.',
                     'Full APF server, process exit notification and Sony hardware restoration remain unqualified.']}
(ROOT / 'sources/native-observer-wakeup.json').write_text(json.dumps(report, indent=2) + '\n')
print('Three native recipient lookups and two proxy wakeup/join scheduling fixtures passed')
