"""Check stock Home label collections, menu metadata and texture order."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import re
import struct
import sys
import tarfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.resources import parse_stx

archive = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', action='store_true')
args = parser.parse_args()
candidate = json.loads((ROOT / 'work/home-entry-candidate/candidate.json').read_text()) if args.candidate else None
binary = (ROOT / (candidate['artifact'] if candidate else 'work/targets-jp/SpiderApp')).read_bytes()
assert hashlib.sha256(binary).hexdigest() == (candidate['candidate_sha256'] if candidate else '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85')
elf = ELFFile(io.BytesIO(binary))
segments = [(s['p_vaddr'], s.data()) for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
def read(address, count):
    return next(data[address-base:address-base+count] for base, data in segments
                if base <= address and address + count <= base + len(data))
base = struct.unpack('<I', read(0x2acd0, 4))[0]
assert base == 0x4e692c
rows = []
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
    texts = {}
    for language in ('en', 'jp', 'cs'):
        name = './usr/local/share/gemini/res/stx/ucs2-dev-' + language + '.stx'
        texts[language] = parse_stx((ROOT/'work/home-entry-candidate/overlay'/name[2:]).read_bytes() if candidate and candidate.get('caption_tid') is not None else tar.extractfile(name).read())
    for menu, collection, texture_address, expected_tids in [
        (0, 10, 0x41669c, [6045, 6046, 6500, 6047, 6048, 6049, 6050, 6051, 6052, 6053]),
        (1, 11, 0x416678, [6052, 6045, 6500, 6047, 6048, 6049, 6053, 6051, 6050]),
    ]:
        record = struct.unpack('<33I', read(base + menu * 132, 132))
        assert record[26] == collection
        name = './usr/local/share/gemini/res/swd/ucs2-dev-sid-000-' + str(collection) + '.swd'
        if candidate:
            data = (ROOT / 'work/home-entry-candidate/overlay' / name[2:]).read_bytes()
            expected_tids.append(candidate.get('caption_tid',264))
            texture_address = candidate['symbols']['hb_home_icons_10' if menu == 0 else 'hb_home_icons_9']
        else:
            data = tar.extractfile(name).read()
        entries = [(int(a), int(b)) for a, b in re.findall(rb'^tid\.(\d+):\s*"tid-(\d+)"', data, re.M)]
        assert [i for i, tid in entries] == list(range(len(expected_tids)))
        assert [tid for i, tid in entries] == expected_tids
        assert all(record[field] == len(entries) for field in (21, 22, 32))
        textures = struct.unpack('<' + str(len(entries)) + 'I', read(texture_address, len(entries) * 4))
        rows.append({'menu': menu, 'collection': collection, 'path': name[2:],
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'items': [{'index': index, 'tid': tid, 'texture': textures[index],
                                'labels': {lang: table[tid] for lang, table in texts.items()}}
                               for index, tid in entries]})
result = {'scope': 'Pinned rootfs SWD/STX and original metadata/texture tables; read only',
          'input_sha256': hashlib.sha256(binary).hexdigest(),
          'input': 'patched ELF and SWD overlays' if candidate else 'original ELF/rootfs',
          'metadata_base': hex(base), 'collection_field': 26, 'menus': rows,
          'limits': ['Label presence is not device rendering qualification.',
                     'No label collection, language table, firmware or storage is modified.']}
(ROOT / ('sources/native-home-candidate-labels.json' if candidate else 'sources/native-home-labels.json')).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print('Both Home label collections match their counts and texture order' + (' (candidate 11 / 10).' if candidate else ' (stock 10 / 9).'))
