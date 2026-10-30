"""Execute actual compiled radio Thumb code with bounded RTOS helper substitutes.

No radio, filesystem installation, kernel/module or proprietary image is needed.
This is NOT radio-firmware memory-ownership or over-air qualification.
"""
import json
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/espnow-radio-bridge'
ELF = OUT/'bridge.elf'


def execute(damage=None, allocation=True, submit_result=0, pending=True, heartbeat=False, seed_rx=False):
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    u.mem_map(0, 0x20000)
    u.mem_map(0xc0000000, 0x20000)
    u.mem_map(0x200000, 0x10000)
    with ELF.open('rb') as f:
        e = ELFFile(f)
        for name in ('.text', '.state'):
            section = e.get_section_by_name(name)
            u.mem_write(section['sh_addr'], section.data())
        symbols = {s.name: s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
    state = symbols['xnow_radio_state']
    u.reg_write(UC_ARM_REG_SP, 0x208000)
    u.reg_write(UC_ARM_REG_R0, 0x200100)
    u.reg_write(UC_ARM_REG_R1, 0x200500)
    u.reg_write(UC_ARM_REG_LR, 0x1f001)
    frame = bytearray(79)
    frame[0], frame[2] = 95, 0xd0
    frame[12:18] = bytes.fromhex('020000000001')
    frame[18:24] = bytes([255])*6
    frame[32:47] = bytes.fromhex('7f18fe3401020304dd2518fe340401')
    inbound = b'XNOW'+bytes([1, 1, 0, 0])+struct.pack('<II', 7, 0x12345678)+bytes(16)
    if heartbeat:inbound=b'XNOW'+bytes([1,1,0,0])+bytes(24)
    outbound = b'XNOW'+bytes([1, 1, 0, 0])+struct.pack('<II', 99, 0xdeadbeef)+bytes(16)
    frame[47:] = inbound
    if damage:
        frame[damage[0]] = damage[1]
    u.mem_write(0x200100, bytes(frame))
    u.mem_write(state+4, struct.pack('<I', int(pending)))
    u.mem_write(state+20, outbound)
    if seed_rx:
        u.mem_write(state+16,struct.pack('<I',44))
        u.mem_write(state+52,b'XNOW'+bytes([1,3,0,0])+struct.pack('<II',12,13)+bytes(16))
        u.mem_write(state+84,bytes.fromhex('020000000009'))
    before = bytes(u.mem_read(state, 92))
    calls = []
    transmitted = []

    def hook(cpu, address, size, user):
        if address == 0x1f000:
            cpu.emu_stop()
            return
        if address not in (0x7b4, 0xa314, 0xd458, 0xda00, 0xd800):
            return
        calls.append(hex(address))
        r0, r1, r2, r3 = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if address == 0x7b4:
            assert r2 <= 32
            cpu.mem_write(r0, bytes(cpu.mem_read(r1, r2)))
        elif address == 0xa314:
            assert r0 == 0x200100 and r1 == 0x200500
            cpu.reg_write(UC_ARM_REG_R0, 77)
        elif address == 0xd458:
            assert r0 == 348
            cpu.reg_write(UC_ARM_REG_R0, 0x202000 if allocation else 0)
        elif address == 0xda00:
            assert (r0, r1, r2, r3) == (0x202000, 0x20010c, 13, 0x200112)
            cpu.mem_write(r0, bytes(128))
        elif address == 0xd800:
            assert r0 == 0x202000
            transmitted.append(bytes(cpu.mem_read(r0, 79)))
            cpu.reg_write(UC_ARM_REG_R0, submit_result & 0xffffffff)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    u.hook_add(UC_HOOK_CODE, hook)
    u.emu_start(symbols['xnow_radio_receive'], 0x1f002, count=2000)
    after = bytes(u.mem_read(state, 92))
    result = u.reg_read(UC_ARM_REG_R0)
    return result, before, after, calls, transmitted, inbound, outbound


checks = []
r, before, after, calls, tx, inbound, outbound = execute()
assert r == 0 and after[52:84] == inbound and after[84:90] == bytes.fromhex('020000000001')
assert struct.unpack_from('<IIII', after, 4) == (1, 1, 0, 2)
assert len(tx) == 1 and tx[0][0:2] == bytes([47, 0])
assert tx[0][32:47] == bytes.fromhex('7f18fe3401020304dd2518fe340401') and tx[0][47:] == outbound
checks.append('receive snapshot and pending TX payload/header preservation')
for options in ({'pending': False}, {'allocation': False}, {'submit_result': -1}):
    r, before, after, calls, tx, _, _ = execute(**options)
    assert r == 0 and struct.unpack_from('<I', after, 16)[0] == 2
    if options.get('pending') is False:
        assert '0xd458' not in calls and not tx
    else:
        assert struct.unpack_from('<II', after, 8) == (1, 0xffffffff)
    checks.append(str(options))
for damage in ((0, 94), (1, 1), (2, 0xc0), (2, 0xd8), (3, 0x40), (32, 255), (33, 0), (40, 0), (41, 250), (42, 0), (45, 0), (46, 2), (47, 0), (51,2),(52,0),(52,4),(53,1),(54,1)):
    r, before, after, calls, tx, _, _ = execute(damage=damage)
    assert r == 77 and after == before and calls == ['0xa314'] and not tx
checks.append('18 non-laboratory/malformed frames preserve original fallback and state')
for pending in (False,True):
    r,before,after,calls,tx,_,outbound=execute(heartbeat=True,pending=pending,seed_rx=True)
    assert r==0 and after[16:]==before[16:] # RX sequence, payload and source retained
    assert len(tx)==int(pending)
    if pending:assert tx[0][47:]==outbound and struct.unpack_from('<II',after,8)==(1,0)
    else:assert after==before
checks.append('exact heartbeat preserves unread RX snapshot while still servicing pending TX')
report = {'passed': True, 'checks': checks, 'compiled_thumb_executed': True,
          'rtos_helpers_mocked': True, 'candidate_memory_ownership_verified': False,
          'device_written': False, 'over_air_tested': False}
(OUT/'offline-tests.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))

