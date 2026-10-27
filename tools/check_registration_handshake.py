"""Bridge original proxy registration bytes into original manager handler.

Locks, ports, memory-pool allocation, transport and thread creation are virtual.
Process/event records and list operations execute original ARM instructions.
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
HASHES = {'sysmgrd': '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0',
          'appproxy': '57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'}
def machine(name):
    raw = (ROOT / 'work/targets-jp' / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HASHES[name]
    elf = ELFFile(io.BytesIO(raw))
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for s in elf.iter_segments():
        if s['p_type'] == 'PT_LOAD':
            u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x30000)
    return u, {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def put(u, address, value):
    u.mem_write(address, struct.pack('<I', value))
def word(u, address):
    return struct.unpack('<I', u.mem_read(address, 4))[0]
def args(u):
    return [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
def returned(u, value=0):
    u.reg_write(UC_ARM_REG_R0, value)
    u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
def call(u, pc, a=0, b=0, c=0):
    for reg, value in [(UC_ARM_REG_R0, a), (UC_ARM_REG_R1, b), (UC_ARM_REG_R2, c),
                       (UC_ARM_REG_SP, 0x60028000), (UC_ARM_REG_LR, 0x50000000)]:
        u.reg_write(reg, value)
    u.emu_start(pc, 0x50000000, count=200000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    return u.reg_read(UC_ARM_REG_R0)

rows = []
for scenario in ('valid', 'wrong-type', 'unknown-pid'):
    m, _ = machine('sysmgrd')
    ctx, ipc, process, event_record = 0x60010000, 0x60006000, 0x60002000, 0x60004000
    app, pid = 0x30001, 321
    replies, pool_requests = [], []
    def manager_hook(uc, pc, size, data):
        a = args(uc)
        result = 0
        if pc == 0x1b858:
            assert a[0] == ipc + 0x1c
            pool_requests.append(a[0])
            result = event_record
        elif pc == 0x16d18:
            assert a[:2] == [44, 642] and a[3] == 20
            replies.append(bytes(uc.mem_read(a[2], 20)))
        elif pc == 0x1618c:
            result = 1  # Unknown pid has no managed ancestor in this fixture.
        elif pc in (0x1c888, 0x1c8c8):
            raise AssertionError('Native manager panic')
        elif pc not in (0x1a458, 0x1a4f0, 0x1a508, 0xa188, 0x1c4d0, 0x1c5ac):
            return
        returned(uc, result)
    m.hook_add(UC_HOOK_CODE, manager_hook)
    put(m, ctx + 0x503c, 2)
    put(m, ipc, ctx)
    put(m, ipc + 4, 44)
    call(m, 0x162b4, ctx + 8)
    call(m, 0x165fc, process, pid if scenario != 'unknown-pid' else 999, app)
    assert call(m, 0x1633c, ctx + 8, process) == 0
    call(m, 0x162b4, ipc + 8)
    put(m, ipc + 8, 0x167ec)

    p, ps = machine('appproxy')
    proxy = 0x1ca5c
    request, opened, threads = [], [], []
    def proxy_hook(uc, pc, size, data):
        a = args(uc)
        result = 0
        if pc == ps['getpid']:
            result = pid
        elif pc == 0xd258:
            opened.append(a[1])
            put(uc, a[0], 500 + len(opened) - 1)
        elif pc == 0xd2c0:
            assert a[:2] == [500, 55] and a[3] == 32
            packet = bytes(uc.mem_read(a[2], 32))
            assert struct.unpack('<8I', packet) == (32, 0, 0, 0, 642, 643, pid, 0x10010001)
            request.append(list(struct.unpack('<8I', packet)))
            if scenario == 'wrong-type':
                packet = packet[:28] + struct.pack('<I', 0x20010001)
            m.mem_write(0x60003000, packet)
            call(m, 0xf584, ipc, 0x60003000)
            assert len(replies) == 1
        elif pc == 0xd36c:
            assert a[0] == 500 and a[2] == 20
            uc.mem_write(a[1], replies[0])
            put(uc, a[3], 20)
        elif pc == 0xe534:
            assert a[:2] == [0x9b40, proxy]
            threads.append(a[0])
            put(uc, word(uc, uc.reg_read(UC_ARM_REG_SP)), 1234)
        elif pc in (0xfbf8, 0xfc38):
            raise AssertionError('Native proxy panic')
        elif pc not in (0xea80, 0xeae8):
            return
        returned(uc, result)
    p.hook_add(UC_HOOK_CODE, proxy_hook)
    rc = call(p, 0xcdec, proxy)
    response = list(struct.unpack('<5I', replies[0]))
    if scenario == 'valid':
        assert rc == 0 and response == [20, 0, 0, 0, app]
        assert word(p, proxy) == app and word(p, proxy + 4) == 1
        assert word(p, proxy + 0x24) == 1 and threads == [0x9b40]
        assert word(m, process + 12) == 1
        assert word(m, ipc + 8 + 16) == event_record
        assert [word(m, event_record + off) for off in (4, 8)] == [app, 643]
    else:
        expected = 0x1d0b if scenario == 'wrong-type' else 0x1d03
        assert rc == expected and response[3] == expected
        assert not pool_requests and not threads and word(m, ipc + 24) == 0
    rows.append({'scenario': scenario, 'client_request': request[0], 'server_reply': response,
                 'client_return': rc, 'client_state': word(p, proxy + 4),
                 'registered_event_port': word(m, event_record + 8) if pool_requests else None,
                 'managed_record_field12': word(m, process + 12), 'thread_requests': threads})
report = {'scope': 'Original proxy registration -> manager handler/core/registry -> reply/state/thread request',
          'hashes': HASHES, 'cases': rows,
          'limits': ['Ports/transport/locks/pool allocation/thread creation are virtual.',
                     'Managed process record is constructed by original code but the actual fork is not run.',
                     'Unknown-pid ancestor lookup is fixture-limited, not full procfs traversal.',
                     'No full receive-loop validation, concurrent scheduling or Sony hardware restoration.']}
(ROOT / 'sources/native-registration-handshake.json').write_text(json.dumps(report, indent=2) + '\n')
print('Three registration handshakes: original bytes/state/port mapping and two rejection paths verified')
