"""Original event5 callback and activation acknowledgement, virtual transport/fork."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/appproxy').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
elf = ELFFile(io.BytesIO(raw))
syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for initial in (1, 2):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x20000)
    for s in elf.iter_segments():
        if s['p_type'] == 'PT_LOAD':
            u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x10000)
    ctx, app = 0x1ca5c, 0x30001
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    put(0x1ca40, ctx)
    put(ctx, app)
    put(ctx + 4, initial)
    put(ctx + 12, 55)
    put(ctx + 16, 500)
    packets, trace = [], []
    def hook(uc, pc, size, data):
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc == 0xd2c0:
            packet = list(struct.unpack('<6I', uc.mem_read(args[2], 24)))
            assert args[:2] == [500, 55] and args[3] == 24
            assert packet == [24, 0, app, 1, 55, 2]
            packets.append(packet)
            trace.append('activation-op1-value2')
        elif pc == 0xd36c:
            assert packets and args[0] == 500 and args[2] == 16
            uc.mem_write(args[1], struct.pack('<4I', 16, 0, 1, 0))
            put(args[3], 16)
            trace.append('activation-reply')
        elif pc == syms['fork']:
            assert word(ctx + 4) == 2
            result = 321
            trace.append('fork-request')
        elif pc in (0xfbf8, 0xfc38):
            raise AssertionError('Native panic reached')
        elif pc not in (0xea80, 0xeae8, 0x98bc, 0xf840):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_SP, 0x60008000)
    u.reg_write(UC_ARM_REG_LR, 0x50000000)
    u.emu_start(0x95c4, 0x50000000, count=20000)
    assert u.reg_read(UC_ARM_REG_PC) == 0x50000000 and word(0x1c834) == 321
    assert trace == (['activation-op1-value2', 'activation-reply', 'fork-request'] if initial == 1 else ['fork-request'])
    rows.append({'initial_client_state': initial, 'packets': packets, 'trace': trace,
                 'final_client_state': word(ctx + 4)})
report = {'scope': 'Original proxy 0x95c4/c6cc/9e24 with virtual IPC and parent fork branch',
          'appproxy_sha256': digest, 'cases': rows,
          'limits': ['Initial state1 is independently observed at registration cf84/cf8c, not replayed here.',
                     'Transport/reply/locks/logging/fork are mocked; no child is executed.',
                     'Server state write and full activation event delivery are separate checks.']}
(ROOT / 'sources/native-proxy-activation.json').write_text(json.dumps(report, indent=2) + '\n')
print('Two activation cases: registered state1 acknowledges value2 before fork; state2 skips repeat ack')
