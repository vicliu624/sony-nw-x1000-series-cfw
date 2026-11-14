"""Original manager sleep acknowledgments, with two explicitly pending clients."""
from pathlib import Path
import hashlib
import json
from check_sleep_storage_paths import SleepManager

ROOT = Path(__file__).resolve().parents[1]
manager = SleepManager()
core = manager.core
manager.put(core + 0x503c, 3)
manager.put(core + 0x5164, 0)
manager.put(core + 0x5168, 55)
manager.put(core + 0x516c, 77)
rows = []
for client in (55, 77):
    before = len(manager.events)
    assert manager.call(0xb1f8, core, client) == 0
    events = manager.events[before:]
    pending = [manager.word(core + 0x5168 + i * 4) for i in range(16)]
    sleep = any(event[0] == 'write' and event[2] == 'S3' for event in events)
    assert sleep == (client == 77)
    assert pending == ([0, 77] + [0] * 14 if client == 55 else [0] * 16)
    rows.append(dict(client_ack=client, pending_after=pending, power_write=sleep,
                     core_state_after=manager.word(core + 0x503c), events=events))
report = dict(passed=True, sysmgrd_sha256=manager.digest, cases=rows,
              scope='Original b1f8/aa40/aa74 clears two supplied pending clients in one manager instance; after final ack original aaac/129d0/17894 executes. Caller/client identities and initial state supplied; transport, policy, timer, physical power virtual. Not real scheduling or application completion.',
              physical_device_access=False,
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
out = ROOT / 'work/stock-sleep'
out.mkdir(parents=True, exist_ok=True)
(out / 'prepare-ack-flow.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
