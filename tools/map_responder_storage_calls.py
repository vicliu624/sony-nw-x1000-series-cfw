"""Map direct ARM branches to storage-related imports; static local-file research only."""
from pathlib import Path
import hashlib
import io
import json
import struct
import tarfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
    binary = archive.extractfile('./usr/local/bin/Responder').read()
elf = ELFFile(io.BytesIO(binary))
imports = {}
for symbol in elf.get_section_by_name('.dynsym').iter_symbols():
    if symbol['st_shndx'] == 'SHN_UNDEF' and symbol.name in (
            'sync', 'fsync', 'fdatasync', 'mount', 'umount', 'umount2', 'ioctl', 'system'):
        imports[symbol.name] = symbol['st_value']
code = elf.get_section_by_name('.text')
data, start = code.data(), code['sh_addr']
calls = {name: [] for name in imports}
for offset in range(0, len(data) - 3, 4):
    word = struct.unpack_from('<I', data, offset)[0]
    if word >> 28 == 15 or word & 0x0e000000 != 0x0a000000:
        continue
    displacement = word & 0xffffff
    if displacement & 0x800000:
        displacement -= 0x1000000
    address = start + offset
    target = address + 8 + displacement * 4
    for name, imported in imports.items():
        if imported and target == imported:
            calls[name].append({'address': hex(address), 'word': hex(word),
                                'kind': 'BL' if word & 0x01000000 else 'B'})
assert imports['sync'] == 0xbc78 and calls['sync']
word_at = lambda address: struct.unpack_from('<I', data, address - start)[0]
for address, expected in {
    0x5e8f8: 0xeb063ce2,  # validity check through two tail-call wrappers
    0x1edc88: 0xea000c3e,
    0x1f0d88: 0xea000dc9,
    0x1f44b4: 0xe5900000,  # read descriptor from handle
    0x5e914: 0xeb063cda,  # close through wrappers
    0x1edc84: 0xea000c72,
    0x1f0e54: 0xea000d9a,
    0x1f44d0: 0xebf85d0d,  # close@plt
    0x5e904: 0xebfeb4db,
    0x5e90c: 0xeafeb4d9,
}.items():
    assert word_at(address) == expected, hex(address)
report = {'responder_sha256': hashlib.sha256(binary).hexdigest(),
          'imports': {name: hex(value) for name, value in imports.items()},
          'direct_branch_candidates': calls, 'physical_device_access': False,
          'reviewed_sync_wrapper': {
              'entry': '0x5e8f0',
              'descriptor_validity_path': ['0x1edc88', '0x1f0d88', '0x1f44b4'],
              'descriptor_close_path': ['0x1edc84', '0x1f0e54', '0x1f44c4', 'close@0xb90c'],
              'sync_sites': ['0x5e904', '0x5e90c'],
              'finding': 'Handle validity/close wrapper followed by two sync calls; not evidence of unmount.',
              'usb_event_reachability_verified': False,
          },
          'limits': ['Branch candidates only: ARM data embedded in .text may resemble instructions.',
                     'Indirect calls and storage operations inside other functions/libraries are not covered.',
                     'sync calls do not establish unmount, USB export order, or reachability from USB events.']}
(ROOT / 'sources/native-responder-storage-call-map.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'imports': report['imports'], 'candidate_counts': {k: len(v) for k, v in calls.items()}}, indent=2))
