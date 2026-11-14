"""Replay pinned Sony sleep/storage branches. PC Unicorn only; no player I/O."""
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


class SleepManager:
    """Fresh stock sysmgrd machine with virtual power, timer and libc ports."""

    core = 0x60000000
    stack = 0x6001f000
    stop = 0x6001fff0

    def __init__(self, kind='sleep', parameter=0):
        data = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
        self.digest = hashlib.sha256(data).hexdigest()
        assert self.digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
        elf = ELFFile(io.BytesIO(data))
        self.symbols = {symbol.name: symbol['st_value'] for symbol in elf.get_section_by_name('.dynsym').iter_symbols()}
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.cpu.mem_map(0x8000, 0x40000)
        self.cpu.mem_map(self.core, 0x20000)
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                self.cpu.mem_write(segment['p_vaddr'], segment.data())
        self.kind = kind
        self.parameter = parameter
        self.events = []
        self.seen = []
        self.cpu.hook_add(UC_HOOK_CODE, self._hook)

    def put(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def word(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def call(self, entry, *args):
        for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
            self.cpu.reg_write(register, value)
        self.cpu.reg_write(UC_ARM_REG_SP, self.stack)
        self.cpu.reg_write(UC_ARM_REG_LR, self.stop)
        self.cpu.emu_start(entry, self.stop, count=500000)
        assert self.cpu.reg_read(UC_ARM_REG_PC) == self.stop
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def _cstr(self, address):
        data = bytearray()
        for index in range(512):
            byte = bytes(self.cpu.mem_read(address + index, 1))
            if byte == b'\0':
                return data.decode()
            data += byte
        raise AssertionError('Unterminated fixture string')

    def _hook(self, cpu, pc, size, context):
        a = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc in (0x12b40, 0x12e84, 0x129d0, 0x17894, 0x17950):
            self.seen.append(hex(pc))
            return
        if pc in (0xa188, 0x17588):
            result = 1
        elif pc in (0x1c4d0, 0x1c5ac, 0x1e518):
            pass
        elif self.kind.startswith('sleep') and pc in (0xa780, 0xa714, 0xa6ac):
            self.events.append(['policy-fixture', hex(pc)])
            result = int(self.kind == 'sleep-usb' and pc in (0xa714, 0xa6ac))
        elif self.kind.startswith('sleep') and pc == 0xa81c:
            self.events.append(['timer-fixture', hex(pc)])
        elif pc == self.symbols['open']:
            self.events.append(['open', self._cstr(a[0]), a[1]])
            result = 42
        elif pc == self.symbols['write']:
            self.events.append(['write', a[0], bytes(cpu.mem_read(a[1], a[2])).decode()])
            result = a[2]
            if self.kind == 'sleep-write-error':
                result = -1
                self.events.append(['injected-write-result', -1, 'errno=EAGAIN'])
        elif pc == self.symbols['close']:
            self.events.append(['close', a[0]])
        elif pc == self.symbols['ioctl']:
            self.events.append(['ioctl', a[0], hex(a[1])])
            self.put(a[2], self.parameter)
        elif pc == self.symbols['sync']:
            self.events.append(['sync'])
        elif pc == self.symbols['umount']:
            self.events.append(['umount', self._cstr(a[0])])
        elif pc in (0x1c888, 0x1c8c8):
            raise AssertionError(('unexpected exception', self.kind, self.parameter, hex(pc)))
        else:
            return
        cpu.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))


def main():
    rows = []
    cases = [('sleep', 0), ('sleep', 2), ('sleep-usb', 2), ('sleep-write-error', 0),
             ('awake', 0x100), ('awake', 0x800), ('unmount', 1), ('unmount', 3),
             ('unmount', 4), ('unmount', 5)]
    for kind, parameter in cases:
        machine = SleepManager(kind, parameter)
        core, events = machine.core, machine.events
        if kind.startswith('sleep'):
            entry = 0xaaac
            machine.put(core + 0x503c, 3)
            machine.put(core + 0x5164, parameter)
            result = machine.call(entry, core)
            assert ['open', '/proc/pm', 1] in events
            assert ['write', 42, 'S4' if kind == 'sleep-usb' else 'S3'] in events
            assert not any(event[0] == 'umount' for event in events)
            assert machine.word(core + 0x503c) == 4 and result == 0
        elif kind == 'awake':
            entry = 0x17950
            result = machine.call(entry, 42)
            assert result == parameter and not any(event[0] == 'umount' for event in events)
        else:
            entry = 0xe084
            machine.put(core + 0x503c, parameter)
            result = machine.call(entry, core)
            if parameter in (1, 3):
                assert ['umount', '/contents'] in events and result == 0
            else:
                assert not any(event[0] == 'umount' for event in events) and result == 0x1d03
        rows.append({'kind': kind, 'fixture': parameter, 'entry': hex(entry), 'return': hex(result),
                     'native_helpers': machine.seen, 'events': events})
    report = dict(all_passed=True, sysmgrd_sha256=machine.digest, physical_device_access=False, cases=rows,
                  scope='Original aaac/129d0/17894 and17950 plus e084/12e84/12b40 execute. Sleep enters supplied core state3 with prepare acknowledgments already complete; mode/policy/timer, libc and physical power virtual. No whole boot, application sleep callbacks, actual suspend or hardware fault reproduction.')
    out = ROOT / 'work/stock-sleep'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'sleep-storage-replay.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
