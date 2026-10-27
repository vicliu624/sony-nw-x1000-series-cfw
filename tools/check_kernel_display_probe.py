"""Replay stock QFB probe's memory-only fix setup; never initialize hardware."""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-1.bin').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
analysis = (ROOT / 'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()
elf = ELFFile(io.BytesIO(analysis))
assert elf.get_section_by_name('.kernel').data() == raw
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
for s in elf.iter_segments():
    if s['p_type'] == 'PT_LOAD':
        low = s['p_vaddr'] & ~4095
        high = (s['p_vaddr'] + s['p_memsz'] + 4095) & ~4095
        u.mem_map(low, high - low)
        u.mem_write(s['p_vaddr'], s.data())
u.mem_map(0x60000000, 0x20000)
info = 0x60001000
def put(p, v): u.mem_write(p, struct.pack('<I', v))
def word(p): return struct.unpack('<I', u.mem_read(p, 4))[0]
# These are previous-stage fb_info geometry fixtures, not measured device values.
put(info + 0x10, 240)
put(info + 0x20, 16)
u.reg_write(UC_ARM_REG_R7, info)
u.reg_write(UC_ARM_REG_SP, 0x60018000)
copies = []
def hook(uc, pc, size, data):
    if pc == 0xc00f4f40:
        dst, src, count = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        assert (dst, src, count) == (info + 0xa8, 0xc0022fb0, 68)
        copies.append([hex(dst), hex(src), count])
        uc.mem_write(dst, bytes(uc.mem_read(src, count)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    elif pc == 0xc0017f3c:
        uc.emu_stop()
u.hook_add(UC_HOOK_CODE, hook)
u.emu_start(0xc0017eec, 0, count=100)
assert u.reg_read(UC_ARM_REG_PC) == 0xc0017f3c
fix = info + 0xa8
assert copies and word(fix + 16) == 0x33000000
assert word(fix + 20) == 0x500000 and word(fix + 44) == 480
page_bytes, visible_bytes = 0x60000, 240 * 432 * 2
assert visible_bytes <= page_bytes and 2 * page_bytes <= word(fix + 20)
report = {
    'kernel_sha256': digest,
    'instruction_range': ['0xc0017eec', '0xc0017f38'],
    'stop_before': '0xc0017f3c',
    'geometry_fixture': {'xres_virtual': 240, 'bits_per_pixel': 16},
    'runtime_fix': {'smem_start': hex(word(fix + 16)), 'smem_len': word(fix + 20), 'line_length': word(fix + 44)},
    'frontend_map_bytes': 2 * page_bytes,
    'frontend_visible_bytes_per_page': visible_bytes,
    'limits': [
        'Only the memory-only tail of probe fix initialization is replayed. Earlier hardware setup is skipped.',
        'The memcpy service is simulated; source template and capacity/base globals come from the pinned kernel.',
        'Geometry is a supplied fixture. No live fb_info, MMIO, mmap, LCD presentation or device boot is tested.',
        'Physical base is diagnostic evidence only; the frontend uses the existing device mmap API.'
    ]
}
(ROOT / 'sources/native-kernel-display-probe.json').write_text(json.dumps(report, indent=2) + '\n')
print('Stock QFB fix setup: 5 MiB capacity; 480-byte stride with 240x16 fixture; frontend two-page range fits')
