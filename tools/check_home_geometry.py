"""Replay stock Home cell placement using pinned style and menu records.

This checks local coordinates and candidate control construction, but not touch hit-testing,
scrolling, compositor transforms or framebuffer presentation.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', action='store_true')
args = parser.parse_args()
candidate = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text()) if args.candidate else None
parent_report = json.loads((ROOT / 'sources/native-home-parent.json').read_text()) if candidate else None
if candidate:
    assert parent_report['candidate_sha256'] == candidate['candidate_sha256']
raw = (ROOT / (candidate['artifact'] if candidate else 'work/targets-jp/SpiderApp')).read_bytes()
assert hashlib.sha256(raw).hexdigest() == (candidate['candidate_sha256'] if candidate else '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85')
style = (ROOT / 'work/resource-analysis/style.dat').read_bytes()
assert hashlib.sha256(style).hexdigest() == '84c29fb6747390c92ac28e9b3cab3410c2af28d40d12da83890b8c2d189a6635'
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
rows = []
for menu in (0, 1):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(low, high - low)
    for s in segments:
        u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    u.mem_map(0x61000000, 0x107000)
    if candidate:
        u.mem_map(0x63000000, 0x100000)
    u.mem_write(0x61000000, style)
    u.mem_write(0x754abc, struct.pack('<I', 0x61000000))
    meta = struct.unpack('<33I', u.mem_read(0x4e692c + menu * 132, 132))
    content_size = parent_report['cases'][menu]['content_size'] if candidate else [meta[3], meta[4]]
    grid, content, position, output = 0x60010000, 0x60012000, 0x60014000, 0x60015000
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    put(grid + 0xb1c, 74)
    put(grid + 0xb00, content)
    for offset, field in [(0xb20, 16), (0xb24, 17), (0xb28, 18), (0xb2c, 19), (0xb30, 20)]:
        put(grid + offset, meta[field])
    put(content + 0x3a8, content_size[0])
    put(content + 0x3ac, content_size[1])
    creation_requests = []
    allocations, heap_allocations = [], []
    touch_payload = bytearray(11)
    selection_events = []
    switch_requests = []
    heap = 0x63080000
    def hook(uc, pc, size, data):
        global heap
        if pc == symbols['__modsi3']:
            a, b = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
            assert a < 0x80000000 and b > 0
            uc.reg_write(UC_ARM_REG_R0, a % b)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif pc == 0xf577c:
            style_id = uc.reg_read(UC_ARM_REG_R3)
            assert style_id == 74 and uc.reg_read(UC_ARM_REG_R1) == content
            xyz = list(struct.unpack('<iii', uc.mem_read(uc.reg_read(UC_ARM_REG_R2), 12)))
            stack = uc.reg_read(UC_ARM_REG_SP)
            assert struct.unpack('<I', uc.mem_read(stack, 4))[0] == 1
            creation_requests.append({'style': style_id, 'position': xyz})
            return  # Execute the original factory and both control constructors.
        elif candidate:
            a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            result = 0
            if pc == 0xe87f4:
                result = 0x60000000
            elif pc == 0xe9300:
                assert len(allocations) < 8
                result = 0x63001000 + len(allocations) * 0x4000
                allocations.append(result)
                uc.mem_write(result + 0x460, struct.pack('<I', 0x2008))
            elif pc == symbols['malloc']:
                result = heap
                heap += (a[0] + 15) & ~15
                assert heap < 0x63100000
                heap_allocations.append(a[0])
            elif pc == symbols['memset']:
                uc.mem_write(a[0], bytes([a[1] & 255]) * a[2])
                result = a[0]
            elif pc == symbols['memcpy']:
                uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])))
                result = a[0]
            elif pc in (0x1072c0, 0x10752c):
                result = 0  # Auxiliary manager/attachment response, not widget lookup.
            elif pc == 0x1047b4:
                uc.mem_write(a[1], b'\0\0')
            elif pc == 0xa57f0:
                selection_events.append([*a, uc.reg_read(UC_ARM_REG_R3)])
            elif pc == 0x2a730:
                result = 0  # Action consumption side effects are outside this check.
            elif pc == 0x2664d0:
                name = bytes(uc.mem_read(a[1], 64)).split(b'\0')[0]
                assert name == b'/contents/HOMEBREW/launcher/app'
                uc.mem_write(a[2], struct.pack('<I', 0x30001))
            elif pc == 0x2681e8:
                request = [a[1], a[2], uc.reg_read(UC_ARM_REG_R3)]
                assert request == [0x30001, 0, 0]
                switch_requests.append(request)
            elif pc == 0xb00bc:
                result = 0
            elif pc == 0x115e28:
                result = 0  # Resource initializer excluded from bounded startup prefix.
            elif pc == 0x33c528:
                result = 0  # Auxiliary service used by1011e0; runtime backend virtual.
            elif pc == symbols['ioctl']:
                assert a[1] == 0x80045401
                uc.mem_write(a[2], bytes(touch_payload))
                result = 0
            elif pc not in (symbols['free'], 0x33b748, 0x33b83c, 0x33b918):
                return
            uc.reg_write(UC_ARM_REG_R0, result)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def interrupt(uc, number, data):
        raise AssertionError('Unexpected syscall during widget/geometry replay')
    u.hook_add(UC_HOOK_INTR, interrupt)
    cells = []
    for index in range(meta[21] + (0 if candidate else 1)):
        put(position + 4, index)
        for reg, value in [(UC_ARM_REG_R0, grid), (UC_ARM_REG_R1, position),
                           (UC_ARM_REG_R2, output), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xfca30, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        x, y, z = struct.unpack('<iii', u.mem_read(output, 12))
        assert -content_size[0] // 2 <= x - 32 and x + 32 <= content_size[0] // 2
        assert -content_size[1] // 2 <= y - 32 and y + 32 <= content_size[1] // 2
        assert all(abs(x - px) >= 64 or abs(y - py) >= 64 for px, py in cells)
        cells.append((x, y))
    if candidate:
        assert cells == [tuple(p[:2]) for p in parent_report['cases'][menu]['cell_centers_in_current_content']]
        # Stock fcb24 tail passes this callback to f8964 (literal atfd16c).
        assert bytes(u.mem_read(0xfcf94, 8)) == bytes.fromhex('d0219fe571eeffeb')
        assert struct.unpack('<I', u.mem_read(0xfd16c, 4))[0] == 0xfd5e8
        metadata = parent_report['cases'][menu]['native_new_entry_metadata']
        assert metadata[1] == 10 and metadata[metadata[1] + 1] == len(cells) - 1
        u.mem_write(0x60017000, struct.pack('<15I', *metadata))
        pool = 0x6000d000
        for reg, value in [(UC_ARM_REG_R0, pool), (UC_ARM_REG_R1, 0),
                           (UC_ARM_REG_R2, 0), (UC_ARM_REG_R3, 0),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        put(0x60008000, 0)
        u.emu_start(0xf826c, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert struct.unpack('<I', u.mem_read(pool, 4))[0] == 1  # Explicit bounded input-unit fixture.
        for reg, value in [(UC_ARM_REG_R0, pool), (UC_ARM_REG_R1, 0x60017000),
                           (UC_ARM_REG_R2, grid), (UC_ARM_REG_R3, 0xfd514),
                           (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xf8304, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and u.reg_read(UC_ARM_REG_R0) == 0
        assert creation_requests == [{'style': 74, 'position': [*cells[0], 0]}]
        child = struct.unpack('<I', u.mem_read(pool + 0x40, 4))[0]
        assert len(allocations) == 2 and child == allocations[0]
        assert struct.unpack('<I', u.mem_read(child + 0x4ac, 4))[0] == 0xece8c
        assert struct.unpack('<I', u.mem_read(child + 0x460, 4))[0] & 0x20000000
        for address in allocations:
            assert struct.unpack('<II', u.mem_read(address + 0x3a8, 8)) == (64, 64)
        rectangle_context = struct.unpack('<I', u.mem_read(child + 0x470, 4))[0]
        assert rectangle_context == 0  # Inherited from this test's parent fixture.
        for reg, value in [(UC_ARM_REG_R0, child), (UC_ARM_REG_R1, 0x60018010),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xed5e8, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        rectangle_result = u.reg_read(UC_ARM_REG_R0)
        assert rectangle_result == 5
        for reg, value in [(UC_ARM_REG_R0, content), (UC_ARM_REG_R1, 0x60019000),
                           (UC_ARM_REG_R2, 1), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xed518, 0x50000000, count=20000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        for address in allocations:
            assert struct.unpack('<I', u.mem_read(address + 0x470, 4))[0] == 0x60019000
        for pc, values in [(0x119258, (0x761394,)), (0xed5e8, (child, 0x60018010))]:
            for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1), values):
                u.reg_write(reg, value)
            u.reg_write(UC_ARM_REG_SP, 0x60008000)
            u.reg_write(UC_ARM_REG_LR, 0x50000000)
            u.emu_start(pc, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        bound_rectangle_result = u.reg_read(UC_ARM_REG_R0)
        assert bound_rectangle_result == 0
        assert list(struct.unpack('<8i', u.mem_read(0x60019000, 32))) == [0,0,240,432] * 2
        input_callbacks = [struct.unpack('<I', u.mem_read(a + 0x4bc, 4))[0] for a in allocations]
        assert input_callbacks == [0xed114, 0x102250]
        model, wrapper, buffer, records = pool, 0x60007000, 0x60003000, 0x60004000
        # Reuse the actual model/control reference produced by preallocation.
        model_capacity = struct.unpack('<I', u.mem_read(model, 4))[0]
        assert model_capacity == 1  # Unit fixture; separate parent integration has native49 slots.
        for reg, value in [(UC_ARM_REG_R0, model),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xf87f8, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        # The original staging/commit functions install metadata and flags.
        # fd5e8 reuses/enables/positions the control; it is not a new allocator.
        for pc, values in [(0xf8844, (model, 0x60017000, 0)), (0xf8964, (model, grid, 0xfd5e8))]:
            for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), values):
                u.reg_write(reg, value)
            u.reg_write(UC_ARM_REG_SP, 0x60008000)
            u.reg_write(UC_ARM_REG_LR, 0x50000000)
            u.emu_start(pc, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and u.reg_read(UC_ARM_REG_R0) == 0
        assert list(struct.unpack('<15I', u.mem_read(model + 4, 60))) == metadata
        registration_flags = struct.unpack('<I', u.mem_read(model + 0x44, 4))[0]
        assert registration_flags == 0x202
        assert struct.unpack('<I', u.mem_read(model + 0x1de0, 4))[0] == 0
        committed_position = list(struct.unpack('<iii', u.mem_read(child + 0x2f4, 12)))
        assert committed_position == [*cells[-1], 0]
        # Local coordinates and classified input phases remain fixtures. Let
        # original hit testing/state handling generate completion and actions.
        leaf = allocations[1]
        point, packet, envelope = 0x60002100, 0x60002200, 0x60002400
        for reg, value in [(UC_ARM_REG_R0, leaf), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xede84, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        native_bounds = list(struct.unpack('<4i', u.mem_read(leaf + 0xa2c, 16)))
        cx, cy = cells[-1]
        assert native_bounds == [cx - 32, cy - 32, cx + 31, cy + 31]
        hit_results = []
        for x, expected_hit in ((cx + 32, 0), (cx, 1)):
            put(point + 4, x & 0xffffffff)
            put(point + 8, cy)
            for reg, value in [(UC_ARM_REG_R0, leaf), (UC_ARM_REG_R1, point),
                               (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            u.emu_start(0xecc20, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
            hit = struct.unpack('<I', u.mem_read(leaf + 0x478, 4))[0]
            assert hit == expected_hit
            hit_results.append({'hit_input_point': [x, cy], 'hit': hit})
        put(envelope + 4, packet)
        touch_context, classified = 0x60016000, 0x60002300
        vector, centered, view = 0x60002500, 0x60002510, 0x60002600
        # Execute the actual manager startup prefix through its two view
        # allocations and position assignments; do not run later subsystems.
        manager = 0x64000000
        u.mem_map(manager, 0x30000)
        for reg, value in [(UC_ARM_REG_R0, manager), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xe8800, 0xe8900, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0xe8900
        view_pool = manager + 8
        assert struct.unpack('<2I', u.mem_read(view_pool, 8)) == (0, 2)
        for reg, value in [(UC_ARM_REG_R0, view_pool), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xebb74, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        view = u.reg_read(UC_ARM_REG_R0)
        assert view == view_pool + 8
        assert struct.unpack('<2I', u.mem_read(manager + 0x364, 8)) == (view, view + 0x11c)
        for active_view in (view, view + 0x11c):
            assert struct.unpack('<3i', u.mem_read(active_view + 0x80, 12)) == (120, 216, -200)
        for reg, value in [(UC_ARM_REG_R0, view), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xeb5ec, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        native_view_matrix = list(struct.unpack('<9h', u.mem_read(view + 0x8c, 18)))
        assert native_view_matrix == [16384,0,0,0,16384,0,0,0,16384]
        px, py = cx + 120, cy + 216
        rx, ry = (px * 2929 + 239) // 240, ((431 - py) * 5281 + 431) // 432
        struct.pack_into('>HH', touch_payload, 2, rx, ry)
        touch_trace = []
        def native_call(pc, values):
            for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), values):
                u.reg_write(reg, value)
            u.reg_write(UC_ARM_REG_SP, 0x60008000)
            u.reg_write(UC_ARM_REG_LR, 0x50000000)
            u.emu_start(pc, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        for contact, expected_phase in ((1, 2), (0, 3)):
            touch_payload[1] = contact
            native_call(0x115acc, (touch_context, classified))
            phase = struct.unpack('<I', u.mem_read(classified, 4))[0]
            assert phase == expected_phase
            assert struct.unpack('<2I', u.mem_read(classified + 0xc, 8)) == (px, py)
            put(0x60008000, 0)
            native_call(0xf6cd0, (packet, classified, 0, 0))
            u.mem_write(vector, bytes(u.mem_read(classified + 0xc, 8)))
            put(vector + 8, 0)
            native_call(0x116ddc, (vector, 120, 216, centered))
            native_call(0x10e38c, (centered, view, point + 4))
            assert struct.unpack('<2i', u.mem_read(point + 4, 8)) == (cx, cy)
            native_call(0xecc20, (leaf, point))
            assert struct.unpack('<I', u.mem_read(leaf + 0x478, 4))[0] == 1
            native_call(0x101d28, (leaf, envelope))
            touch_trace.append({'contact_fixture': contact, 'raw_fixture': [rx, ry],
                                'decoded_pixel': [px, py], 'native_phase': phase,
                                'transformed_hit_point': [cx, cy]})
        pending_count = struct.unpack('<I', u.mem_read(leaf + 0x498, 4))[0]
        pending_types = []
        for i in range(pending_count):
            record = struct.unpack('<I', u.mem_read(leaf + 0x480 + i * 4, 4))[0]
            pending_types.append(struct.unpack('<I', u.mem_read(record + 4, 4))[0])
        assert pending_types == [0x11, 0x14, 0x13, 0x14]
        put(0x60005ff0, model)
        put(wrapper + 0x4c8, child)
        put(buffer + 0x10, 4)
        put(buffer + 0x14, records)
        for reg, value in [(UC_ARM_REG_R0, wrapper), (UC_ARM_REG_R1, 0x60005ff0),
                           (UC_ARM_REG_R2, buffer), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0x114914, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and u.reg_read(UC_ARM_REG_R0) == 0
        assert struct.unpack('<I', u.mem_read(buffer + 8, 4))[0] == 4
        enriched_metadata = list(struct.unpack('<15I', u.mem_read(records + 2 * 0x2b0 + 0x1c, 60)))
        assert enriched_metadata == metadata
        assert struct.unpack('<I', u.mem_read(leaf + 0x498, 4))[0] == 0
        consumer = 0x60009000
        put(consumer + 0xea48, 1)
        put(consumer + 0x2ff8, menu)
        for unused_slot in range(1, 4):
            put(consumer + 0x2ff8 + unused_slot * 0x2e94, 0xffffffff)
        descriptor_guard = 0x60005000
        put(consumer + 0x2b18 + menu * 8, descriptor_guard)
        consumer_buffer = consumer + 0x2ff8 + 0x20
        u.mem_write(consumer_buffer, bytes(u.mem_read(buffer, 24)))
        for created_state in (0, 2, parent_report['cases'][menu]['native_descriptor_created_state']):
            put(descriptor_guard + 0x98, created_state)
            for reg, value in [(UC_ARM_REG_R0, consumer), (UC_ARM_REG_SP, 0x60008000),
                               (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            u.emu_start(0x2c4bc, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
            if created_state != 1:
                assert selection_events == []
        assert selection_events == [[0x2010b, 0, len(cells) - 1, menu]]
        context = bytearray(32)
        context[0], context[1], context[13] = 1, 11, 10
        struct.pack_into('<I', context, 4, 0x3ea150)
        put(0x613e4c, menu + 1)
        for phase in ('gui', 'home'):
            if phase == 'home':
                context[0], context[1] = 0x33, 2
                struct.pack_into('<I', context, 4, 0x3f55d8)
            u.mem_write(0x60002000, bytes(context))
            event = selection_events[-1]
            for reg, value in [(UC_ARM_REG_R0, 0x60002000), (UC_ARM_REG_R1, event[0]),
                               (UC_ARM_REG_R2, event[2]), (UC_ARM_REG_R3, event[3]),
                               (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            u.emu_start(0x17c608, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert selection_events[-1] == [0x4a0111, 0, len(cells) - 1, menu]
        assert switch_requests == [[0x30001, 0, 0]]
        # ef2a4 installs a 352-byte input template, not a click dispatch.
        template = bytes((i * 17 + 3) & 255 for i in range(0x160))
        u.mem_write(0x60002000, template)
        leaf = allocations[1]
        bank = struct.unpack('<I', u.mem_read(leaf + 0xb00, 4))[0]
        bank_index = struct.unpack('<I', u.mem_read(leaf + 0xafc, 4))[0]
        assert bank != 0 and bank_index < 5
        for reg, value in [(UC_ARM_REG_R0, leaf), (UC_ARM_REG_R1, 0x60002000),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0xef2a4, 0x50000000, count=20000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        assert bytes(u.mem_read(leaf, 0x160)) == template
        assert bytes(u.mem_read(bank + bank_index * 0x2c0, 0x2c0)) == template * 2
    rows.append({'menu': menu, 'source_items': meta[21], 'tested_items': len(cells),
                 'content_size': content_size, 'cell_size': [64, 64],
                 'local_centers': cells, 'fits_assumed_content': True,
                 'native_cell_creation_requests': creation_requests,
                 'native_control_count': len(allocations),
                 'native_pool_preallocation': bool(candidate),
                 'native_model_reused_without_reference_transfer': bool(candidate),
                 'native_input_template_callbacks': [hex(x) for x in input_callbacks] if candidate else [],
                 'native_leaf_input_template_copies': 3 if candidate else 0,
                 'native_completion_reason_fixture': None,
                 'native_input_phase_fixtures': [],
                 'native_touch_to_selection_trace': touch_trace if candidate else [],
                 'coordinate_mapping_fixture': 'Explicit centered-vector helper wiring; not the full native pixel reprojection' if candidate else None,
                 'native_zero_pose_view_matrix': native_view_matrix if candidate else [],
                 'native_view_constructor': '0xeb594' if candidate else None,
                 'native_view_pool_allocate_and_get_active': bool(candidate),
                 'native_view_startup_allocated_count': 2 if candidate else None,
                 'native_view_startup_position': [120, 216, -200] if candidate else [],
                 'native_hit_tests': hit_results if candidate else [],
                 'native_refreshed_hit_bounds': native_bounds if candidate else [],
                 'native_pending_action_types': pending_types if candidate else [],
                 'native_collected_action_metadata': enriched_metadata if candidate else [],
                 'native_registration_flags': registration_flags if candidate else None,
                 'native_model_capacity': model_capacity if candidate else None,
                 'native_commit_callback': '0xfd5e8' if candidate else None,
                 'native_committed_position': committed_position if candidate else [],
                 'native_selection_events': selection_events,
                 'native_descriptor_created_states_checked': [0, 2, 1] if candidate else [],
                 'native_switch_requests': switch_requests,
                 'heap_allocation_sizes': heap_allocations,
                 'initial_rectangle_pointer_0x470': rectangle_context if candidate else None,
                 'unbound_rectangle_reset_0xed5e8_result': rectangle_result if candidate else None,
                 'native_rectangle_pointer_propagation': bool(candidate),
                 'bound_rectangle_reset_after_context_init': bound_rectangle_result if candidate else None,
                 'native_callback_assignment': bool(creation_requests)})
result = {'scope': 'Original fca30 placement/static division' + (' and fd514/f577c/control constructors/callback assignment' if candidate else '') + '; allocation/modulo fixtures; stock portrait dimensions',
          'input_sha256': hashlib.sha256(raw).hexdigest(),
          'input': 'patched ELF' if candidate else 'stock ELF with one additional index',
          'procedure': '0xfca30', 'cell_style': 74, 'cases': rows,
          'limits': ['Candidate fd514/f577c and both style74 constructors execute; pool addresses, malloc/free/libc/logging are virtual.',
                     'Important gap: wired116ddc/10e38c feeds centered vectors into a zero-parent-position fixture. Original dispatcher uses10e334/116cc8 pixel reprojection, which preserves pixels with default viewport/identity. Parent positions/viewport must be recovered before claiming this is the real touch-to-Home pipeline.',
                     'This conditional input-unit replay explicitly uses request0/one slot. Separate native GUI-manager/parent integration creates the original default49 slots; earlier claims that one slot was the native default were incorrect.',
                     'Original manager startup e8800..e8900 initializes the pool, allocates two views and sets positions;115e28 is virtual and later initialization is not run. Native getter/update provide the first view matrix. Virtual ioctl/native decoding and explicitly wired coordinate/input helpers generate actions. Full e9690 scheduling, later Home view/animation/hardware/graphics remain unqualified;33c528/10752c are virtual.',
                     'Original109c04/1094fc execute descriptor-created checks with supplied states0/2/1; they do not establish actual visible/active view. Collected actions pass through2c4bc/GUI/Home to candidate request; action consumption/APF services and GUI/Home states remain virtual.',
                     'Parent/content and initial managers remain fixtures; no graphics backend, image upload, hit testing, scrolling or compositor transform is validated.',
                     'Unbound rectangle reset returns5; after original119258 context initialization, native pointer propagation and bound reset return0 and write two full-screen rectangles. This is memory/viewport state only, not actual framebuffer/compositor qualification.',
                     'Candidate new-entry metadata comes from the hash-bound native GUI/root/list construction report; its last index is not manually inserted here.',
                     'Candidate content dimensions/centers are checked against hash-bound native parent/grid initialization; later layout/scroll and full screen-space parent positions remain unqualified.',
                     'Fit applies to the supplied stock portrait content dimensions, not a physical screen test.',
                     'Source ELF and resources are unmodified.']}
(ROOT / ('sources/native-home-candidate-geometry.json' if candidate else 'sources/native-home-geometry.json')).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
