"""Check the guest NCAN stop handshake against the original ARM ioctl code."""
import hashlib
import io
import json
import struct
import subprocess
import tarfile
import time

from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from player_arm_guest import stock_libraries, run_guest
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC


def driver_contract(out):
    with tarfile.open(ROOT / 'work/upg-jp/verified-3.bin', 'r:gz') as archive:
        module = archive.extractfile('./lib/modules/icx1111_ncan.ko').read()
    assert hashlib.sha256(module).hexdigest() == '69f4f590c32fb9843993758413e8a538c62cced21a4e738e9f469a6052dd9837'
    original = out / 'icx1111_ncan.ko'
    original.write_bytes(module)
    undefined = subprocess.check_output(['arm-linux-gnueabi-nm', '-u', str(original)], text=True)
    externals = {line.split()[-1]: 0x50100000 + index * 16 for index, line in enumerate(undefined.splitlines()) if line.strip()}
    linked = out / 'original.elf'
    subprocess.run(['arm-linux-gnueabi-ld', '-Ttext=0x50000000', '-Tdata=0x51000000', '-Tbss=0x52000000',
                    '-e', '0x50000000',
                    *['--defsym=' + name + '=' + hex(address) for name, address in externals.items()],
                    str(original), '-o', str(linked)], check=True, capture_output=True)
    elf = ELFFile(io.BytesIO(linked.read_bytes()))
    symbols = {symbol.name: int(symbol['st_value']) for symbol in elf.get_section_by_name('.symtab').iter_symbols()
               if symbol['st_shndx'] != 'SHN_UNDEF'}
    results = []
    for digipod in (0, 1):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        segments = [segment for segment in elf.iter_segments() if segment['p_type'] == 'PT_LOAD']
        areas = [(int(s['p_vaddr']) & ~4095, (int(s['p_vaddr']) + int(s['p_memsz']) + 4095) & ~4095) for s in segments]
        areas += [(0x50100000, 0x50110000), (0x53000000, 0x53010000), (0x60000000, 0x60001000), (0x70000000, 0x70010000)]
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
        put = lambda address, value: cpu.mem_write(address, struct.pack('<I', value & 0xffffffff))
        word = lambda address: struct.unpack('<I', cpu.mem_read(address, 4))[0]
        device = symbols['icx1111_ncan_dev']
        put(device + 4, 1)
        put(device + 0x68, 1)
        put(symbols['s_isDigipod'], digipod)
        put(0x53000080, device)
        put(0x7000e008, 0xffffffff)
        put(0x7000a008, 0xffffffff)
        put(0x7000e00c, 0x53002000)
        put(0x7000a00c, 0x53003000)
        put(0x53002004, 0x7000e000)
        put(0x53003004, 0x7000a000)
        names = {address: name for name, address in externals.items()}
        wakeups = []
        trace = []
        scheduled = []
        paused = [False]
        registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)

        def hook(machine, pc, size, context):
            trace.append(hex(pc))
            if len(trace) > 24:
                trace.pop(0)
            args = [machine.reg_read(register) for register in registers]
            r0, r2 = 0, None
            if pc == symbols['icx1111_ncan_key_status_read']:
                pass  # Explicit unchanged idle key state0, not a sensor model.
            elif pc in (symbols['icx1111_ncan_nchpr_det_irq_enable'],
                        symbols['icx1111_ncan_all_irq_enable_without_lock']):
                pass  # IRQ setup is a peripheral fixture; no hardware register IO.
            elif pc in names:
                name = names[pc]
                if name == '__get_user_4':
                    assert args[0] == 0x60000000
                    r2 = word(args[0])
                elif name == '__put_user_4':
                    assert args[0] == 0x60000000
                    put(args[0], args[2])
                elif name == '__wake_up':
                    wakeups.append(args[:3])
                elif name == 'schedule':
                    scheduled.append(pc)
                    paused[0] = True
                    machine.emu_stop()
                    return
                elif name == '__down_trylock_failed':
                    # ARM semaphore failure helper restores the decremented
                    # count and returns nonzero in ip, preserving r0.
                    semaphore = machine.reg_read(UC_ARM_REG_R12)
                    put(semaphore, word(semaphore) + 1)
                    machine.reg_write(UC_ARM_REG_R12, 1)
                    machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
                    return
                elif name == 'msleep':
                    assert args[0] == 20  # No physical contention timing model.
                elif name == 'printk':
                    pass
                elif name == 'memset':
                    assert args[2] <= 4096
                    machine.mem_write(args[0], bytes([args[1] & 255]) * args[2])
                    r0 = args[0]
                elif name == '__memzero':
                    assert args[1] <= 4096
                    machine.mem_write(args[0], bytes(args[1]))
                elif name in ('prepare_to_wait', 'finish_wait', 'icx1087_nc_clbk_set', 'icx1087_nc_GetOutputDevice'):
                    pass
                else:
                    raise AssertionError(('Unexpected kernel/hardware effect', name))
            else:
                return
            machine.reg_write(UC_ARM_REG_R0, r0)
            if r2 is not None:
                machine.reg_write(UC_ARM_REG_R2, r2)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        cpu.hook_add(UC_HOOK_CODE, hook)

        def ioctl(command, stack=0x7000f000):
            for register, value in zip(registers, (0, 0x53000000, command, 0x60000000)):
                cpu.reg_write(register, value)
            cpu.reg_write(UC_ARM_REG_SP, stack)
            cpu.reg_write(UC_ARM_REG_LR, 0x7000ff00)
            try:
                cpu.emu_start(symbols['icx1111_ncan_ioctl'], 0x7000ff00, count=500000)
            except Exception:
                (out / 'driver-failure.json').write_text(json.dumps(dict(command=hex(command),
                    pc=hex(cpu.reg_read(UC_ARM_REG_PC)), lr=hex(cpu.reg_read(UC_ARM_REG_LR)),
                    trace=trace), indent=2) + '\n', encoding='utf-8')
                raise
            if paused[0]:
                assert command == 0xc0046308 and len(scheduled) == 1
                assert word(device + 0xd4) == 0, 'Wait must clear a stale break before sleeping'
                paused[0] = False
                context = cpu.context_save()
                resume = cpu.reg_read(UC_ARM_REG_LR)
                # A second modeled kernel task executes the real break ioctl;
                # no event flags or application completion words are fabricated.
                assert ioctl(0x6309, 0x7000b000) == 0
                cpu.context_restore(context)
                cpu.reg_write(UC_ARM_REG_R0, 0)
                cpu.emu_start(resume, 0x7000ff00, count=500000)
            assert cpu.reg_read(UC_ARM_REG_PC) == 0x7000ff00
            return cpu.reg_read(UC_ARM_REG_R0)

        assert ioctl(0x6309) == 0 and word(device + 0xd4) == 0x200 and len(wakeups) == 1
        put(0x60000000, 0x1000)
        assert ioctl(0xc0046308) == 0
        # The Digipod branch clears its private flag on return; the other
        # branch retains it until the next wait. Both expose break word0x200.
        expected_flags = 0 if digipod else 0x200
        assert word(0x60000000) == 0x200 and word(device + 0xd4) == expected_flags, (
            digipod, hex(word(0x60000000)), hex(word(device + 0xd4)))
        expected_schedules = 0 if digipod else 1
        assert len(scheduled) == expected_schedules and len(wakeups) == 1 + expected_schedules, (
            digipod, len(scheduled), wakeups)
        results.append(dict(digipod=digipod, break_sets=0x200, successful_wait_returns=0x200,
                            break_flags_after_return=expected_flags, prior_break_cleared=not digipod,
                            break_during_wait_executed=not digipod, hardware_state_fixture=0))
    return results


