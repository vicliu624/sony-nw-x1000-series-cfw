"""Replay stock READ CAPACITY response construction offline, with fixture RAM only."""
from pathlib import Path
import hashlib
import io
import json
import struct
import tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R11

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
    module = archive.extractfile('./lib/modules/g_nwm_msc.ko').read()
digest = hashlib.sha256(module).hexdigest()
assert digest == '084bec059243f852c8b14f5feeac965534c9345e19302b96b9ac8bf1d32c197e'
code = ELFFile(io.BytesIO(module)).get_section_by_name('.text').data()
# Command dispatcher compares opcode0x25; successful validation sets r5=0,
# while r4 retains the eight-byte response length. External validation is excluded.
assert struct.unpack_from('<I', code, 0x2e6c)[0] == 0xe3530025
assert struct.unpack_from('<I', code, 0x3264)[0] == 0xe3a04008
rows = []
for sectors in (1, 2, 32529973248 // 2048, 0xffffffff):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    base = 0x10000
    u.mem_map(base, 0x10000)
    u.mem_write(base, code)
    u.mem_map(0x30000, 0x10000)
    obj, lun, bh, buf, frame = 0x30000, 0x31000, 0x32000, 0x33000, 0x34000
    write = lambda address, value: u.mem_write(address, struct.pack('<I', value))
    write(obj + 0x11c, lun)
    write(lun + 12, sectors)
    write(frame - 128, bh)
    write(bh, buf)
    u.mem_write(buf, b'\xaa' * 8)
    for reg, value in ((UC_ARM_REG_R4, 8), (UC_ARM_REG_R5, 0),
                       (UC_ARM_REG_R6, obj), (UC_ARM_REG_R11, frame)):
        u.reg_write(reg, value)
    u.emu_start(base + 0x3298, base + 0x32e0, count=100)
    response = bytes(u.mem_read(buf, 8))
    last_lba, block_bytes = struct.unpack('>II', response)
    assert (last_lba, block_bytes) == (sectors - 1, 2048)
    assert u.reg_read(UC_ARM_REG_R5) == 8
    rows.append({'fixture_sector_count': sectors, 'response_hex': response.hex(),
                 'last_lba': last_lba, 'block_bytes': block_bytes})
report = {'module_sha256': digest, 'text_range': ['0x3298', '0x32e0 (exclusive)'],
          'cases': rows, 'all_passed': True, 'physical_device_access': False,
          'limits': ['RAM fixtures supply validated command state and backing-sector count.',
                     'Command validation, USB transfer and actual backing-device size are not replayed.']}
(ROOT / 'sources/native-usb-read-capacity.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
