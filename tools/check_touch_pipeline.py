"""Original ioctl payload -> touch decoder -> classified UI record, offline only."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for header in range(4):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x900000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    packet = bytearray(11)
    packet[0] = header
    struct.pack_into('>HH', packet, 2, 1464, 2640)
    ioctl_result = 0
    def hook(uc, pc, size, data):
        if pc == symbols['ioctl']:
            if ioctl_result == 0:
                uc.mem_write(uc.reg_read(UC_ARM_REG_R2), bytes(packet))
            uc.reg_write(UC_ARM_REG_R0, ioctl_result & 0xffffffff)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def interrupt(uc, number, data):
        raise AssertionError(f'Unexpected physical syscall/interrupt {number}')
    u.hook_add(UC_HOOK_CODE, hook)
    u.hook_add(UC_HOOK_INTR, interrupt)
    def invoke():
        for reg, value in [(UC_ARM_REG_R0, 0x60010000), (UC_ARM_REG_R1, 0x60011000),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(0x115acc, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    records = []
    for contact, phase in ((1, 2), (1, 4), (0, 3)):
        packet[1] = contact
        assert invoke() == 0
        words = list(struct.unpack('<12I', u.mem_read(0x60011000, 48)))
        assert words[:7] == [phase, header, contact, 119, 216, 119, 216]
        for reg, value in [(UC_ARM_REG_R0, 0x60012000), (UC_ARM_REG_R1, 0x60011000),
                           (UC_ARM_REG_R2, 0), (UC_ARM_REG_R3, 0),
                           (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.mem_write(0x60008000, struct.pack('<I', 0))
        u.emu_start(0xf6cd0, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        ui_kind = struct.unpack('<I', u.mem_read(0x60012004, 4))[0]
        ui_flags = struct.unpack('<I', u.mem_read(0x600120a0, 4))[0]
        copied = list(struct.unpack('<12I', u.mem_read(0x60012060, 48)))
        assert ui_kind == 1 and ui_flags == 1 and copied == words
        records.append({'contact_byte': contact, 'classified_record_words': words,
                        'native_ui_kind': ui_kind, 'native_ui_flags': ui_flags,
                        'classified_record_copied_to_ui_offset': '0x60'})
    # A failed read must not be reported as a fresh valid touch record.
    ioctl_result = -1
    sentinel = bytes([0xa5]) * 48
    u.mem_write(0x60011000, sentinel)
    assert invoke() == 0xffffffff
    assert bytes(u.mem_read(0x60011000, 48)) == sentinel
    rows.append({'header_fixture': header, 'records': records, 'failed_ioctl_returns_error_without_output': True})
report = {'input_sha256': digest, 'procedures': ['0x115acc', '0x14b0a4', '0xf6cd0'], 'cases': rows,
          'limits': ['ioctl payloads and successful responses are virtual; no physical device access.',
                     'Default-mode context and fixed coordinates are fixtures; driver timing, calibration modes and real gesture streams are not qualified.',
                     'Original f6cd0 builds kind1/flag1 UI records with optional inputs NULL. The actual scheduling/caller and screen-to-control coordinate transform are not yet joined to the Home control.']}
(ROOT / 'sources/native-touch-pipeline.json').write_text(json.dumps(report, indent=2) + '\n')
print('Four original touch sequences (12 records) and four ioctl-error controls passed')
