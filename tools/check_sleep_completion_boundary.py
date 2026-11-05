"""Execute original completion actions; do not infer a manager acknowledgement."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR

ROOT = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/check_spider_restore_dispatch.py'))
u = model['u']
events = []

def hook(cpu, pc, size, unused):
    if pc in (0xff5c, 0x33b83c, 0x33b918, 0x17c42c, 0xe600, 0xb174c, 0xb03e8):
        cpu.reg_write(UC_ARM_REG_R0, 0)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        return
    if pc not in (0xb17c4, 0xe5f4, 0xf5c8, 0xe684):
        return
    events.append([hex(pc), cpu.reg_read(UC_ARM_REG_R0)])
    cpu.reg_write(UC_ARM_REG_R0, 0x6001e000 if pc == 0xe5f4 else 0)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

u.hook_add(UC_HOOK_CODE, hook)
rows = []
for entry, expected in (
    (0x61500, ['0xb17c4', '0xe5f4', '0xf5c8']),
    (0x619d8, ['0xe5f4', '0xe684', '0xb17c4']),
):
    events.clear()
    model['queued'].clear()
    result = model['call'](entry, ())
    assert result == 1
    assert [event[0] for event in events] == expected, events
    if entry == 0x61500:
        assert events[-1][1] == 0x6001e000
        assert not model['queued']
    else:
        assert events[1][1] == 0x6001e000
        assert model['queued'] == [[0x42001a, 0, 0, 0]]
    rows.append(dict(entry=hex(entry), calls=list(events),
                     queued=[list(event) for event in model['queued']], result=result))

model['queued'].clear()
u.mem_write(0x60010004, struct.pack('<I', 5))
model['call'](0x10ee4, (0x60010000,))
assert model['queued'] == [[0x410001, 0, 0, 0]], model['queued']
command5_events=[list(event) for event in model['queued']]
context=bytearray(32);context[0]=3;context[1]=4;context[13]=6
struct.pack_into('<I',context,4,0x3ef680);u.mem_write(0x60010000,bytes(context))
model['queued'].clear();events.clear()
model['call'](0x17c608,(0x60010000,0x410010,0,0))
restored_state=list(u.mem_read(0x60010000,2))
assert restored_state==[3,1],restored_state
restore_calls=list(events);restore_queue=[list(event) for event in model['queued']]
prepare_transitions=[]
for before,after in (([2,1],[2,2]),([3,7],[3,4])):
 context[0],context[1]=before;u.mem_write(0x60010000,bytes(context))
 model['call'](0x17c608,(0x60010000,0x410006,0,0))
 actual=list(u.mem_read(0x60010000,2));assert actual==after,(before,actual)
 prepare_transitions.append(dict(before=before,after=actual,event='0x410006'))
report = dict(passed=True, SpiderApp_sha256=model['digest'], cases=rows,
    command5_completion_events=command5_events,
    command15_main_transition=dict(before=[3,4],event='0x410010',after=restored_state,
                                  calls=restore_calls,queued=restore_queue),
    prepare_main_transitions=prepare_transitions,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original action instructions execute; media completion, environment getter/setter and environment continuation are intercepted.',
            'No APF acknowledgement, manager transport, hardware suspend or full event consumer is qualified.'])
destination = ROOT / 'work/remote-sleep-completion-latest.json'
destination.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
