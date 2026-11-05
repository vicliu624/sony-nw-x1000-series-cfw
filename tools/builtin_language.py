"""Pinned native language Settings edit for source-built Japanese 1.11."""
import hashlib
import io
import struct
from elftools.elf.elffile import ELFFile

BASE_SHA = 'ea106d7d362793fe39450673b79e3cf77dbdd00bc1ba573b7e8f854d56dc53e0'
SETTINGS_SHA = '4ca0755d3fe3322cf14c60ccbc456a344d5293e1cbd59665a1c2b9ebd11bbbd8'

def enable_settings(raw):
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError('Pinned source-built Homebrew base required')
    elf = ELFFile(io.BytesIO(raw))
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    def offset(address, size):
        matches = [s for s in segments if s['p_vaddr'] <= address
                   and address + size <= s['p_vaddr'] + s['p_filesz']]
        if len(matches) != 1:
            raise ValueError('Settings range must have one mapping')
        s = matches[0]
        return int(s['p_offset'] + address - s['p_vaddr'])
    table = 0x3f611c
    records = [struct.unpack_from('<5I', raw, offset(table + i * 20, 20)) for i in range(95)]
    index = next(i for i, r in enumerate(records) if r[0] == 2)
    if records[index][1:3] != (0x3f6fc4, 10):
        raise ValueError('Japanese Settings descriptor mismatch')
    original = struct.unpack_from('<10I', raw, offset(0x3f6fc4, 40))
    if 0xf80000 in original or 0xfa0000 not in original:
        raise ValueError('Original Japanese Settings list mismatch')
    address = 0x4d8000
    payload = struct.pack('<11I', *original, 0xf80000)
    at = offset(address, len(payload))
    aliases = []
    for s in segments:
        lo, hi = max(at, s['p_offset']), min(at + len(payload), s['p_offset'] + s['p_filesz'])
        if lo < hi:
            aliases.append((s['p_vaddr'] + lo - s['p_offset'], s['p_flags']))
    if aliases != [(address, 5)] or raw[at:at + len(payload)] != bytes(len(payload)):
        raise ValueError('Settings slot occupied or aliased')
    result = bytearray(raw)
    result[at:at + len(payload)] = payload
    struct.pack_into('<II', result, offset(table + index * 20 + 4, 8), address, 11)
    if hashlib.sha256(result).hexdigest() != SETTINGS_SHA:
        raise ValueError('Built-in Settings output identity mismatch')
    return bytes(result)
