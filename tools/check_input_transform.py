"""Original input matrix transform with explicit matrix/vector fixtures, no GPU."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
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
u.mem_map(0x60000000, 0x10000)
def interrupt(uc, number, data):
    raise AssertionError(f'Unexpected syscall/interrupt {number}')
u.hook_add(UC_HOOK_INTR, interrupt)
rows = []
for name, matrix in [('identity', [16384,0,0,0,16384,0,0,0,16384]),
                     ('quarter_turn_fixture', [0,16384,0,-16384,0,0,0,0,16384])]:
    u.mem_write(0x6000108c, struct.pack('<9h', *matrix))
    for vector in [(0,0,0),(-120,-216,0),(119,215,0),(6,132,0),(-70,132,0)]:
        u.mem_write(0x60002000, struct.pack('<3i', *vector))
        for reg, value in [(UC_ARM_REG_R0, 0x60002000), (UC_ARM_REG_R1, 0x60001000),
                           (UC_ARM_REG_R2, 0x60003000), (UC_ARM_REG_SP, 0x60008000),
                           (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0x10e38c, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        output = list(struct.unpack('<3i', u.mem_read(0x60003000, 12)))
        expected = list(vector) if name == 'identity' else [-vector[1],vector[0],vector[2]]
        assert output == expected
        rows.append({'matrix_fixture': name, 'input_vector': vector, 'output_vector': output})
def native_call(pc, values):
    for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), values):
        u.reg_write(reg, value & 0xffffffff)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(pc, 0x50000000, count=100000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
    return u.reg_read(UC_ARM_REG_R0)
orientations = []
for orientation in range(4):
    u.mem_write(0x60001000, bytes(0x200))
    angle = native_call(0xeb8fc, (orientation,))
    native_call(0xeb87c, (0x60001000, angle))
    native_call(0xeb5ec, (0x60001000,))
    assert native_call(0xeb8ec, (0x60001000,)) == orientation
    matrix = list(struct.unpack('<9h', u.mem_read(0x6000108c, 18)))
    u.mem_write(0x60002000, struct.pack('<3i', 7, 11, 0))
    native_call(0x10e38c, (0x60002000, 0x60001000, 0x60003000))
    output = list(struct.unpack('<3i', u.mem_read(0x60003000, 12)))
    assert output[0] ** 2 + output[1] ** 2 == 170 and output[2] == 0
    dimensions = [native_call(0xeb948, (orientation,)), native_call(0xeb97c, (orientation,))]
    assert dimensions == ([432, 240] if orientation in (0, 2) else [240, 432])
    orientations.append({'orientation_fixture': orientation, 'angle_bits': hex(angle),
                         'native_matrix': matrix, 'transformed_vector': output,
                         'native_dimensions': dimensions})
assert len({tuple(x['native_matrix']) for x in orientations}) == 4
assert orientations[1]['native_matrix'] == [16384,0,0,0,16384,0,0,0,16384]
context = native_call(0x119190, ())
native_call(0x119258, (context,))
viewport_records = []
for getter in (0x11e48c, 0x11e464, 0x11e478):
    pointer = native_call(getter, (context,))
    words = list(struct.unpack('<4i', u.mem_read(pointer, 16)))
    assert words == [0,0,239,431]
    viewport_records.append({'getter': hex(getter), 'words': words})
native_call(0xeb87c, (0x60001000, 0))
native_call(0xeb5ec, (0x60001000,))
pixel_cases = []
for point in [(0,0,0),(120,216,0),(126,348,0),(50,348,0),(239,431,0)]:
    u.mem_write(0x60002000, struct.pack('<3i', *point))
    native_call(0x10e334, (0x60002000, 0x60001000, 0x60003000))
    output = list(struct.unpack('<3i', u.mem_read(0x60003000, 12)))
    assert output == list(point)
    pixel_cases.append({'input_pixel': point, 'output_pixel': output})
report = {'input_sha256': digest, 'procedures': ['0x10e38c', '0x1351fc', '0xeb8fc', '0xeb87c', '0xeb5ec',
                                              '0x119190', '0x119258', '0x11e48c', '0x11e464', '0x11e478',
                                              '0x10e334', '0x116cc8'], 'cases': rows,
          'native_orientation_cases': orientations,
          'native_pixel_conversion_cases': pixel_cases,
          'native_initial_viewport_records': viewport_records,
          'limits': ['Explicit signed Q14 matrix/vector fixtures; no mocked arithmetic, syscalls or GPU.',
                     'Four original orientation setter/update/getter and dimension roundtrips use zero-translation state; no actual Home orientation/animation or hardware configuration is established.',
                     'Five original10e334/116cc8 pixel cases use original119190/119258 context initialization and native viewport getters, with no arithmetic/getter mocks. Initial viewport preserves pixels under identity. Later graphics/clipping state and full parent/scheduler mapping remain unqualified.']}
(ROOT / 'sources/native-input-transform.json').write_text(json.dumps(report, indent=2) + '\n')
print('Ten vector transforms, four orientation roundtrips and five default-viewport pixel conversions passed')
