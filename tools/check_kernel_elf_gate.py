"""Replay only the stock kernel ELF type/ARM/entry/APCS26 admission block.

No process is loaded: execution stops before mmap/file operations. Acceptance
here does not prove syscall ABI, dynamic linking or full loader compatibility.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_FP

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
analysis = (ROOT / 'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()
elf = ELFFile(io.BytesIO(analysis))
assert elf.get_section_by_name('.kernel').data() == raw
segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
def loaded_word(address):
    for s in segments:
        if s['p_vaddr'] <= address and address + 4 <= s['p_vaddr'] + s['p_filesz']:
            return struct.unpack_from('<I', s.data(), address - s['p_vaddr'])[0]
    raise AssertionError('Address outside original image')
hwcap = loaded_word(0xc00ad880)
files = {
    'stock-SpiderApp': ROOT / 'work/targets-jp/SpiderApp',
    'external-frontend': ROOT / 'work/x1000-homebrew-frontend',
    'home-candidate': ROOT / 'work/home-entry-candidate/SpiderApp.analysis-only.elf',
}
cases = [(name, path.read_bytes()[:52], True) for name, path in files.items()]
baseline = files['external-frontend'].read_bytes()[:52]
for name, offset, fmt, value in [('wrong-machine', 18, '<H', 3), ('relocatable', 16, '<H', 1),
                                  ('unaligned-entry', 24, '<I', 2),
                                  ('apcs26-without-hwcap', 36, '<I', 8)]:
    header = bytearray(baseline)
    struct.pack_into(fmt, header, offset, value)
    cases.append((name, bytes(header), False))
rows = []
for name, header, expected in cases:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    low = min(s['p_vaddr'] for s in segments) & ~4095
    high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
    u.mem_map(low, high - low)
    for s in segments:
        u.mem_write(s['p_vaddr'], s.data())
    if not low <= hwcap < high:
        u.mem_map(hwcap & ~4095, 4096)
    u.mem_write(hwcap, bytes(4))  # conservative fixture: ARM32 only
    u.mem_map(0x60000000, 0x20000)
    u.mem_write(0x60010000, header)
    u.reg_write(UC_ARM_REG_FP, 0x60008000)
    u.mem_write(0x60008000 - 0x88, struct.pack('<I', 0x60010000))
    observed = []
    def hook(uc, pc, size, data):
        if pc in (0xc00acaa0, 0xc00adea0):
            observed.append(pc == 0xc00acaa0)
            uc.emu_stop()
    u.hook_add(UC_HOOK_CODE, hook)
    u.emu_start(0xc00aca24, 0, count=1000)
    assert observed == [expected], (name, observed)
    rows.append({'input': name, 'header_sha256': hashlib.sha256(header).hexdigest(),
                 'e_flags': hex(struct.unpack_from('<I', header, 36)[0]),
                 'entry': hex(struct.unpack_from('<I', header, 24)[0]), 'accepted_by_block': expected})
result = {'scope': 'Original kernel load_elf_binary admission instructions only; fixture memory, no file/mapping operations',
          'kernel_sha256': hashlib.sha256(raw).hexdigest(),
          'analysis_sha256': hashlib.sha256(analysis).hexdigest(),
          'entry': '0xc00aca24', 'accepted_stop': '0xc00acaa0', 'rejected_stop': '0xc00adea0',
          'hwcap_fixture': 0, 'cases': rows,
          'limits': ['Architecture admission is not full exec or device qualification.',
                     'Modern EABI flags passing this block do not make r7+svc0 compatible with the OABI decoder.',
                     'Program-header mapping, permissions, interpreter, relocations and lifecycle remain separate checks.']}
(ROOT / 'sources/native-kernel-elf-gate.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'{len(rows)} original kernel ELF admission cases passed; no loader or device execution')
