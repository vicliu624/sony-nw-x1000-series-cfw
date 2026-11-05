"""Bounded original core power-event restoration; transport remains unqualified."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/check_sleep_manager_packets.py'))
u, core = model['u'], model['core']
calls, notices = [], []
def hook(cpu, pc, size, unused):
    if pc not in (0x13c54, 0x16b10, 0x6001ffd0):
        return
    args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
    if pc == 0x6001ffd0:
        assert args[1] == 99
        notices.append(list(struct.unpack('<3I', cpu.mem_read(args[0], 12))))
    else:
        calls.append([hex(pc), args[0]])
    cpu.reg_write(UC_ARM_REG_R0, 0)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE, hook)
model['put'](core + 0x503c, 4)
model['put'](core + 0x51b4, 0x6001ffd0)
model['put'](core + 0x51b8, 99)
event = 0x60007000
u.mem_write(event, struct.pack('<3I', 2, 1, 0))
for register, value in ((UC_ARM_REG_R0, event), (UC_ARM_REG_R1, core),
                        (UC_ARM_REG_SP, model['model']['sp']), (UC_ARM_REG_LR, model['model']['stop'])):
    u.reg_write(register, value)
u.emu_start(0xb80c, model['model']['stop'], count=500000)
assert u.reg_read(UC_ARM_REG_PC) == model['model']['stop']
assert model['word'](core + 0x503c) == 1
assert notices == [[2, 1, 0]], notices
assert ['0x13c54', core + 0x4214] in calls
report = dict(passed=True, sysmgrd_sha256=model['model']['sha'],
    supplied_event=[2, 1, 0], initial_state=4, final_state=1,
    callback_notices=notices, calls=calls,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original core event handler at0xb80c executes with supplied state4 and event2/reason1.',
            'Power-event production, timer/helper calls and callback delivery are fixtures.',
            'Internal callback type2 is not assumed to equal APF wire opcode2; that conversion is not executed.',
            'No physical wake, application restoration or remote rearm is qualified.'])
(ROOT / 'work/remote-manager-power-restore-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
