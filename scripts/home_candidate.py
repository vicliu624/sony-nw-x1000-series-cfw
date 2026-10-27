"""Pinned Japanese 1.11 ELF analysis candidate; no UPG/device operations."""
import hashlib
import io
import struct
from elftools.elf.elffile import ELFFile

STOCK_SHA = '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
INSERT = 0x4ce004
PAYLOAD_ADDRESS = 0x4d6010
INSERT_BYTES = 0x8000


def make_candidate(raw: bytes, payload: bytes, symbols: dict[str, int]):
    if hashlib.sha256(raw).hexdigest() != STOCK_SHA:
        raise ValueError('Requires the pinned Japanese 1.11 SpiderApp')
    elf = ELFFile(io.BytesIO(raw))
    segments = list(elf.iter_segments())
    loads = [s for s in segments if s['p_type'] == 'PT_LOAD']
    if len(loads) != 2:
        raise ValueError('Unexpected load segments')
    code, data = loads
    code_end = code['p_vaddr'] + code['p_memsz']
    if (code['p_offset'] != 0 or code['p_filesz'] != code['p_memsz'] or
        code['p_filesz'] != INSERT or data['p_vaddr'] - code_end != INSERT_BYTES or
        data['p_align'] != INSERT_BYTES):
        raise ValueError('Unexpected ELF gap/alignment')
    prefix = PAYLOAD_ADDRESS - code_end
    if not payload or prefix < 0 or prefix + len(payload) > INSERT_BYTES:
        raise ValueError('Payload does not fit the existing virtual gap')
    for name in ('hb_home_select', 'hb_original_home', 'hb_home_icons_10', 'hb_home_icons_9',
                 'hb_switch_name', 'hb_switch_args', 'hb_switch_return', 'hb_code_end'):
        if not PAYLOAD_ADDRESS <= symbols[name] < PAYLOAD_ADDRESS + len(payload):
            raise ValueError('Payload symbol outside mapped bytes: ' + name)
    edits = []
    original = bytearray(raw)
    def offset(address):
        return next(s['p_offset'] + address - s['p_vaddr'] for s in loads
                    if s['p_vaddr'] <= address and address + 4 <= s['p_vaddr'] + s['p_filesz'])
    def word(address, before, after):
        off = offset(address)
        if struct.unpack_from('<I', original, off)[0] != before:
            raise ValueError('Unexpected original word at ' + hex(address))
        struct.pack_into('<I', original, off, after)
        edits.append({'address': hex(address), 'before': hex(before), 'after': hex(after)})
    def branch(address, before, symbol):
        delta = symbols[symbol] - (address + 8)
        if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
            raise ValueError('Hook branch outside ARM B range')
        word(address, before, 0xea000000 | ((delta >> 2) & 0xffffff))
    branch(0x737ec, 0xe92d40f0, 'hb_home_select')
    branch(0xb04b0, 0xea00000d, 'hb_switch_name')
    branch(0xb0518, 0xeafffff3, 'hb_switch_args')
    branch(0xb04ec, 0xe28dd010, 'hb_switch_return')
    word(0xb58fc, 0xe3550009, 0xe355000a)
    word(0xb5974, 0xe3550008, 0xe3550009)
    word(0xb5984, 0x41669c, symbols['hb_home_icons_10'])
    word(0xb5988, 0x416678, symbols['hb_home_icons_9'])
    for menu, count in ((0, 10), (1, 9)):
        for field in (21, 22, 32):
            word(0x4e692c + menu * 132 + field * 4, count, count + 1)
    block = bytes(prefix) + payload + bytes(INSERT_BYTES - prefix - len(payload))
    out = original[:INSERT] + block + original[INSERT:]
    header = elf.header
    # All original virtual addresses and headers remain. File data after the
    # insertion shifts by the original 32KB segment alignment.
    for index, segment in enumerate(segments):
        ph = header['e_phoff'] + index * header['e_phentsize']
        if segment['p_type'] == 'PT_LOAD' and segment['p_offset'] == 0:
            struct.pack_into('<II', out, ph + 16, segment['p_filesz'] + INSERT_BYTES,
                             segment['p_memsz'] + INSERT_BYTES)
        elif segment['p_offset'] >= INSERT:
            struct.pack_into('<I', out, ph + 4, segment['p_offset'] + INSERT_BYTES)
    shoff = header['e_shoff']
    moved_shoff = shoff + (INSERT_BYTES if shoff >= INSERT else 0)
    struct.pack_into('<I', out, 32, moved_shoff)
    for index, section in enumerate(elf.iter_sections()):
        if section['sh_offset'] >= INSERT:
            struct.pack_into('<I', out, moved_shoff + index * header['e_shentsize'] + 16,
                             section['sh_offset'] + INSERT_BYTES)
    candidate = bytes(out)
    check = ELFFile(io.BytesIO(candidate))
    assert check.header['e_entry'] == header['e_entry']
    assert check.header['e_phnum'] == header['e_phnum']
    after_segments = list(check.iter_segments())
    for before, after in zip(segments, after_segments):
        for field in ('p_type', 'p_vaddr', 'p_paddr', 'p_flags', 'p_align'):
            assert before[field] == after[field]
        if after['p_type'] == 'PT_LOAD':
            assert after['p_offset'] % after['p_align'] == after['p_vaddr'] % after['p_align']
        if before['p_type'] in ('PT_NOTE', 'PT_ARM_EXIDX', 'PT_GNU_EH_FRAME'):
            assert before.data() == after.data()
            assert before['p_filesz'] == after['p_filesz']
        if before['p_type'] == 'PT_PHDR':
            assert before['p_offset'] == after['p_offset']
            assert before['p_filesz'] == after['p_filesz']
    assert len(candidate) == len(raw) + INSERT_BYTES
    grown_loads = [s for s in after_segments if s['p_type'] == 'PT_LOAD']
    assert grown_loads[0]['p_vaddr'] + grown_loads[0]['p_memsz'] == grown_loads[1]['p_vaddr']
    # Verify every original loaded byte at the same VA, excluding only recorded
    # patches and ELF header/program header fields whose offsets/sizes changed.
    allowed = set(range(32, 36))
    for index in range(header['e_phnum']):
        ph = header['e_phoff'] + index * header['e_phentsize']
        allowed.update(range(ph + 4, ph + 8))
        allowed.update(range(ph + 16, ph + 24))
    for edit in edits:
        allowed.update(range(offset(int(edit['address'], 16)), offset(int(edit['address'], 16)) + 4))
    for before, after in zip(segments, after_segments):
        if before['p_type'] != 'PT_LOAD':
            continue
        start = before['p_offset']
        old = raw[start:start + before['p_filesz']]
        new = candidate[after['p_offset']:after['p_offset'] + before['p_filesz']]
        assert all(a == b or start + i in allowed for i, (a, b) in enumerate(zip(old, new)))
    return candidate, {'stock_sha256': STOCK_SHA, 'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
                       'growth_bytes': INSERT_BYTES, 'payload_bytes': len(payload),
                       'payload_address': hex(PAYLOAD_ADDRESS), 'edits': edits,
                       'original_load_addresses_preserved': True,
                       'original_notes_and_unwind_tables_preserved': True,
                       'physical_device_access': False, 'firmware_package_created': False}
