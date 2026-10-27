"""Replay stock elf_map/set_brk/padzero helpers against real ELF program headers.

The VMA allocator, locks and clear_user are simulated. This is not a complete
load_elf_binary, interpreter, security, relocation or physical-device test.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR,
                     UC_PROT_ALL, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
                              UC_ARM_REG_PC, UC_ARM_REG_CPSR, UC_CPU_ARM_926)

ROOT = Path(__file__).resolve().parents[1]
kernel = ELFFile(io.BytesIO((ROOT / 'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()))
raw_kernel = (ROOT / 'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(raw_kernel).hexdigest() == '6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
assert kernel.get_section_by_name('.kernel').data() == raw_kernel
ksegments = [s for s in kernel.iter_segments() if s['p_type'] == 'PT_LOAD']
paths = [('stock', ROOT / 'work/targets-jp/SpiderApp'),
         ('candidate', ROOT / 'work/home-entry-candidate/SpiderApp.analysis-only.elf'),
         ('frontend', ROOT / 'work/x1000-homebrew-frontend')]
rows = []
for name, path in paths:
    raw = path.read_bytes()
    elf = ELFFile(io.BytesIO(raw))
    loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.ctl_set_cpu_model(UC_CPU_ARM_926)
    lo = min(s['p_vaddr'] for s in ksegments) & ~4095
    hi = (max(s['p_vaddr'] + s['p_memsz'] for s in ksegments) + 4095) & ~4095
    u.mem_map(lo, hi - lo)
    for s in ksegments:
        u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    def put(a, value):
        u.mem_write(a, struct.pack('<I', value))
    # Original helpers recover current from the 8KB kernel-stack base.
    put(0x60006008, 0xbf000000)
    put(0x6000600c, 0x60014000)
    put(0x60014000 + 0x6c, 0x60015000)
    pages, mappings, clears, brks = {}, [], [], []
    def map_pages(address, length, permissions, file_offset=None):
        for page in range(address, (address + length + 4095) & ~4095, 4096):
            if page not in pages:
                u.mem_map(page, 4096, UC_PROT_ALL)
            else:
                u.mem_protect(page, 4096, UC_PROT_ALL)
            if file_offset is None:
                data = bytes(4096)
            else:
                offset = file_offset + page - address
                data = raw[offset:offset + 4096].ljust(4096, b'\0')
            u.mem_write(page, data)
            u.mem_protect(page, 4096, permissions)
            pages[page] = permissions
    def hook(uc, pc, size, data):
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        sp = uc.reg_read(UC_ARM_REG_SP)
        if pc in (0xc021a294, 0xc00f214c):
            assert a[0] == 0x60015000 + 0x2c
            uc.reg_write(UC_ARM_REG_R0, 0)
        elif pc == 0xc00780b0:
            flags, pgoff = struct.unpack('<II', uc.mem_read(sp, 8))
            assert a[0] == 123 and flags == 0x1812
            assert a[1] % 4096 == 0 and a[2] > 0
            offset = pgoff * 4096
            map_pages(a[1], a[2], a[3], offset)
            mappings.append({'address': a[1], 'length': a[2], 'prot': a[3], 'file_offset': offset})
            uc.reg_write(UC_ARM_REG_R0, a[1])
        elif pc == 0xc00787f4:
            assert a[0] % 4096 == 0 and a[1] % 4096 == 0
            map_pages(a[0], a[1], UC_PROT_READ | UC_PROT_WRITE)
            brks.append([a[0], a[1]])
            uc.reg_write(UC_ARM_REG_R0, a[0])
        elif pc == 0xc00f60f4:
            assert all(pages[p] & UC_PROT_WRITE for p in range(a[0] & ~4095, a[0] + a[1], 4096))
            uc.mem_write(a[0], bytes(a[1]))
            clears.append([a[0], a[1]])
            uc.reg_write(UC_ARM_REG_R0, 0)
        else:
            return
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    kernel_hook = u.hook_add(UC_HOOK_CODE, hook)
    def call(address, a=0, b=0, c=0, d=0, stackarg=0):
        for r, value in [(UC_ARM_REG_R0, a), (UC_ARM_REG_R1, b), (UC_ARM_REG_R2, c),
                         (UC_ARM_REG_R3, d), (UC_ARM_REG_SP, 0x60008000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(r, value)
        put(0x60008000, stackarg)
        u.emu_start(address, 0x50000000, count=10000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    for s in loads:
        ph = [1, s['p_offset'], s['p_vaddr'], s['p_paddr'], s['p_filesz'], s['p_memsz'], s['p_flags'], s['p_align']]
        u.mem_write(0x60010000, struct.pack('<8I', *ph))
        prot = ((UC_PROT_READ if s['p_flags'] & 4 else 0) |
                (UC_PROT_WRITE if s['p_flags'] & 2 else 0) | (UC_PROT_EXEC if s['p_flags'] & 1 else 0))
        before = len(mappings)
        assert call(0xc00ac8b0, 123, s['p_vaddr'], 0x60010000, prot, 0x1812) == s['p_vaddr'] & ~4095
        observed = mappings[before]
        assert observed['length'] == s['p_filesz'] + (s['p_vaddr'] & 4095)
        assert observed['file_offset'] == s['p_offset'] - (s['p_vaddr'] & 4095)
    bss = max(s['p_vaddr'] + s['p_filesz'] for s in loads)
    brk = max(s['p_vaddr'] + s['p_memsz'] for s in loads)
    assert call(0xc00ac7c8, bss, brk) == 0
    expected_brk = (brk + 4095) & ~4095
    assert struct.unpack('<II', u.mem_read(0x60015000 + 0x50, 8)) == (expected_brk, expected_brk)
    call(0xc00ac860, bss)
    for s in loads:
        assert bytes(u.mem_read(s['p_vaddr'], s['p_filesz'])) == raw[s['p_offset']:s['p_offset'] + s['p_filesz']]
        count = s['p_memsz'] - s['p_filesz']
        assert bytes(u.mem_read(s['p_vaddr'] + s['p_filesz'], count)) == bytes(count)
    entry = elf['e_entry']
    assert pages[entry & ~4095] & UC_PROT_EXEC
    rejected = []
    first = loads[0]
    original_ph = [1, first['p_offset'], first['p_vaddr'], first['p_paddr'],
                   first['p_filesz'], first['p_memsz'], first['p_flags'], first['p_align']]
    for control in ('unaligned-file-offset', 'overflowing-file-range'):
        ph = list(original_ph)
        if control == 'unaligned-file-offset':
            ph[1] += 1
        else:
            ph[1], ph[4] = 0xfffff000, 0x3000
        u.mem_write(0x60010000, struct.pack('<8I', *ph))
        before = len(mappings)
        assert call(0xc00ac8b0, 123, ph[2], 0x60010000, 5, 0x1812) == 0xffffffea
        assert len(mappings) == before
        rejected.append(control)
    selftest_exit = None
    if name == 'frontend':
        u.hook_del(kernel_hook)
        u.mem_map(0x7ffd0000, 0x20000)
        u.mem_write(0x7ffe0000, struct.pack('<5I', 2, 0x7ffe0100, 0x7ffe0120, 0, 0))
        u.mem_write(0x7ffe0100, b'frontend\0')
        u.mem_write(0x7ffe0120, b'--selftest\0')
        u.reg_write(UC_ARM_REG_CPSR, 0x10)
        u.reg_write(UC_ARM_REG_SP, 0x7ffe0000)
        def interrupt(uc, number, data):
            global selftest_exit
            pc = uc.reg_read(UC_ARM_REG_PC)
            assert struct.unpack('<I', uc.mem_read(pc - 4, 4))[0] == 0xef900001
            selftest_exit = uc.reg_read(UC_ARM_REG_R0)
            uc.emu_stop()
        u.hook_add(UC_HOOK_INTR, interrupt)
        u.emu_start(entry, 0, count=1000000)
        assert selftest_exit == 0
    rows.append({'image': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'mappings': mappings,
                 'anonymous_bss': brks, 'zeroed_tail': clears,
                 'rejected_without_mapping': rejected,
                 'loaded_bytes_and_bss_verified': True, 'mapped_frontend_selftest_exit': selftest_exit})
result = {'scope': 'Original kernel ELF map/brk/zero helpers; VMA/locks/clear_user virtual; not full exec',
          'kernel_sha256': hashlib.sha256(raw_kernel).hexdigest(), 'cases': rows,
          'limits': ['No real VMA allocator, MMU, file operations or physical device ran.',
                     'ELF admission, initial stack construction, interpreter, relocations, security and lifecycle are not combined here.',
                     'Only the external freestanding frontend enters selftest; no Sony application entry executes.']}
(ROOT / 'sources/native-kernel-elf-mapping.json').write_text(json.dumps(result, indent=2) + '\n')
print('Three ELF images map byte-exactly with zero BSS; mapped frontend ARM926 selftest exits zero')
