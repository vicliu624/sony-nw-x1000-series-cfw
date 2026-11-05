"""Compare retained Homebrew roots with a UPG; read-only, no device access.

This is a regression inventory, not a hardware pass or a firmware builder.
Executable PT_LOAD segments also contain data: decoded words are observations,
not proof that every changed word is an executed instruction.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from app_registry import ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
from upg import unpack


def digest(data):
    return hashlib.sha256(data).hexdigest()


def root_files(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        result = {}
        for member in archive:
            if not member.isfile():
                continue
            name = member.name.removeprefix('./')
            if name in result:
                raise ValueError('Duplicate root member: ' + name)
            result[name] = archive.extractfile(member).read()
        return result


def word(raw, address):
    image = ELFFile(io.BytesIO(raw))
    matches = [s for s in image.iter_segments() if s['p_type'] == 'PT_LOAD'
               and s['p_vaddr'] <= address and address + 4 <= s['p_vaddr'] + s['p_filesz']]
    if len(matches) != 1:
        raise ValueError('Ambiguous or absent ELF word: ' + hex(address))
    segment = matches[0]
    offset = segment['p_offset'] + address - segment['p_vaddr']
    return raw[offset:offset + 4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--earlier-root', required=True, type=Path)
    parser.add_argument('--current-upg', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # All artifacts stay in ignored local work; never accept a device mount.
    for path in (args.earlier_root, args.current_upg, args.output):
        if not path.resolve().is_relative_to((ROOT / 'work').resolve()):
            raise ValueError('Use local work/ artifacts only')
    if args.output.exists():
        raise ValueError('Refuse to replace an existing comparison')
    earlier_bytes = args.earlier_root.read_bytes()
    current_bytes = args.current_upg.read_bytes()
    _, parts = unpack(current_bytes, require_stock=False)
    earlier = root_files(earlier_bytes)
    current = root_files(gzip.decompress(parts[3]))
    old = earlier['usr/local/bin/SpiderApp']
    new = current['usr/local/lib/x1000-player/SpiderApp']
    changes = []
    for name in sorted(earlier.keys() | current.keys()):
        a, b = earlier.get(name), current.get(name)
        if a != b:
            changes.append(dict(path=name, old_bytes=len(a) if a is not None else None,
                                new_bytes=len(b) if b is not None else None,
                                old_sha256=digest(a) if a is not None else None,
                                new_sha256=digest(b) if b is not None else None))
    decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    boundaries = []
    for address in (0xff3c, 0x10958, 0x3b9e4, 0x718e0, 0x71aa4, 0x71cd8,
                    0x71e6c, 0x71f5c, 0xb04f8, 0xb0500, 0xb0554, 0xb0624, 0x4d61c0):
        a, b = word(old, address), word(new, address)
        decode = lambda data: [' '.join((i.mnemonic, i.op_str)).strip()
                               for i in decoder.disasm(data, address)]
        boundaries.append(dict(address=hex(address), unchanged=a == b,
                               old_hex=a.hex(), new_hex=b.hex(),
                               old_decode=decode(a), new_decode=decode(b)))
    report = dict(earlier_root_sha256=digest(earlier_bytes),
                  earlier_player_sha256=digest(old), current_upg_sha256=digest(current_bytes),
                  current_player_sha256=digest(new), changed_files=changes,
                  applist_equal=earlier['etc/AppList.conf'] == current['etc/AppList.conf'],
                  native_boundaries=boundaries, device_accessed=False, firmware_created=False,
                  physical_regression_reproduced=False,
                  limits=['Earlier artifact hardware acceptance must be established separately.',
                          'Matching request instructions do not qualify downstream retirement or exec.',
                          'External launcher, state and hardware are not present in either root inventory.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(report=str(args.output), changed_files=len(changes),
                         applist_equal=report['applist_equal'],
                         changed_boundaries=[r['address'] for r in boundaries if not r['unchanged']],
                         hardware_qualified=False), indent=2))


if __name__ == '__main__':
    main()
