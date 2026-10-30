"""Execute candidate scatter initialization, pool initialization and RX veneer.
Computer-only; RTOS helpers are substituted. This is not a hardware test.
"""
import json
import argparse
import hashlib
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R8, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from marvell_firmware import parse

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate',required=True,type=Path)
args=parser.parse_args()
folder=args.candidate.resolve()
if not folder.is_relative_to((ROOT/'work').resolve()):raise ValueError('candidate must be under project work/')
report = json.loads((folder/'review.json').read_text())
image=(folder/'candidate/sd8686.bin').read_bytes()
if hashlib.sha256(image).hexdigest()!=report['candidate_sha256']:raise ValueError('candidate report/image mismatch')
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
for address, size in ((0, 0x20000), (0xc0000000, 0x20000), (0x04000000, 0x2000), (0x200000, 0x10000)):
    u.mem_map(address, size)
    u.mem_write(address, bytes([0xa5])*size)
for record in parse(image):
    if record.command == 1:
        u.mem_write(record.address, record.data)
start, end = int(report['reserved_start'], 16), int(report['reserved_end'], 16)
state = int(report['mailbox_address'], 16)
reserved = bytes(u.mem_read(start, end-start))
calls = []


def hook(cpu, address, size, user):
    if address in (0xc54, 0x1f000):
        cpu.emu_stop()
    elif address in (0xfa94, 0xfaa0):
        cpu.reg_write(UC_ARM_REG_R0, 0)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
    elif address == 0x7b4:
        dest, source, n = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        assert n <= 32
        cpu.mem_write(dest, bytes(cpu.mem_read(source, n)))
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
    elif address == 0xa314:
        calls.append('original subtype dispatcher')
        cpu.reg_write(UC_ARM_REG_R0, 77)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))


u.hook_add(UC_HOOK_CODE, hook)
u.reg_write(UC_ARM_REG_R8, 0x110)
u.emu_start(0xb0, 0xc58, count=150000)
assert bytes(u.mem_read(start, end-start)) == reserved
assert not any(u.mem_read(0xc0006e70, start-0xc0006e70))
assert not any(u.mem_read(end, 0xc0017da4-end))
assert not any(u.mem_read(0xc0000000, 0xe00))
assert not any(u.mem_read(0x04000008, 0x1d7c))
assert struct.unpack('<I', u.mem_read(state, 4))[0] == 0x31524e58


def call(entry, *args):
    u.reg_write(UC_ARM_REG_SP, 0x208000)
    u.reg_write(UC_ARM_REG_LR, 0x1f001)
    for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
        u.reg_write(register, value)
    u.emu_start(entry, 0x1f002, count=10000)
    return u.reg_read(UC_ARM_REG_R0)


call(0x11e0) # original routine reclaims startup-only scatter inputs
assert bytes(u.mem_read(0x17320,32))==bytes(32)
assert bytes(u.mem_read(start,end-start))==reserved
assert call(0x163ed) == 0xc000d5a4
allocated = [call(0x102dd, 0xc000d5a4) for _ in range(4)]
assert allocated == [0xc0008b50, 0xc00092bc, 0xc0009a28, 0]
for pointer in allocated[:3]:
    assert call(0x1031d, 0xc000d5a4, pointer) == 0
assert bytes(u.mem_read(start, end-start)) == reserved
frame = bytearray(79)
frame[0], frame[2] = 95, 0xd0
frame[12:18] = bytes.fromhex('020000000001')
frame[18:24] = bytes([255])*6
frame[32:47] = bytes.fromhex('7f18fe3401020304dd2518fe340401')
packet = b'XNOW'+bytes([1, 3, 0, 0])+struct.pack('<II', 9, 0x12345678)+bytes([1,0,1,1])+b'X'+bytes(11)
frame[47:] = packet
u.mem_write(0x200100, bytes(frame))
assert call(0xc00026a8, 0x200100, 0x200500) == 0
assert bytes(u.mem_read(state+52, 32)) == packet
assert struct.unpack('<I', u.mem_read(state+16, 4))[0] == 2
snapshot=bytes(u.mem_read(state,92))
frame[47:]=b'XNOW'+bytes([1,1,0,0])+bytes(24)
u.mem_write(0x200100,bytes(frame))
for _ in range(100):assert call(0xc00026a8,0x200100,0x200500)==0
assert bytes(u.mem_read(state,92))==snapshot
frame[32] = 255
u.mem_write(0x200100, bytes(frame))
assert call(0xc00026a8, 0x200100, 0x200500) == 77
assert calls == ['original subtype dispatcher']
result = {'passed': True, 'candidate_scatter_executed': True,
          'candidate_sha256':hashlib.sha256(image).hexdigest(),
          'all_unreserved_bss_zeroed': True, 'payload_survived_startup': True,
          'candidate_pool_blocks': 3, 'payload_survived_pool_alloc_release': True,
          'patched_arm_to_thumb_veneer_executed': True,
          'radio_rx_snapshot_updated': True, 'original_fallback_preserved': True,
          'hundred_heartbeats_preserve_unread_snapshot':True,
          'original_reclaim_routine_executed':'0x11e0',
          'boot_scatter_inputs_reclaimed':True,'payload_survived_reclaim':True,
          'rtos_helpers_mocked': True, 'hardware_tested': False, 'device_written': False}
(folder/'offline-integration.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
