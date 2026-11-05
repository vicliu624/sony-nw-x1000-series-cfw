"""Original manager observer/worker conversion, with queue and registry fixtures."""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows = []
for notice in ([3, 0, 0], [2, 1, 0], [0, 0, 2]):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in ELFFile(io.BytesIO(raw)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x60000000, 0x20000)
    ipc, event, node = 0x60006000, 0x60007000, 0x60009000
    put = lambda address, value: u.mem_write(address, struct.pack('<I', value))
    word = lambda address: struct.unpack('<I', u.mem_read(address, 4))[0]
    put(ipc + 4, 44); put(ipc + 0x1b0, 77); put(node + 8, 865)
    u.mem_write(event, struct.pack('<3I', *notice))
    queue, sent, reads = [], [], []
    def hook(cpu, pc, size, unused):
        args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if pc == 0x1967c:
            assert args[0] == 77 and args[2:] == [52, 0]
            queue.append(bytes(cpu.mem_read(args[1], 52)))
        elif pc == 0x1978c:
            if reads:
                cpu.emu_stop(); return
            assert args[0] == 77 and args[2:] == [52, 0] and len(queue) == 1
            cpu.mem_write(args[1], queue[0]); reads.append(True)
        elif pc == 0x16498:
            assert args[0] == ipc + 8 and args[1:3] == [0, 0]
            put(args[3], node)
            put(word(cpu.reg_read(UC_ARM_REG_SP) + 4), 1)
        elif pc == 0x16d18:
            assert args[:2] == [44, 865] and args[3] == 20
            sent.append(list(struct.unpack('<5I', cpu.mem_read(args[2], 20))))
        elif pc != 0x16578:
            return
        cpu.reg_write(UC_ARM_REG_R0, 0)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    for entry, arg0, arg1 in ((0xf298, event, ipc), (0xf0fc, ipc, 0)):
        u.reg_write(UC_ARM_REG_R0, arg0); u.reg_write(UC_ARM_REG_R1, arg1)
        u.reg_write(UC_ARM_REG_SP, 0x6001f000); u.reg_write(UC_ARM_REG_LR, 0x6001fff0)
        u.emu_start(entry, 0x6001fff0, count=50000)
    assert sent == [[20, 0, *notice]], sent
    rows.append(dict(internal_notice=notice, queue_prefix=list(struct.unpack('<5I', queue[0][:20])), wire=sent[0]))
report = dict(passed=True, sysmgrd_sha256=digest, cases=rows,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), physical_device_access=False,
    limits=['Original observer0xf298 and worker0xf0fc produce queue envelope and wire bytes.',
            'Queue, registry enumeration with one registered port, IPC send and locks are fixtures.',
            'Does not prove power-event source, real message delivery, client restoration or RF rearm.'])
(ROOT / 'work/remote-manager-notification-wire-latest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