def main():
    out = ROOT / 'work/stock-ncan-wait' / str(time.time_ns())
    out.mkdir(parents=True)
    results = driver_contract(out)
    source = 'tools/fixtures/stock_ncan_wait_test.c'
    flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-pthread']
    host = out / 'host'
    subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', source, '-o', str(host)], cwd=ROOT, check=True)
    run = subprocess.run([str(host)], capture_output=True, text=True, timeout=10, check=True)
    (out / 'host.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    libraries = stock_libraries()
    arm = out / 'test.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-pie', '-no-pie', '-nostdlib',
                    '-Wl,--hash-style=sysv,--build-id=none', source, 'runtime/store/start.c', 'runtime/store/start.S',
                    str(libraries['libpthread.so.0']), str(libraries['libc.so.6']), str(libraries['ld-linux.so.3']),
                    '-lgcc', '-o', str(arm)], cwd=ROOT, check=True)
    init = out / 'init.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-pie', '-no-pie', '-nostdlib',
                    '-Wl,--hash-style=sysv,--build-id=none', 'tools/fixtures/player_worker_system_init.c',
                    'runtime/store/start.c', 'runtime/store/start.S', str(libraries['libc.so.6']),
                    str(libraries['ld-linux.so.3']), '-lgcc', '-o', str(init)], cwd=ROOT, check=True)
    guest = run_guest(out, init, {'test': arm}, libraries,
                      ['STOCK_NCAN_WAIT_MODEL_PASS', 'PLAYER_WORKER_CHILD_STATUS=0'])
    assert guest['passed']
    sources = [source, 'tools/fixtures/stock_ncan_wait_model.h', 'tools/test_stock_ncan_wait.py',
               'runtime/store/start.c', 'runtime/store/start.S', 'tools/fixtures/player_worker_system_init.c']
    report = dict(passed=True, device_accessed=False, firmware_created=False, original_driver_branches=results,
                  host_sanitizers=True, original_libc_arm926=True, actual_linuxthreads_system_guest=True,
                  arm_system_guest=guest,
                  source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
                  limits=['Explicit idle key state; IRQ, wait queues and kernel synchronization are fixtures.',
                          'The C model selects the non-Digipod ordering; the comparison variant retains an earlier break.',
                          'No sensor, noise-cancellation engine, codec, full native exit or hardware qualification.'])
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'report': str((out / 'report.json').relative_to(ROOT))}))


if __name__ == '__main__':
    main()
