"""Validate the recovered style structure against both shipped copies."""
from pathlib import Path
from collections import Counter
import hashlib
import io
import json
import sys
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.style import parse_style, RECORD_BYTES, CHILD_BYTES

data = (ROOT / 'work/resource-analysis/style.dat').read_bytes()
assert hashlib.sha256(data).hexdigest() == '84c29fb6747390c92ac28e9b3cab3410c2af28d40d12da83890b8c2d189a6635'
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
address = 0x4F80CC
embedded = None
for segment in elf.iter_segments():
    start = segment['p_vaddr']
    if segment['p_type'] == 'PT_LOAD' and start <= address and address + len(data) <= start + segment['p_filesz']:
        embedded = segment.data()[address - start:address - start + len(data)]
        break
assert embedded == data, 'External and embedded layout bytes differ'
layouts = parse_style(data)
assert len(layouts) == 204
counts = Counter(child.kind for layout in layouts for child in layout.children)
result = {
    'scope': 'Pinned shipped layout file and embedded bytes, interpreted using REA loader/builder evidence; no rendering or patching',
    'style_sha256': hashlib.sha256(data).hexdigest(),
    'bytes': len(data), 'layout_count': len(layouts), 'record_bytes': RECORD_BYTES,
    'child_slots': 32, 'child_bytes': CHILD_BYTES,
    'active_children': sum(counts.values()),
    'child_kind_counts': {str(k): v for k, v in sorted(counts.items())},
    'embedded_address': hex(address), 'embedded_identical': True,
    'loader': '0x108c58', 'builder': '0xf577c',
    'limits': ['Home layout identity not established by this check.',
               'Stored geometry is not final hitbox geometry; runtime offsets and alignment apply.',
               'No writer, changed style file, firmware or physical device operation.'],
}
(ROOT / 'sources/native-style-table.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
