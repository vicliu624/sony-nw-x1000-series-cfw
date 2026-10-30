"""PC-only execution of stock pool init/alloc/free with a reserved final block.

Requires the private original radio image. Never writes or connects to a device.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
sys.path.insert(0, str(Path(__file__).resolve().parent))
from marvell_firmware import parse

ROOT = Path(__file__).resolve().parents[1]
blob = (ROOT/'work/targets-jp/sd8686.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest() == '08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
BASE, STRIDE, MANAGER = 0xc0008b4c, 0x76c, 0xc000d5a4
RESERVED, END = BASE + 3*STRIDE, BASE + 4*STRIDE
reports = []
for count in (4, 3):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    u.mem_map(0, 0x20000)
    u.mem_map(0xc0000000, 0x20000)
    u.mem_map(0x200000, 0x10000)
    for record in parse(blob):
        if record.command == 1 and record.address < 0x20000:
            u.mem_write(record.address, record.data)
    assert bytes(u.mem_read(0x163ee, 2)) == bytes.fromhex('0422')
    if count == 3:
        u.mem_write(0x163ee, bytes.fromhex('0322'))
    sentinel = bytes([0xa5])*STRIDE
    u.mem_write(RESERVED, sentinel)

    def hook(cpu, address, size, user):
        if address == 0x1f000:
            cpu.emu_stop()
        elif address in (0xfa94, 0xfaa0):
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, hook)

    def call(entry, *args):
        u.reg_write(UC_ARM_REG_SP, 0x208000)
        u.reg_write(UC_ARM_REG_LR, 0x1f001)
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
            u.reg_write(register, value)
        u.emu_start(entry | 1, 0x1f002, count=5000)
        return u.reg_read(UC_ARM_REG_R0)

    assert call(0x163ec) == MANAGER
    assert struct.unpack('<H', u.mem_read(MANAGER+4, 2))[0] == STRIDE
    assert struct.unpack('<H', u.mem_read(MANAGER+6, 2))[0] == count
    expected = [BASE + i*STRIDE + 4 for i in range(count)]
    cycles = 12
    for cycle in range(cycles):
        allocated = [call(0x102dc, MANAGER) for _ in range(count)]
        assert sorted(allocated) == expected
        assert call(0x102dc, MANAGER) == 0
        for pointer in allocated:
            assert call(0x1031c, MANAGER, pointer) == 0
        if count == 3:
            assert bytes(u.mem_read(RESERVED, STRIDE)) == sentinel
    reports.append({'pool_blocks': count, 'allocation_release_cycles': cycles,
                    'expected_buffer_addresses': [hex(x) for x in expected],
                    'reserved_block_untouched': count == 3})
report = {'passed': True, 'reserved_start': hex(RESERVED), 'reserved_end': hex(END),
          'reserved_bytes': STRIDE, 'reports': reports,
          'stock_instructions_executed': True, 'irq_helpers_mocked': True,
          'other_users_audited': False, 'device_written': False}
out = ROOT/'work/espnow-radio-bridge'
out.mkdir(exist_ok=True)
(out/'pool-reservation-tests.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
