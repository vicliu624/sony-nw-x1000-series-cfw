"""Pinned kernel sleep wrapper ordering; suspend itself is an explicit fixture."""
from pathlib import Path
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-1.bin').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
rows = []
for mode in (1, 2, 3):
    for result in (0, -11):
        u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(0xc0000000, 0x800000)
        u.mem_write(0xc0008000, raw)
        u.mem_map(0x60000000, 65536)
        calls = []
        def word(address):
            return struct.unpack('<I', u.mem_read(address, 4))[0]
        def hook(cpu, pc, size, unused):
            if pc not in (0xc0047ac4, 0xc0063408):
                return
            if pc == 0xc0063408:
                assert word(0xc02b800c) == mode and word(0xc02b8010) == 0
                assert cpu.reg_read(UC_ARM_REG_R0) == (3 if mode == 3 else 1)
                calls.append(dict(mode_during_suspend=word(0xc02b800c), suspend_result=result))
            cpu.reg_write(UC_ARM_REG_R0, (result if pc == 0xc0063408 else 0) & 0xffffffff)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE, hook)
        u.reg_write(UC_ARM_REG_R0, mode)
        u.reg_write(UC_ARM_REG_SP, 0x6000f000)
        u.reg_write(UC_ARM_REG_LR, 0x6000ff00)
        u.emu_start(0xc003a148, 0x6000ff00, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x6000ff00
        assert u.reg_read(UC_ARM_REG_R0) == result & 0xffffffff
        assert word(0xc02b800c) == 0 and len(calls) == 1
        rows.append(dict(mode=mode, calls=calls, mode_after_return=0, result=result))
report = dict(passed=True, kernel_sha256=digest, cases=rows,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    physical_device_access=False,
    limits=['Original mp200_pm_sleep wrapper executes; printk and pm_suspend are intercepted.',
            'No driver suspend, actual wake, proc-write handler or manager timing is qualified.',
            'A non-final application acknowledgement can return before sleep; wrapper ordering does not make every acknowledgement a wake signal.'])
(ROOT / 'work/remote-kernel-sleep-wrapper-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
