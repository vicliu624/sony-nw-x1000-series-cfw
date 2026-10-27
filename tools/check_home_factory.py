"""Replay stock metadata binding and view construction; pool/libc mocked.

Modified-count cases change only Unicorn RAM, never the source ELF or firmware.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', action='store_true')
args = parser.parse_args()
candidate = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text()) if args.candidate else None
raw = (ROOT / (candidate['artifact'] if candidate else 'work/targets-jp/SpiderApp')).read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == (candidate['candidate_sha256'] if candidate else '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85')
elf = ELFFile(io.BytesIO(raw))
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
low = min(s['p_vaddr'] for s in segments) & ~4095
high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
rows = []
for menu, original in [(0, 10), (1, 9)]:
    if candidate:
        original += 1
    for additional in ((0,) if candidate else (0, 1)):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(low, high - low)
        for s in segments:
            u.mem_write(s['p_vaddr'], s.data())
        u.mem_map(0x50000000, 4096)
        u.mem_map(0x60000000, 0x40000)
        word = lambda a: struct.unpack('<I', u.mem_read(a, 4))[0]
        # Actual pointer loaded by AppGuiBrowser initialization, not a nearby field.
        base = word(0x2acd0)
        assert base == 0x4e692c
        count = original + additional
        for field in (21, 22, 32):
            address = base + menu * 132 + field * 4
            assert word(address) == original
            u.mem_write(address, struct.pack('<I', count))
        manager, output = 0x60010000, 0x60020000
        def hook(uc, pc, size, data):
            if pc == 0x1094f0:
                uc.reg_write(UC_ARM_REG_R0, manager)
            elif pc == 0x1047b4:
                uc.mem_write(uc.reg_read(UC_ARM_REG_R1), b'\0\0')
                uc.reg_write(UC_ARM_REG_R0, 0)
            elif pc == symbols['memset']:
                dst, value, length = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
                uc.mem_write(dst, bytes([value & 255]) * length)
            elif pc == symbols['memcpy']:
                dst, src, length = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
                uc.mem_write(dst, bytes(uc.mem_read(src, length)))
            else:
                return
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, hook)
        def call(address, arg0, arg1):
            for reg, value in [(UC_ARM_REG_R0, arg0), (UC_ARM_REG_R1, arg1),
                               (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
                u.reg_write(reg, value)
            u.emu_start(address, 0x50000000, count=100000)
            assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        call(0x10e754, base, 156)
        assert word(0x75cef8) == base and word(0x75cefc) == 156
        call(0x10e558, menu, output)
        assert u.reg_read(UC_ARM_REG_R0) == 0
        view = word(output)
        assert view == manager + 4
        assert word(view + 0x5c) == 3
        assert word(view + 0x4c) == count
        assert word(view + 0x90) == count
        assert word(view + 0xa4) == count
        call(0xf1ac0, 0x60024000, view + 0x54)
        assert word(0x60024000 + 0xb34) == 1
        rows.append({'menu': menu, 'additional_in_emulator_ram': additional,
                     'descriptor_words_0x00_to_0x50': [hex(word(view + offset)) for offset in range(0, 0x54, 4)],
                     'selected_subtype': word(0x60024000 + 0xb34),
                     'layout_parameter_0x5c': word(view + 0x5c),
                     'counts': {hex(offset): word(view + offset) for offset in (0x4c, 0x90, 0xa4)}})
result = {
    'scope': ('Patched file metadata with original binder/constructor' if candidate else 'Original metadata binder and constructor; additions only in emulator RAM') + '; pool slot and libc mocked',
    'SpiderApp_sha256': digest, 'metadata_base': '0x4e692c',
    'record_bytes': 132, 'count_field_indices': [21, 22, 32],
    'binder': '0x10e754', 'constructor': '0x10e558', 'cases': rows,
    'limits': ['Does not instantiate or render the live widget or test its hitboxes.',
               'Modified-count cases are evidence of descriptor propagation only.',
               'Text, texture mapping, input bounds and APF entry must still be extended together.',
               'No source binary, UPG, physical storage or original metadata file changed.'],
}
(ROOT / ('sources/native-home-candidate-factory.json' if candidate else 'sources/native-home-factory.json')).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
