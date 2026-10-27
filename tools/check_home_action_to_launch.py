"""Candidate action record -> GUI forwarding -> Home hook -> APF request.

The metadata prefix comes from the original constructor. Its last item index,
action container, descriptor-created flag and state contexts are fixtures.
No raw touch, widget hit testing, actual manager or physical device runs.
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
manifest = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text())
raw = (ROOT / manifest['artifact']).read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == manifest['candidate_sha256']
elf = ELFFile(io.BytesIO(raw))
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for menu, cfg, index in ((0, 1, 10), (1, 2, 9)):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x80000)
    root, action = 0x60010000, 0x60030000
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    def cstr(address):
        token = bytearray()
        while (c := bytes(u.mem_read(address, 1))) != b'\0':
            token.extend(c)
            address += 1
        return token.decode()
    put(root + 0xea48, 1)
    put(root + 0x2ff8, menu)
    for unused_slot in range(1, 4):
        put(root + 0x2ff8 + unused_slot * 0x2e94, 0xffffffff)
    events = root + 0x2ff8 + 0x20
    put(events + 8, 1)
    put(events + 0x14, action)
    put(action + 8, 0x13)
    put(0x613e4c, cfg)
    queued, requests, names = [], [], []
    def hook(uc, pc, size, data):
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc == 0x1094f0:
            result = 0x60050000
        elif pc == 0x1047b4:
            uc.mem_write(a[1], b'\0\0')
        elif pc == symbols['memset']:
            uc.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            result = a[0]
        elif pc == symbols['memcpy']:
            uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])))
            result = a[0]
        elif pc == 0xa57f0:
            queued.append(a)
        elif pc == 0x2664d0:
            name = cstr(a[1])
            assert name == '/contents/HOMEBREW/launcher/app'
            names.append(name)
            put(a[2], 0x30001)
        elif pc == 0x2681e8:
            assert a[1:] == [0x30001, 0, 0]
            requests.append(a[1:])
        elif pc not in (0x2a730, 0xb00bc, 0x33b83c):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def call(pc, values):
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), values):
            u.reg_write(reg, value)
        u.reg_write(UC_ARM_REG_SP, 0x60078000)
        u.reg_write(UC_ARM_REG_LR, 0x50000000)
        u.emu_start(pc, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    call(0x10e754, (0x4e692c, 156, 0, 0))
    call(0x10e558, (menu, 0x60052000, 0, 0))
    view = word(0x60052000)
    assert view == 0x60050004
    put(root + 0x2b18 + menu * 8, view)
    metadata = list(struct.unpack('<15I', u.mem_read(view + 0x18, 60)))
    assert metadata[1] == 10 and metadata[2] == menu
    # Exact native vector, with the selected item's last-level value inserted.
    # Real per-cell construction/hit testing remains outside this fixture.
    metadata[metadata[1] + 1] = index
    u.mem_write(action + 0x1c, struct.pack('<15I', *metadata))
    for created_state in (0, 2, 1):
        put(view + 0x98, created_state)
        call(0x2c4bc, (root, 0, 0, 0))
        if created_state != 1:
            assert queued == []
    assert queued == [[0x2010b, 0, index, menu]], (menu, queued)
    context = bytearray(32)
    context[0], context[1], context[13] = 1, 11, 10
    struct.pack_into('<I', context, 4, 0x3ea150)
    u.mem_write(0x60040000, bytes(context))
    call(0x17c608, (0x60040000, queued[0][0], queued[0][2], queued[0][3]))
    assert queued[-1] == [0x4a0111, 0, index, menu]
    context[0], context[1] = 0x33, 2
    struct.pack_into('<I', context, 4, 0x3f55d8)
    u.mem_write(0x60040000, bytes(context))
    call(0x17c608, (0x60040000, queued[-1][0], queued[-1][2], queued[-1][3]))
    assert len(names) == 1 and requests == [[0x30001, 0, 0]]
    rows.append({'list_fixture': menu, 'cfg_fixture': cfg, 'new_index': index,
                 'native_descriptor_created_states_checked': [0, 2, 1],
                 'constructor_metadata': metadata, 'metadata_last_selector': metadata[1],
                 'events': [[hex(q[0]), *q[1:]] for q in queued],
                 'lookup_name': names[0], 'switch_request': requests[0]})
report = {'scope': 'Patched ARM action-processing/GUI forwarding/Home hook/native switch request; external services mocked',
          'candidate_sha256': digest, 'cases': rows,
          'limits': ['Metadata prefix comes from original binder/constructor; the selected last-level index and action13 container remain injected.',
                     'Original descriptor-created getter executes with states0/2/1 supplied; this is not a visibility/active-view check or real widget/touch production.',
                     'GUI mode1/state11 and Home mode33/state2 are fixtures; actual runtime routing remains unqualified.',
                     'Actual APF lookup/change, process execution and Walkman return are separate checks.',
                     'Does not prove new Home item visibility, touch hitbox or final caption.']}
(ROOT / 'sources/native-home-action-to-launch.json').write_text(json.dumps(report, indent=2) + '\n')
print('Two candidate action-metadata -> original GUI/Home -> native APF switch-request chains verified')
