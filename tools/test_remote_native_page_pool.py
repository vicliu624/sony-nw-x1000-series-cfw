"""Replay an extra choice descriptor through Sony's original page pool.

No firmware is written. Registration arguments are explicitly supplied, not
claimed to be patched into startup. Callback routing/rendering remain untested.
"""
import io
import hashlib
import json
import struct
import time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from test_native_settings_count import replay

source=ROOT/'work/player-homebrew-review-20261105-1/SpiderApp.player-prepare.analysis-only.elf'
raw=source.read_bytes()
image=ELFFile(io.BytesIO(raw))

def at(address,size,executable=False):
    matches=[s for s in image.iter_segments() if s['p_type']=='PT_LOAD'
             and s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']]
    assert len(matches)==1 and (not executable or matches[0]['p_flags']&1)
    segment=matches[0]
    return segment['p_offset']+address-segment['p_vaddr']

table=raw[at(0x4e692c,156*132):at(0x4e692c,156*132)+156*132]
choice=bytearray(table[29*132:30*132])
# New private resource identity is an experiment; no file/page is installed.
for field in (21,22,32):struct.pack_into('<I',choice,field*4,2)
struct.pack_into('<I',choice,26*4,90000)
address=0x4d8f00
payload=table+choice
offset=at(address,len(payload),True)
assert raw[offset:offset+len(payload)]==bytes(len(payload))
patched=bytearray(raw);patched[offset:offset+len(payload)]=payload
before=replay(raw)
after=replay(bytes(patched),address,157)
assert before['templates']==after['templates'][:156]
added=after['templates'][156]
assert added['id']==156 and added['resource']==90000
assert added['field21']==added['field32']==added['capacity']==2
report=dict(passed=True,original_templates_unchanged=156,extra_choice=added,
            root_view_extension_qualified=False,
            production_blocker='Root view slot156 aliases an existing object at Root+0x2ff8; pool capacity alone is insufficient',
            input_player_sha256=hashlib.sha256(raw).hexdigest(),
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                           for p in ('tools/test_remote_native_page_pool.py','tools/test_native_settings_count.py')},
            original_pool_registration_and_construction=True,
            supplied_registration_arguments=True,firmware_created=False,device_accessed=False,
            limits=['Generic ARM instruction replay; native allocation/copy constructor executes.',
                    'Startup registration callsite is not modified; caller supplies table/count.',
                    'New SWD loading, event callbacks, return navigation and physical GUI remain untested.'])
out=ROOT/'work/remote-page-pool'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
