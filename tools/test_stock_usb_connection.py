"""Compare the guest USB contract with the pinned original ARM kernel module.

No module is loaded in the host or a device. Selected original instructions run
in Unicorn; kernel locks/wait queues and copy-to-user are explicit fixtures.
"""
from pathlib import Path
import hashlib
import io
import json
import os
import struct
import subprocess
import tarfile
import time

from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from player_arm_guest import stock_libraries
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

GET_STATUS, ALLOW, PROHIBIT = 0x80046701, 0x40046702, 0x40046703
MODEL_SOURCE = 'tools/fixtures/stock_usb_connection_core.c'
TEST_SOURCE = 'tools/fixtures/stock_usb_connection_test.c'
MODEL_HEADER = 'tools/fixtures/stock_usb_connection_model.h'


def extract(out):
    gpl = ROOT / 'work/downloads/linux-kernel-2.6.10.local.tgz'
    packed = ROOT / 'work/upg-jp/verified-3.bin'
    assert hashlib.sha256(gpl.read_bytes()).hexdigest() == '286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
    assert hashlib.sha256(packed.read_bytes()).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
    with tarfile.open(gpl, 'r:gz') as archive:
        header = archive.extractfile('./include/asm-arm/arch-mp200/icx1087_usbconn.h').read()
    with tarfile.open(packed, 'r:gz') as archive:
        module = archive.extractfile('./lib/modules/icx1087_usbconn.ko').read()
    assert hashlib.sha256(header).hexdigest() == 'ff1b3134f79f85bc8157985e89180879ced19833a241929642b29f96f1448882'
    assert hashlib.sha256(module).hexdigest() == 'e21778550c53b82d8755b1366c1d9db051f6376c6e1e00f550d68925f4d7356d'
    (out / 'icx1087_usbconn.h').write_bytes(header)
    target = out / 'icx1087_usbconn.ko'
    target.write_bytes(module)
    return target


def compile_models(out, module):
    undefined = subprocess.check_output(['arm-linux-gnueabi-nm', '-u', str(module)], text=True)
    externals = {line.split()[-1]: 0x50100000 + index * 16
                 for index, line in enumerate(undefined.splitlines()) if line.strip()}
    linked = out / 'original-module.elf'
    subprocess.run(['arm-linux-gnueabi-ld', '-Ttext=0x50000000', '-Tdata=0x51000000',
                    '-Tbss=0x52000000', '-e', 'usbconn_ioctl',
                    *['--defsym=' + name + '=' + hex(address) for name, address in externals.items()],
                    str(module), '-o', str(linked)], check=True, capture_output=True)
    flags = ['-std=c99', '-Os', '-Wall', '-Wextra', '-Werror', '-march=armv5te', '-marm',
             '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
             '-fno-pie', '-no-pie', '-nostdlib', '-Wl,--build-id=none']
    model = out / 'model.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Wl,-Ttext=0x55000000,-e,_start',
                    MODEL_SOURCE, '-lgcc', '-o', str(model)], cwd=ROOT, check=True)
    return linked, model, externals


