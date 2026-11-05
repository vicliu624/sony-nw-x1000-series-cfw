"""Replay original prepare/wake IPC producers with explicit transport fixtures."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

ROOT = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path(str(ROOT / 'tools/check_main_activation_ack.py'))
rows = []
for entry, opcode, length in ((0x267d50, 19, 24), (0x267e28, 18, 20)):
    for initial_state in (0, 1, 2):
        for reply_status in (0, 0x1d04):
            u = model['machine']()
            ctx = 0x820f68
            packets = []
            for offset, value in ((0, 1), (4, initial_state), (8, 9), (12, 55),
                                  (16, 500), (20, 7), (40, 123)):
                model['put'](u, ctx + offset, value)
            def hook(cpu, pc, size, unused):
                args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
                if pc == 0x268c9c:
                    assert args[0] == 500 and args[3] == length
                    packet = list(struct.unpack('<' + 'I' * (length // 4), cpu.mem_read(args[2], length)))
                    assert packet == [length, 7, 1, opcode, 55] + ([0] if opcode == 19 else [])
                    packets.append(packet)
                elif pc == 0x268d48:
                    assert args[0] == 500 and args[2] == 16
                    cpu.mem_write(args[1], struct.pack('<4I', 16, 7, opcode, reply_status))
                    model['put'](cpu, args[3], 16)
                elif pc not in (0x337a80, 0x337ae8):
                    return
                model['returned'](cpu)
            u.hook_add(UC_HOOK_CODE, hook)
            result = model['call'](u, entry, (ctx, 0))
            admitted = initial_state != 0 and (opcode != 19 or initial_state != 1)
            assert result == (reply_status if admitted else 0x1d09)
            assert len(packets) == int(admitted)
            assert model['word'](u, ctx + 20) == 7 + int(admitted)
            assert model['word'](u, ctx + 8) == (2 if opcode == 18 and admitted and not reply_status else 9)
            rows.append(dict(entry=hex(entry), initial_state=initial_state,
                             reply_status=reply_status, packets=packets, result=result))
report = dict(passed=True, SpiderApp_sha256=model['digest'], cases=rows,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original client packet construction, admission, sequence and reply handling execute.',
            'Mutexes and transport replies are modeled; no manager receiver or hardware sleep executes.'])
(ROOT / 'work/remote-sleep-client-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
