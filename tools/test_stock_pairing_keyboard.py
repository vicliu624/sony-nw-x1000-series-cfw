"""Trace the stock WLAN password keyboard and delete confirmation in ARM emulation."""
import hashlib
import io
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

from app_registry import ROOT

raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
image = ELFFile(io.BytesIO(raw))
cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
cpu.mem_map(0x8000, 0x1000000)
cpu.mem_map(0x70000000, 0x10000)
for segment in image.iter_segments():
    if segment['p_type'] == 'PT_LOAD':
        cpu.mem_write(segment['p_vaddr'], segment.data())
word = lambda address: struct.unpack('<I', cpu.mem_read(address, 4))[0]
callbacks = word(word(0x3f55d8 + (143 - 1) * 4) + 12)
assert word(callbacks + 5 * 4) == 0x7e688
assert word(callbacks + 7 * 4) == 0x7e79c
delete_desc = word(0x3f55d8 + (145 - 1) * 4)
delete_callbacks = word(delete_desc + 12)
assert word(delete_callbacks + 7 * 4) == 0x7f4a0
event_map = word(delete_desc + 16)
count = struct.unpack('<h', cpu.mem_read(delete_desc + 6, 2))[0]
delete_action, = (word(event_map + 8*i + 4) for i in range(count)
                  if word(event_map + 8*i) == 0x4a012e)
stride = cpu.mem_read(delete_desc, 1)[0]
assert cpu.mem_read(word(delete_desc + 8) + delete_action*stride + 3, 1)[0] == 7
descriptor = 0x4eb99c + 43*48
assert struct.unpack('<12I', cpu.mem_read(descriptor, 48)) == (43,14400,3,0,0,0,0,2,0,0,0,4)

registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
stop = 0x7000ff00
text_pointer = 0x638e04 + 0x2b20
input_bytes = ('0123456789ABCDEF' * 2 + '\0').encode('utf-16le')
cpu.mem_write(text_pointer, input_bytes)
events, text_reads = [], []


def hook(uc, address, size, _):
    args = tuple(uc.reg_read(register) for register in registers)
    result = 0
    if address == 0xa57f0:
        events.append(args)
    elif address == 0x7fb48:
        result = 0x70000000
    elif address in (0x7fce0, 0x33b340):
        assert args[0] == text_pointer and bytes(uc.mem_read(args[0], len(input_bytes))) == input_bytes
        text_reads.append(address)
    elif address == 0xd574:
        assert args[1] == 0 and args[2] == 65
    elif address == 0x2a984:
        result = 0x63bd8c
    elif address == 0x2b360:
        assert args[:2] == (0x63bd8c, 132)
    else:
        return
    uc.reg_write(UC_ARM_REG_R0, result)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


def call(address, *args):
    for register, value in zip(registers, args):
        cpu.reg_write(register, value)
    cpu.reg_write(UC_ARM_REG_SP, 0x7000f000)
    cpu.reg_write(UC_ARM_REG_LR, stop)
    cpu.emu_start(address, stop, count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC) == stop
    return cpu.reg_read(UC_ARM_REG_R0)


cpu.hook_add(UC_HOOK_CODE, hook)
assert call(0x7e79c, 0, 0, 0, 132) == 4
assert events == [(0x20107, 0, 2, 0)] and not text_reads
events.clear()
assert call(0x7e688, 0, 0, 1, 0) == 2
assert events == [(0x20621, 0, 0, 0)] and not text_reads
events.clear()
assert call(0x7e688, 0, 0, 0, 0) == 2
assert events == [(0x20621, 0, 0, 0)] and text_reads == [0x7fce0, 0x33b340]
events.clear()
assert call(0x7f4a0, 0, 0x4a012e, 2, 0) == 2
assert not events
assert call(0x7f4a0, 0, 0x4a012e, 1, 0) == 5
assert events == [(0x4c8001, 0, 0xf60020, 0)]
print(json.dumps(dict(passed=True, stock_open_event='0x20107', stock_mode_arg=2,
                      stock_group=143, completion_callback_index=5,
                      text_pointer=hex(text_pointer), confirm_reads_text=True, cancel_reads_text=False,
                      delete_dialog_id=43,delete_result_event='0x4a012e',
                      delete_yes=1,delete_no=2,negative_does_not_queue_delete=True,
                      rendering_and_IME_modeled=True, device_accessed=False), indent=2))
