"""Replay original command dispatch/channel handler; RF helpers are substituted.

No radio IO. Starts at the command switch after original pre-dispatch gates;
therefore this does not qualify admission in disconnected/power-save states.
"""
import hashlib
import json
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_ARM, UC_HOOK_CODE
from elftools.elf.elffile import ELFFile
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4,
                              UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP,
                              UC_ARM_REG_PC, UC_ARM_REG_LR)
from marvell_firmware import parse

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT/'work/targets-jp/sd8686.bin'
EXPECTED = '08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
blob = IMAGE.read_bytes()
if hashlib.sha256(blob).hexdigest() != EXPECTED:
    raise ValueError('unqualified original radio image')
records = parse(blob)


def replay(action, channel):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for address, size in ((0, 0x20000), (0xc0000000, 0x20000),
                          (0x04000000, 0x2000), (0x200000, 0x10000)):
        cpu.mem_map(address, size)
    for record in records:
        if record.command == 1:
            cpu.mem_write(record.address, record.data)
    request = struct.pack('<6H', 0x1d, 48, 0x4321, 0, action, channel)+bytes(36)
    cpu.mem_write(0x200100, request)
    cpu.mem_write(0xc0006624, b'\x08')  # observed-current-channel fixture
    cpu.mem_write(0xc001453e, struct.pack('<H', 17))  # power-value fixture
    for reg, value in ((UC_ARM_REG_R0, 0x1d), (UC_ARM_REG_R4, 0x200108),
                       (UC_ARM_REG_R5, 0x200100), (UC_ARM_REG_R6, 0),
                       (UC_ARM_REG_SP, 0x208000)):
        cpu.reg_write(reg, value)
    helpers, trace = [], []

    def hook(u, address, size, data):
        trace.append(address)
        if address in (0x9a46, 0x8d52):
            u.emu_stop()
        elif address in (0xd8ac, 0xd87c, 0xcb88):
            helpers.append((hex(address), u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)))
            u.reg_write(UC_ARM_REG_R0, 0)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x8133, 0x9b40, count=500)
    assert 0x8c9a in trace, 'command0x1d did not reach channel handler'
    assert trace[-1] in (0x9a46, 0x8d52), 'did not complete bounded handler path'
    after = bytes(cpu.mem_read(0x200100, len(request)))
    if action == 0:
        assert not helpers and struct.unpack_from('<H', after, 10)[0] == 8
        assert after[:10] == request[:10]
    elif action == 1:
        assert [h[0] for h in helpers] == ['0xd8ac', '0xd87c', '0xcb88']
        assert helpers[0][1:] == (17, channel & 255)
        assert helpers[1][1] == helpers[2][1] == channel & 255
        assert after == request
    else:
        assert not helpers and after == request
    return {'action': action, 'channel': channel, 'helpers': helpers,
            'response_body_hex': after[8:].hex(), 'switch_target': '0x8c9a'}


def replay_driver_builder(action, channel):
    module = ROOT/'work/hardware-audit/sd8686.ko'
    if hashlib.sha256(module.read_bytes()).hexdigest() != '2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69':
        raise ValueError('unqualified driver')
    with module.open('rb') as f:
        text = ELFFile(f).get_section_by_name('.text').data()
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0, 0x30000);cpu.mem_write(0, text)
    cpu.mem_map(0x200000, 0x10000)
    cpu.mem_write(0x200200, struct.pack('<H', channel))
    cpu.reg_write(UC_ARM_REG_R5, 0x200200)
    cpu.reg_write(UC_ARM_REG_R6, 0x200100)
    cpu.reg_write(UC_ARM_REG_R7, action)
    # Stop before the relocated branch; this basic block has no relocations.
    cpu.emu_start(0xc838, 0xc87c, count=30)
    expected = struct.pack('<6H', 0x1d, 48, 0, 0, action, channel if action==1 else 0)+bytes(36)
    assert bytes(cpu.mem_read(0x200100,48)) == expected
    return {'action': action, 'channel': channel, 'original_driver_packet_bytes': 48}


cases = [replay(0, 0), *(replay(1, channel) for channel in (1, 8, 13, 0x108)), replay(2, 8)]
builders = [replay_driver_builder(0, 0), replay_driver_builder(1, 8)]
out = ROOT/'work/espnow-channel-handler'
out.mkdir(parents=True, exist_ok=True)
report = {'passed': True, 'image_sha256': EXPECTED, 'cases': cases, 'driver_builder_cases': builders,
          'original_dispatch_instructions_executed': True,
          'get_helper_original_code_executed': True, 'rf_set_helpers_substituted': True,
          'pre_dispatch_admission_exercised': False, 'driver_admission_exercised': False,
          'disconnected_state_qualified': False, 'device_accessed': False}
(out/'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