def original_comparison(linked, model, externals):
    originals, helper = (ELFFile(io.BytesIO(path.read_bytes())) for path in (linked, model))
    symbols = {symbol.name: int(symbol['st_value']) for elf in (originals, helper)
               for symbol in elf.get_section_by_name('.symtab').iter_symbols()}
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    segments = [segment for elf in (originals, helper) for segment in elf.iter_segments()
                if segment['p_type'] == 'PT_LOAD']
    areas = [(int(segment['p_vaddr']) & ~4095,
              (int(segment['p_vaddr']) + int(segment['p_memsz']) + 4095) & ~4095)
             for segment in segments]
    areas += [(0x50100000, 0x50110000), (0x50200000, 0x50201000),
              (0x53000000, 0x53010000), (0x60000000, 0x60001000), (0x70000000, 0x70010000)]
    merged = []
    for start, end in sorted(areas):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in merged:
        cpu.mem_map(start, end - start)
    for segment in segments:
        cpu.mem_write(int(segment['p_vaddr']), segment.data())
    registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
    device, file, callback_table, user = 0x53000100, 0x53001000, 0x53002000, 0x60000000
    done, callback = 0x7000ff00, 0x50200000
    put = lambda address, value: cpu.mem_write(address, struct.pack('<I', value & 0xffffffff))
    word = lambda address: struct.unpack('<I', cpu.mem_read(address, 4))[0]
    put(symbols['usbconn_devices'], device)
    put(file + 0x80, device)
    put(device + 0x68, callback_table)
    put(callback_table, callback)
    # Original thread_info used by the IRQ/preemption and user-copy code.
    put(0x7000e000, 0)
    put(0x7000e004, 0)
    put(0x7000e008, 0xffffffff)
    names = {address: name for name, address in externals.items()}
    wakeups, access_callbacks = [], []

    def hook(machine, pc, size, context):
        args = [machine.reg_read(register) for register in registers]
        if pc == callback:
            access_callbacks.append(args[0])
        elif pc in names:
            name = names[pc]
            if name == '__arch_copy_to_user':
                assert args[2] == 4 and args[0] == user
                machine.mem_write(args[0], bytes(machine.mem_read(args[1], args[2])))
            elif name == '__wake_up':
                assert args[0] == device + 0x60
                wakeups.append(args[:3])
            elif name == 'printk':
                pass
            elif name == 'strlen':
                length = 0
                while machine.mem_read(args[0] + length, 1)[0]:
                    length += 1
                    assert length < 1024
                machine.reg_write(UC_ARM_REG_R0, length)
                machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
                return
            else:
                raise AssertionError(('Unexpected kernel effect', name))
        else:
            return
        machine.reg_write(UC_ARM_REG_R0, 0)
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)

    def call(name, *args):
        for register, value in zip(registers, args):
            cpu.reg_write(register, value)
        cpu.reg_write(UC_ARM_REG_SP, 0x7000f000)
        cpu.reg_write(UC_ARM_REG_LR, done)
        cpu.emu_start(symbols[name], done, count=100000)
        assert cpu.reg_read(UC_ARM_REG_PC) == done, name
        return cpu.reg_read(UC_ARM_REG_R0)

    operations = [('get', 0), ('poll', 0), ('change', 4), ('get', 0), ('get', 0),
                  ('change', 1), ('poll', 0), ('poll', 0), ('access', ALLOW), ('get', 0),
                  ('access', PROHIBIT), ('get', 0), ('change', 4), ('get', 0), ('poll', 0),
                  ('change', 0), ('get', 0), ('poll', 0), ('change', 4), ('poll', 0),
                  ('access', PROHIBIT), ('change', 1), ('get', 0), ('poll', 0),
                  ('change', 1), ('poll', 0), ('change', 0), ('change', 1), ('get', 0), ('poll', 0)]
    rows = []
    for operation, value in operations:
        wakes_before = len(wakeups)
        if operation == 'change':
            expected_wake = call('test_change', value)
            call('usbconn_chg_sts', value)
            assert len(wakeups) - wakes_before == expected_wake
        elif operation == 'get':
            assert call('usbconn_ioctl', 0, file, GET_STATUS, user) == 0
            assert word(user) == call('test_status')
        elif operation == 'access':
            assert call('usbconn_ioctl', 0, file, value, user) == call('test_access', value) == 0
            assert access_callbacks[-1] == (1 if value == ALLOW else 2)
        else:
            assert call('usbconn_poll', file, 0) == call('test_poll')
        original = [word(device + offset) for offset in (0x70, 0x74, 0x6c)]
        candidate = list(struct.unpack('<3I', cpu.mem_read(symbols['test_usb'], 12)))
        assert original == candidate, (operation, value, original, candidate)
        rows.append({'operation': operation, 'value': value, 'state': original,
                     'kernel_wakeups': len(wakeups)})
    return rows


def unit_checks(out):
    flags = ['-std=c99', '-Wall', '-Wextra', '-Werror']
    host = out / 'host'
    subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', TEST_SOURCE,
                    '-o', str(host)], cwd=ROOT, check=True)
    run = subprocess.run([str(host)], capture_output=True, text=True, timeout=10, check=True)
    (out / 'host.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    libraries = stock_libraries()
    arm = out / 'test.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-DTEST_GPL_USB_ABI', '-DCONFIG_SONY_ICX1111',
                    '-I' + str(out), '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te',
                    '-marm', '-mfloat-abi=soft', '-fno-pie', '-no-pie', '-nostdlib',
                    '-Wl,--hash-style=sysv,--build-id=none', TEST_SOURCE,
                    'runtime/store/start.c', 'runtime/store/start.S', str(libraries['libc.so.6']),
                    str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(arm)], cwd=ROOT, check=True)
    run = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libraries['ld-linux.so.3']),
                          '--library-path', str(libraries['libc.so.6'].parent), str(arm)],
                         env=dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),
                         capture_output=True, text=True, timeout=10, check=True)
    (out / 'arm.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    assert 'STOCK_USB_CONNECTION_MODEL_PASS' in run.stdout


def main():
    out = ROOT / 'work/stock-usb-connection' / str(time.time_ns())
    out.mkdir(parents=True)
    sources = [MODEL_SOURCE, TEST_SOURCE, MODEL_HEADER, 'tools/test_stock_usb_connection.py',
               'runtime/store/start.c', 'runtime/store/start.S']
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    (out / 'inputs.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    module = extract(out)
    linked, model, externals = compile_models(out, module)
    rows = original_comparison(linked, model, externals)
    unit_checks(out)
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
    report = {'passed': True, 'device_accessed': False, 'firmware_created': False,
              'original_module_instructions_executed': True, 'original_libc_arm926': True,
              'host_sanitizers': True, 'operations': rows, 'source_hashes': hashes,
              'original_module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
              'limits': ['Kernel scheduling, IRQ delivery, wait queues and copy-to-user are fixtures.',
                         'No original userspace manager, USB gadget, host enumeration or storage ownership is qualified.',
                         'Only disconnected/connected/start-connect and access gating are modeled; no update or MTP state.']}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'operations': len(rows), 'report': str((out / 'report.json').relative_to(ROOT))}))


if __name__ == '__main__':
    main()
