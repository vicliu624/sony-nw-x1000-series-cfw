"""PC-only original Si470x ARM replay. Never opens a player or I2C device.

Input: locally extracted Japanese 1.11 module. All bus/MMIO is synthetic.
The stock instructions, including read/write helpers, execute unchanged.
"""
import argparse
import hashlib
import io
import json
import struct
import tarfile
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC

PIN = 'c65262032cc8dec3d28ee6061ac267c5de61ef7f78a8744fc983de9941113bcb'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, default=Path('work/fm-driver-audit/si470x.ko'))
    parser.add_argument('--upg', type=Path, help='Extract the module from the pinned local stock UPG first')
    parser.add_argument('--output', type=Path, default=Path('work/fm-driver-audit/replay.json'))
    args = parser.parse_args()
    if args.upg:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from scripts.upg import unpack
        _, components = unpack(args.upg.read_bytes())
        assert hashlib.sha256(components[3]).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
        with tarfile.open(fileobj=io.BytesIO(components[3]), mode='r:gz') as archive:
            members = [m for m in archive.getmembers() if m.name.lstrip('./') == 'lib/modules/icx_si470x_radio_tuner.ko']
            assert len(members) == 1
            blob = archive.extractfile(members[0]).read()
        assert hashlib.sha256(blob).hexdigest() == PIN
        args.module.parent.mkdir(parents=True, exist_ok=True)
        args.module.write_bytes(blob)
    raw = args.module.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('Not the pinned Japanese 1.11 module')
    elf = ELFFile(io.BytesIO(raw))
    tab = elf.get_section_by_name('.symtab')
    bases = {i: 0x100000+i*0x10000 for i, s in enumerate(elf.iter_sections()) if s['sh_flags'] & 2}
    external = {}

    def address(s):
        if s['st_shndx'] == 'SHN_UNDEF':
            return external.setdefault(s.name, 0x700000+16*len(external))
        return bases[s['st_shndx']]+s['st_value']

    symbols = {s.name: address(s) for s in tab.iter_symbols()
               if s.name and (s['st_shndx'] in bases or s['st_shndx'] == 'SHN_UNDEF')}
    images = {i: bytearray(s.data()) for i, s in enumerate(elf.iter_sections())
              if i in bases and s['sh_type'] != 'SHT_NOBITS'}
    for sec in elf.iter_sections():
        if sec['sh_type'] != 'SHT_REL' or sec['sh_info'] not in images:
            continue
        data = images[sec['sh_info']]
        for rel in sec.iter_relocations():
            off = rel['r_offset']
            word = struct.unpack_from('<I', data, off)[0]
            target = address(tab.get_symbol(rel['r_info_sym']))
            kind = rel['r_info_type']
            if kind == 2:
                new = (target+word) & 0xffffffff
            elif kind == 1:
                addend = word & 0xffffff
                if addend & 0x800000:
                    addend -= 0x1000000
                delta = target+4*addend-(bases[sec['sh_info']]+off)
                assert delta % 4 == 0 and -(1 << 25) <= delta < (1 << 25)
                new = (word & 0xff000000) | ((delta >> 2) & 0xffffff)
            elif kind == 40:
                continue
            else:
                raise ValueError(('unsupported relocation', kind))
            struct.pack_into('<I', data, off, new)

    def replay(name, values=(), regs=None, setup=None, transfer_result=1, follow=()):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        for i, base in bases.items():
            size = elf.get_section(i)['sh_size']
            cpu.mem_map(base, max(4096, (size+4095) & ~4095))
            if i in images:
                cpu.mem_write(base, bytes(images[i]))
        for base, size in ((0x700000, 0x10000), (0x800000, 0x20000), (0x900000, 0x10000),
                           (0xa00000, 4096), (0xec810000, 4096), (0xec050000, 4096)):
            cpu.mem_map(base, size)
        client = 0x800000
        cpu.mem_write(client+12, struct.pack('<I', 0x801000))
        if setup:
            setup(cpu, symbols)
        registers = list(regs) if regs is not None else [0x1000+i for i in range(16)]
        events = []
        stopped = []
        names = {v: k for k, v in external.items()}

        def hook(u, pc, size, unused):
            if pc == 0xa00000:
                stopped.append(True)
                u.emu_stop()
                return
            if pc not in names:
                return
            helper = names[pc]
            a, b, c = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            result = 0
            if helper == 'i2c_transfer':
                assert c == 1
                addr, flags, length, pad, buf = struct.unpack('<4HI', bytes(u.mem_read(b, 12)))
                event = dict(kind='i2c', address=addr, flags=flags, length=length)
                if flags & 1:
                    payload = b''.join(struct.pack('>H', registers[(10+i) % 16]) for i in range(length//2))
                    u.mem_write(buf, payload)
                else:
                    payload = bytes(u.mem_read(buf, length))
                    if transfer_result == 1:
                        for i in range(length//2):
                            registers[(2+i) % 16] = struct.unpack_from('>H', payload, 2*i)[0]
                event['bytes'] = payload.hex()
                events.append(event)
                result = transfer_result
            elif helper == '__memzero':
                u.mem_write(a, bytes(b))
            elif helper == 'memcpy':
                u.mem_write(a, bytes(u.mem_read(b, c)))
                result = a
            elif helper in ('__udivsi3', '__divsi3'):
                assert helper == '__udivsi3' or a < 0x80000000
                result = a//b
            elif helper in ('msleep', 'icx1087_AdcMixMute'):
                events.append(dict(kind=helper, value=a))
            elif helper == 'printk':
                events.append(dict(kind='printk'))
            else:
                raise AssertionError(('unexpected external', helper))
            u.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

        cpu.hook_add(UC_HOOK_CODE, hook)
        for r, v in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), (client, *values)):
            cpu.reg_write(r, v & 0xffffffff)
        cpu.reg_write(UC_ARM_REG_SP, 0x90f000)
        cpu.reg_write(UC_ARM_REG_LR, 0xa00000)
        for entry in (name, *follow):
            stopped.clear()
            cpu.reg_write(UC_ARM_REG_R0, client)
            cpu.reg_write(UC_ARM_REG_LR, 0xa00000)
            cpu.emu_start(symbols[entry], 0, count=100000)
            assert stopped, ('instruction budget exceeded', entry)
        return dict(function=name, arguments=list(values), result=cpu.reg_read(UC_ARM_REG_R0), events=events)

    checks = []
    for index in range(16):
        case = replay('si470x_read', (index,))
        assert case['result'] == 0x1000+index
        assert case['events'][0]['length'] == 2*((index-10) % 16+1)
        checks.append(case)
    for index in range(2, 16):
        case = replay('si470x_write', (index, 0xabcd))
        assert case['result'] == 0
        assert case['events'][0]['length'] == 2*(index-1)
        assert case['events'][0]['bytes'].endswith('abcd')
        checks.append(case)
    for index in (0, 1, 16):
        case = replay('si470x_write', (index, 0xabcd))
        assert case['result'] == 0xffffffff and not case['events']
        checks.append(case)
    case = replay('si470x_read', (16,))
    assert case['result'] == 0xffffffff and not case['events']
    checks.append(case)
    for name, values in (('si470x_read', (10,)), ('si470x_write', (2, 0xabcd))):
        case = replay(name, values, transfer_result=0)
        assert case['result'] == 0xffffffff
        checks.append(case)
    for name in ('si470x_initialize', 'si470x_reset', 'si470x_sleep'):
        checks.append(replay(name))
    initialized = replay('si470x_initialize', follow=('si470x_reset',))
    writes = [e for e in initialized['events'] if e['kind'] == 'i2c' and not e['flags']]
    assert [e['length'] for e in writes] == [28, 2, 10, 2, 28]
    assert writes[-1]['bytes'] == writes[0]['bytes']
    initialized['function'] = 'initialize then reset (same cache)'
    checks.append(initialized)
    for destination in range(13):
        def setup(cpu, syms, destination=destination):
            ro = elf.get_section_by_name('.rodata').data()
            value = struct.unpack_from('<I', ro, destination*8)[0]
            cpu.mem_write(syms['si470x_dest'], struct.pack('<I', value))
            cpu.mem_write(syms['fm_dev'], struct.pack('<I', 82500))
        case = replay('si470x_initialize', setup=setup)
        writes = [e for e in case['events'] if e['kind'] == 'i2c' and not e['flags']]
        words = struct.unpack('>14H', bytes.fromhex(writes[0]['bytes']))
        assert words[1] == 130
        assert words[2] == (0x0084 if (1 << destination) & 0x1a1e else 0x0884)
        assert words[3:5] == (0x126f, 0x1000)
        assert words[5:8] == (0x1007, 0x1008, 0x1009)
        assert words[8:] == (0,)*6
        case['destination_table_index'] = destination
        checks.append(case)
    for rssi, afc, expected in ((17, False, 0), (18, False, 0), (19, False, 1), (80, True, 0)):
        regs = [0]*16
        regs[10] = rssi | (0x1000 if afc else 0)
        regs[5] = 0x1200
        case = replay('fmGetSigStrength', (0x802000,), regs=regs,
                      setup=lambda cpu, syms: cpu.mem_write(0x802000, struct.pack('<I', 82500)))
        assert case['result'] == expected
        checks.append(case)
    data = elf.get_section_by_name('.data').data()
    for name in ('fmMUTE_ON', 'fmMOST_STEREO', 'fmMOST_MONO'):
        checks.append(replay(name))
    for sense in (6, 11, 23):
        checks.append(replay('fmSenseSet', (sense,)))
    # Exercise the original write-prefix mechanism with a property command image.
    # This verifies bytes only: the synthetic chip does NOT implement commands.
    def command_setup(cpu, syms):
        image = bytes.fromhex('000100000084126f100000000000000000000000000000000c000000')
        assert len(image) == 28
        cpu.mem_write(syms['si47RegBufferWrite'], image)
    case = replay('si470x_write', (15, 8), setup=command_setup)
    assert case['events'][0]['bytes'].endswith('000000000c000008')
    case['scope'] = 'Command-shaped bytes only; no command processor or property response modeled'
    checks.append(case)
    report = dict(module_sha256=PIN, tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), hardware_access=False,
                  scope='Original relocated ARM; synthetic I2C, mapped inert MMIO and mocked kernel services',
                  initial_table_hex=data[0x38c:0x3a8].hex(),
                  symbol_ranges=[dict(name=s.name, section=elf.get_section(s['st_shndx']).name,
                                      offset=s['st_value'], size=s['st_size'])
                                 for s in tab.iter_symbols() if s['st_info']['type'] == 'STT_FUNC'
                                 and isinstance(s['st_shndx'], int)],
                  read_messages=[struct.unpack_from('<4H', data, 0x21c+12*i) for i in range(16)],
                  checks=checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(checks)} original ARM cases passed; {args.output}')


if __name__ == '__main__':
    main()
