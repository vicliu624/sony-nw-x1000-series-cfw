"""Run original command prologue and admission gates for channel command001d.

All radio code is original and hash-bound; only response copying is substituted.
Synthetic state bytes are NOT proof of real-state transitions or RF operation.
"""
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R6, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR
from marvell_firmware import parse

ROOT = Path(__file__).resolve().parents[1]
image = (ROOT/'work/targets-jp/sd8686.bin').read_bytes()
digest = hashlib.sha256(image).hexdigest()
assert digest == '08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records = parse(image)


def replay(state, busy, flag):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for address, size in ((0, 0x20000), (0xc0000000, 0x20000), (0x04000000, 0x2000), (0x200000, 0x10000)):
        cpu.mem_map(address, size)
    for record in records:
        if record.command == 1:
            cpu.mem_write(record.address, record.data)
    cpu.mem_write(0xc00155b8, struct.pack('<6H', 0x1d, 48, 7, 0, 0, 0)+bytes(36))
    cpu.mem_write(0xc0007859, bytes([state]))
    cpu.mem_write(0xc000edf4, bytes([busy]))
    cpu.mem_write(0xc001452a, bytes([flag]))
    cpu.reg_write(UC_ARM_REG_SP, 0x208000)
    trace, copies = [], []

    def hook(u, address, size, data):
        trace.append(address)
        if address in (0x8c9a, 0x8110, 0x9a46):
            u.emu_stop()
        elif address == 0x9c90:
            dest, source, count = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            assert count in (8, 48)
            u.mem_write(dest, bytes(u.mem_read(source, count)))
            copies.append(count)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x8079, 0x9b40, count=1500)
    stop = trace[-1]
    admitted = stop == 0x8c9a
    assert admitted == (state != 2 and not busy)
    status = struct.unpack('<H', cpu.mem_read(0xc00155b8+6, 2))[0]
    if state == 2:
        assert stop == 0x8110 and status == 2 and 0x3668 in trace
    elif busy:
        assert stop == 0x9a46 and cpu.reg_read(UC_ARM_REG_R6) == 4
    elif not flag:
        assert 0x4b80 in trace  # original feature/command whitelist ran
    return {'radio_state_byte': state, 'busy_byte': busy, 'feature_flag': flag,
            'admitted_to_channel_handler': admitted, 'stop': hex(stop),
            'response_status_if_written': status, 'copy_sizes': copies}


cases = [replay(state, busy, flag) for state in (0, 1, 2) for busy in (0, 1) for flag in (0, 1)]
out = ROOT/'work/espnow-radio-admission'
out.mkdir(parents=True, exist_ok=True)
report = {'passed': True, 'image_sha256': digest, 'cases': cases,
          'entry': '0x8078', 'radio_state_address': '0xc0007859',
          'busy_address': '0xc000edf4', 'original_admission_instructions_executed': True,
          'response_copy_substituted': True, 'linux_driver_gate_exercised': False,
          'real_state_transitions_qualified': False, 'device_accessed': False}
(out/'report.json').write_text(json.dumps(report, indent=2))
print('Original radio admission:', len(cases), 'state combinations passed; no hardware IO')
