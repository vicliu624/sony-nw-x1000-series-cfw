"""Locate stock Main preparation/status completion actions; no wake inference."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import struct
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/check_main_activation_ack.py'))
u = model['machine']()
hits = []
def hook(cpu, pc, size, unused):
    if pc in model['actions']:
        hits.append(pc)
        model['returned'](cpu)
u.hook_add(UC_HOOK_CODE, hook)
rows = []
for mode, states in ((1, 1), (2, 2), (3, 7)):
    for state in range(1, states + 1):
        for event in (0x41000d, 0x410006, 0x410001, 0x410010):
            context = bytearray(32)
            context[0], context[1], context[13] = mode, state, 6
            struct.pack_into('<I', context, 4, 0x3ef680)
            u.mem_write(0x60010000, bytes(context))
            hits.clear()
            result = model['call'](u, 0x17c608, (0x60010000, event, 0, 0))
            assert result == 0 and len(hits) == 1
            expected = {
                0x41000d: {(2, 2): 0x6159c, (3, 4): 0x618a4},
                0x410006: {(2, 1): 0x614e4, (2, 2): 0x6163c,
                           (3, 4): 0x61c44, (3, 7): 0x61928},
                0x410001: {(3, 1): 0x61674, (3, 2): 0x61674,
                           (3, 3): 0x61674, (3, 4): 0x61674,
                           (3, 5): 0x61ca8, (3, 7): 0x61674},
                0x410010: {(2, 2): 0x61540, (3, 4): 0x61a1c},
            }.get(event, {}).get((mode, state), 0x613cc)
            assert hits == [expected]
            rows.append(dict(mode=mode, state=state, event=hex(event), action=hex(hits[0])))
report = dict(passed=True, SpiderApp_sha256=model['digest'], cases=rows,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original dispatcher and action selection execute against supplied mode/state contexts.',
            'Selected action bodies are intercepted; no manager acknowledgement or hardware sleep is inferred.'])
(ROOT / 'work/remote-sleep-dispatch-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
