"""Replay stock IP event handling. Synthetic events; no radio, IPC or device.

Initial in-flight states and pending command are supplied, not reached through
AP selection. Original instructions choose the resulting state and API reply.
"""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/qqmusic-wifi/cnmgr_daemon').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
results = []
for label, initial, event, expected in [('IP start success', 7, 0, 8), ('IP start failure', 7, 1, 14), ('IP stop completed', 9, 2, 10)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x100000)
    for segment in ELFFile(io.BytesIO(raw)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x2000000, 0x40000)
    obj, end = 0x2001000, 0x2000100
    def get(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
    def put(a, n): u.mem_write(a, struct.pack('<I', n))
    put(obj + 0xa09c, initial)
    put(obj + 0xa080, 91)
    put(obj + 8, 92)
    put(obj + 20, 7)
    trace = []
    def hook(uc, pc, size, unused):
        r0, r1, r2 = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        result = 0
        if pc == end:
            uc.emu_stop(); return
        elif pc == 0x9fac:  # read: provide only the synthetic IP event
            assert r0 == 91 and r2 == 4
            put(r1, event); result = 4
        elif pc == 0x9ae4:  # write: capture reply, never perform IPC
            assert r0 == 92 and r2 == 1012
            trace.append({'operation': 'API reply', 'status': get(r1), 'state_at_reply': get(obj + 0xa09c)})
            result = r2
        elif pc == 0x9a6c:
            uc.mem_write(r0, bytes([r1 & 255]) * r2); result = r0
        elif pc in (0xa14c, 0xa760, 0x2327c):  # logging only
            pass
        elif pc in (0x11934, 0x1118c):
            trace.append({'operation': 'IP stop request' if pc == 0x11934 else 'WLAN disconnect request', 'state': get(obj + 0xa09c), 'modeled_return': 0})
        else:
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def reject_syscall(*args): raise AssertionError('Unexpected system instruction')
    u.hook_add(UC_HOOK_CODE, hook)
    u.hook_add(UC_HOOK_INTR, reject_syscall)
    for reg, value in ((UC_ARM_REG_R0, obj), (UC_ARM_REG_SP, 0x203f000), (UC_ARM_REG_LR, end)):
        u.reg_write(reg, value)
    u.emu_start(0xb538, end, count=20000)
    assert u.reg_read(UC_ARM_REG_PC) == end
    assert get(obj + 0xa09c) == expected
    if event == 0:
        assert trace == [{'operation': 'API reply', 'status': 0, 'state_at_reply': 7}]
        assert get(obj + 20) == 0
    else:
        assert len(trace) == 1 and get(obj + 20) == 7
    results.append({'case': label, 'initial_state': initial, 'event': event, 'final_state': expected, 'trace': trace})
report = {'passed': True, 'daemon_sha256': digest, 'cases': results, 'physical_device_or_ipc': False,
          'limits': ['Initial states and pending command supplied synthetically; AP selection and reachability not proven.',
                     'IP/WLAN operations return modeled success; no actual connection, DHCP or disconnect executed.',
                     'This proves event completion ordering, not the full application lifecycle.']}
(ROOT / 'sources/stock-wifi-ip-completion.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
