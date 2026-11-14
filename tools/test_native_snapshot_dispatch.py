"""Check original snapshot dispatch, including the warm-switch no-reply states.

States are explicit fixtures. Accepted states stop at the serializer callback;
ignored states execute their real no-op callback and return through the FSM.
This does not establish a complete application switch or hardware readiness.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import time

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
from unicorn.arm_const import UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
STOCK_SHA256 = '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
SNAPSHOT_CONSTRUCTOR = 0x6dec0
SNAPSHOT_RECEIVER = 0x6df2c
SNAPSHOT_CONTEXT = 0x683328
SNAPSHOT_CALLBACK = 0x6ed0c
IGNORE_CALLBACK = 0x6df6c
NATIVE_POST = 0xa57f0
SNAPSHOT_EVENT = 0x430113


def file_bytes(elf, address, size):
    segments = [segment for segment in elf.iter_segments()
                if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address
                and address + size <= segment['p_vaddr'] + segment['p_filesz']]
    if len(segments) != 1:
        raise ValueError('Expected a unique file-backed native range')
    segment = segments[0]
    start = address - segment['p_vaddr']
    return segment.data()[start:start + size]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    source = args.input.resolve()
    if args.input.is_symlink() or not source.is_relative_to(ROOT / 'work'):
        raise ValueError('Use an explicit analysis ELF under work/')
    stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
        raise ValueError('Original JP1.11 identity differs')
    raw = source.read_bytes()
    original, image = ELFFile(io.BytesIO(stock)), ELFFile(io.BytesIO(raw))
    if image['e_machine'] != 'EM_ARM' or image.elfclass != 32 or not image.little_endian:
        raise ValueError('Expected the fixed-address ARM32 player')
    ranges = ((0x6deb0, 0xd0), (SNAPSHOT_CALLBACK, 0x5c), (0x17c474, 0x53c),
              (0x3f4388, 0x24))
    for address, size in ranges:
        if file_bytes(image, address, size) != file_bytes(original, address, size):
            raise ValueError('Snapshot/FSM code differs at ' + hex(address))

    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0x8000, 0x1000000)
    cpu.mem_map(0x70000000, 0x20000)
    for segment in image.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            cpu.mem_write(segment['p_vaddr'], segment.data())
    packet, stack, done = 0x70001000, 0x70018000, 0x7001fff0
    phase = None
    selected, posts = [], []

    def observe(machine, pc, size, context):
        if phase != 'dispatch':
            return
        if pc in (SNAPSHOT_CALLBACK, IGNORE_CALLBACK):
            selected.append(pc)
            if pc == SNAPSHOT_CALLBACK:
                machine.emu_stop()
        if pc == NATIVE_POST:
            posts.append(machine.reg_read(UC_ARM_REG_R0))
            raise AssertionError('Ignored snapshot state unexpectedly posted an event')

    def no_syscalls(machine, number, context):
        raise AssertionError('Unexpected syscall in pure native dispatch')

    cpu.hook_add(UC_HOOK_CODE, observe)
    cpu.hook_add(UC_HOOK_INTR, no_syscalls)

    def call(address, arguments=()):
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
                                   [*arguments, 0, 0, 0, 0]):
            cpu.reg_write(register, value)
        cpu.reg_write(UC_ARM_REG_SP, stack)
        cpu.reg_write(UC_ARM_REG_LR, done)
        cpu.emu_start(address, done, count=100000)
        return cpu.reg_read(UC_ARM_REG_R0)

    cases = []
    for state in range(1, 8):
        phase = 'constructor'
        if call(SNAPSHOT_CONSTRUCTOR) != 0 or cpu.reg_read(UC_ARM_REG_PC) != done:
            raise AssertionError('Original snapshot constructor did not return normally')
        constructed = bytes(cpu.mem_read(SNAPSHOT_CONTEXT, 32))
        if constructed[:3] != bytes((1, 1, 1)):
            raise AssertionError('Unexpected original constructor header')
        cpu.mem_write(SNAPSHOT_CONTEXT + 1, bytes((state,)))
        cpu.mem_write(packet, struct.pack('<4I', 0, SNAPSHOT_EVENT, 6, 0))
        selected.clear()
        posts.clear()
        phase = 'dispatch'
        result = call(SNAPSHOT_RECEIVER, (packet,))
        expected = SNAPSHOT_CALLBACK if state <= 5 else IGNORE_CALLBACK
        if selected != [expected]:
            raise AssertionError((state, selected))
        if state >= 6 and (cpu.reg_read(UC_ARM_REG_PC) != done or result != 0 or posts):
            raise AssertionError('Ignored state must return without a completion event')
        cases.append(dict(state_fixture=state, selected_callback=hex(expected),
                          serializer_body_executed=False,
                          original_noop_return_executed=state >= 6,
                          completion_emitted=False))
    output = ROOT / 'work/native-snapshot-dispatch' / str(time.time_ns())
    output.mkdir(parents=True)
    report = dict(contract_checked=True, application_handoff_qualified=False,
                  device_accessed=False, firmware_created=False,
                  original_sha256=STOCK_SHA256,
                  image_sha256=hashlib.sha256(raw).hexdigest(), cases=cases,
                  source_hashes={'tools/test_native_snapshot_dispatch.py':
                                 hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                  limits=['State bytes are supplied fixtures after the real native constructor.',
                          'States1..5 stop at the serializer; media and IPC are not executed.',
                          'States6/7 execute the no-op and original FSM return, with no completion.',
                          'A mode0 byte patch does not establish snapshot readiness or a successful switch.'])
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(contract_checked=True, cases=len(cases),
                         report=(output / 'report.json').relative_to(ROOT).as_posix())))


if __name__ == '__main__':
    main()
