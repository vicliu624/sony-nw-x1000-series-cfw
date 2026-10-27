"""Execute stock display finalizer with virtual munmap/close, including failures."""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(raw))
symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows = []
for mapped, unmap_result, close_result in ((True, 0, 0), (True, -1, 0), (True, 0, -1), (True, -1, -1), (False, 0, 0), (False, 0, -1)):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    low = min(s['p_vaddr'] for s in segments) & ~4095
    high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
    u.mem_map(low, high - low)
    for s in segments: u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x60000000, 0x20000)
    context, sentinel = 0x60001000, 0x6001f000
    initial = [0xa5000000 + i for i in range(34)]
    initial[0] = 17
    initial[1] = 0x61000000 if mapped else 0
    u.mem_write(context, struct.pack('<34I', *initial))
    calls = []
    def hook(uc, pc, size, data):
        if pc == sentinel:
            uc.emu_stop(); return
        if pc == symbols['munmap']:
            assert mapped
            args = [uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)]
            assert args == [0x61000000, 0x500000]
            calls.append({'call': 'munmap', 'args': args, 'result': unmap_result})
            result = unmap_result
        elif pc == symbols['close']:
            assert uc.reg_read(UC_ARM_REG_R0) == 17
            calls.append({'call': 'close', 'fd': 17, 'result': close_result})
            result = close_result
        elif pc in (symbols['ioctl'], symbols['poll']):
            raise AssertionError('Unexpected device command or poll in native finalizer')
        else: return
        uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def intr(uc, number, data): raise AssertionError(f'Unexpected syscall {number}')
    u.hook_add(UC_HOOK_CODE, hook)
    u.hook_add(UC_HOOK_INTR, intr)
    u.reg_write(UC_ARM_REG_R0, context)
    u.reg_write(UC_ARM_REG_SP, 0x60018000)
    u.reg_write(UC_ARM_REG_LR, sentinel)
    u.emu_start(0x14a3f0, 0, count=1000)
    assert u.reg_read(UC_ARM_REG_PC) == sentinel
    final = list(struct.unpack('<34I', u.mem_read(context, 136)))
    expected = initial[:]
    if mapped:
        for index in (1, 2, 3, 4, *range(11, 27)): expected[index] = 0
    assert final == expected
    assert [c['call'] for c in calls] == (['munmap', 'close'] if mapped else ['close'])
    assert u.reg_read(UC_ARM_REG_R0) == close_result & 0xffffffff
    rows.append({'mapped_fixture': mapped, 'calls': calls, 'return_signed': close_result,
                 'cleared_word_indices': [i for i in range(34) if initial[i] != final[i]]})
report = {'input_sha256': digest, 'native_entry': '0x14a3f0', 'cases': rows,
          'finding': 'Mapped branch always clears selected pointers and closes after munmap, including virtual failure. No explicit ioctl/poll drain inside this finalizer; return is close result.',
          'limits': ['Only this function is covered; preceding GUI final presentation and kernel close/release behavior are outside this test.',
                     'Context, mapping and fd are fixtures. munmap/close are virtual; no real device or display completion.',
                     'Absence of a drain in this function does not show the entire native handoff needs no synchronization.']}
(ROOT / 'sources/native-display-finalize.json').write_text(json.dumps(report, indent=2) + '\n')
print('Six stock display-finalizer cases passed: unmap/clear/close order and failure semantics; no drain claim')
