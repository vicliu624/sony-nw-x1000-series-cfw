"""Original SpiderApp acknowledgement and sysmgrd handler in separate ARM machines."""
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
    manager = runpy.run_path(str(ROOT / 'tools/check_sleep_manager_packets.py'))
    client = runpy.run_path(str(ROOT / 'tools/check_main_activation_ack.py'))
mu, core = manager['u'], manager['core']
put = manager['put']
put(core + 0x503c, 3)
put(core + 0x5164, 0)
for index in range(16):
    put(core + 0x5168 + 4 * index, 0)
put(core + 0x5168, 1)
put(core + 0x516c, 2)
rows = []
for app_id in (1, 2):
    cu = client['machine']()
    ctx = 0x820f68
    for offset, value in ((0, app_id), (4, 2), (8, 9), (12, 55),
                          (16, 500), (20, 30), (40, 123)):
        client['put'](cu, ctx + offset, value)
    exchange = []
    pending_reply = None
    manager['environment']['events'].clear()
    def hook(cpu, pc, size, unused):
        global pending_reply
        args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x268c9c:
            assert pending_reply is None and args[:2] == [500, 55] and args[3] == 20
            request = bytes(cpu.mem_read(args[2], args[3]))
            assert list(struct.unpack('<5I', request)) == [20, 30, app_id, 18, 55]
            mu.mem_write(manager['packet'], request)
            before = len(manager['replies'])
            for register, value in ((UC_ARM_REG_R0, manager['ipc']),
                                    (UC_ARM_REG_R1, manager['packet']),
                                    (UC_ARM_REG_SP, manager['model']['sp']),
                                    (UC_ARM_REG_LR, manager['model']['stop'])):
                mu.reg_write(register, value)
            mu.emu_start(0xffb0, manager['model']['stop'], count=500000)
            assert mu.reg_read(UC_ARM_REG_PC) == manager['model']['stop']
            assert len(manager['replies']) == before + 1
            reply = manager['replies'][-1]
            assert reply == [16, 30, 18, 0]
            pending_reply = struct.pack('<4I', *reply)
            exchange.append(dict(request=list(struct.unpack('<5I', request)), reply=reply))
        elif pc == 0x268d48:
            assert pending_reply is not None and args[0] == 500 and args[2] == 16
            cpu.mem_write(args[1], pending_reply)
            client['put'](cpu, args[3], len(pending_reply))
            pending_reply = None
        elif pc not in (0x337a80, 0x337ae8):
            return
        client['returned'](cpu)
    cu.hook_add(UC_HOOK_CODE, hook)
    assert client['call'](cu, 0x267e28, (ctx,)) == 0
    assert len(exchange) == 1 and pending_reply is None
    assert client['word'](cu, ctx + 20) == 31 and client['word'](cu, ctx + 8) == 2
    power = any(event[0] == 'write' and event[2] == 'S3' for event in manager['environment']['events'])
    assert power == (app_id == 2)
    rows.append(dict(app_id=app_id, exchange=exchange, sleep_requested=power,
                     manager_state=manager['word'](core + 0x503c)))
report = dict(passed=True, SpiderApp_sha256=client['digest'], sysmgrd_sha256=manager['model']['sha'],
    cases=rows, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original client constructs requests; original retained manager constructs replies and runs sleep gating.',
            'In-memory transport replaces IPC; initial active clients, manager preparation/pending IDs, locks, timers and physical power are fixtures.',
            'No complete GUI preparation, kernel suspend, wake or wireless retirement is qualified.'])
(ROOT / 'work/remote-sleep-client-manager-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
