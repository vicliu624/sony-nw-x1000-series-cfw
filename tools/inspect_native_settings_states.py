"""Read pinned Sony UI-state descriptors separately from Pcs controls.

Static inventory only: this does not register an extra state, interpret every
transition byte, execute UI navigation or produce a modified firmware.
"""
import hashlib
import io
import json
import struct
import time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from app_registry import ROOT

source=ROOT/'work/targets-jp/SpiderApp'
raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
image=ELFFile(io.BytesIO(raw))

def read(address,size):
    segments=[s for s in image.iter_segments() if s['p_type']=='PT_LOAD'
              and s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']]
    assert len(segments)==1
    segment=segments[0];offset=segment['p_offset']+address-segment['p_vaddr']
    return raw[offset:offset+size]

def word(address):return struct.unpack('<I',read(address,4))[0]

# Original registration wrapper0x73694 passes count193 and this table.
assert word(0x73698)==0xe3a010c1 and word(0x736bc)==0x3f55d8
rows=[]
for index in range(193):
    address=word(0x3f55d8+index*4)
    fields=struct.unpack('<8I',read(address,32))
    rows.append(dict(state=index+1,descriptor=hex(address),
                     event_fields=[hex(v) for v in fields[:2]],
                     transitions=hex(fields[2]),callbacks=hex(fields[3]),
                     event_map=hex(fields[4]),initializers=hex(fields[5])))
assert rows[1]['descriptor']=='0x41120c'
assert rows[153]['descriptor']=='0x4052e4'
assert word(0x405304)==0x88400 and word(0x405438)==0x88494
report=dict(passed=True,original_state_table='0x3f55d8',original_state_count=193,
            settings_state=rows[1],wireless_confirmation_state=rows[153],
            descriptors=rows,device_accessed=False,firmware_created=False,
            limits=['Static pinned table and original registration instructions only.',
                    'State registration capacity/allocation and transition semantics need executable replay.',
                    'Pcs control-pool capacity176 is not evidence of UI-state capacity.'],
            source_hashes={'tools/inspect_native_settings_states.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
out=ROOT/'work/native-settings-states'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='descriptors'},indent=2))
