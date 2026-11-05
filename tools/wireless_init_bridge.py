"""Compose native three-choice initialization without touching confirmation."""
import hashlib
import io
import struct
import subprocess
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from wireless_callback_bridge import offset

def patch_choice_descriptor(base,patched):
    descriptor=0x4e692c+0x1d*132
    if struct.unpack_from('<I',base,offset(base,descriptor+26*4,4))[0]!=13900:
        raise ValueError('Expected native wireless On/Off resource descriptor')
    edits=[]
    for field in (21,22,32):
        address=descriptor+field*4;at=offset(base,address,4)
        if struct.unpack_from('<I',base,at)[0]!=2:raise ValueError('Unexpected native two-choice descriptor')
        struct.pack_into('<I',patched,at,3)
        edits.append(dict(address=address,field=field,before=2,after=3))
    return edits


def compose(base, out):
    out.mkdir(parents=True, exist_ok=True)
    source = 'runtime/platform/wireless/native_mode_init.c'
    ld, helper, binary = (out / name for name in ('init.ld', 'init.elf', 'init.bin'))
    ld.write_text('''ENTRY(xw_wireless_native_init)
SECTIONS { . = 0x4d8100; .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
ASSERT(SIZEOF(.data)==0, "No data")
ASSERT(SIZEOF(.bss)==0, "No BSS")
ASSERT(. < 0x4d8400, "Initializer exceeds slot")
xw_mode_ui_root = 0x2a984;
xw_mode_param_get = 0x10a118;
xw_mode_param_set = 0x10a0d4;
xw_mode_stock_init = 0x88400;
xw_mode_request = 0xda84;
xw_mode_post = 0xa57f0;
xw_mode_parent = 0x7461c;
xw_mode_index = 0x74608;
xw_mode_category = 0x74668;
xw_mode_selected = 0x4ee5d8;
''')
    subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror', '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie', '-fno-stack-protector', '-ffreestanding', '-nostdlib', '-no-pie', '-Wl,--build-id=none,-T,' + str(ld), source, '-o', str(helper)], cwd=ROOT, check=True)
    subprocess.run(['arm-linux-gnueabi-objcopy', '-O', 'binary', str(helper), str(binary)], check=True)
    elf = ELFFile(io.BytesIO(helper.read_bytes()))
    entry = int(elf['e_entry']); code = binary.read_bytes()
    slot, pointer = offset(base, 0x4d8100, len(code)), offset(base, 0x405304, 4)
    if any(base[slot:slot+len(code)]) or struct.unpack_from('<I', base, pointer)[0] != 0x88400:
        raise ValueError('Unexpected initializer slot or callback')
    aliases = []
    for segment in ELFFile(io.BytesIO(base)).iter_segments():
        if segment['p_type'] != 'PT_LOAD': continue
        low, high = max(slot, segment['p_offset']), min(slot+len(code), segment['p_offset']+segment['p_filesz'])
        if low < high: aliases.append((segment['p_vaddr']+low-segment['p_offset'], segment['p_flags']))
    if aliases != [(0x4d8100, 5)]: raise ValueError('Unexpected initializer mapping')
    patched = bytearray(base); patched[slot:slot+len(code)] = code
    struct.pack_into('<I', patched, pointer, entry)
    data_edits=patch_choice_descriptor(base,patched)
    restored = bytearray(patched); restored[slot:slot+len(code)] = base[slot:slot+len(code)]; restored[pointer:pointer+4] = base[pointer:pointer+4]
    for edit in data_edits:struct.pack_into('<I',restored,offset(base,edit['address'],4),edit['before'])
    assert restored == base and len(patched) == len(base)
    callers=[instruction.address+4 for instruction in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,0x4d8100) if instruction.mnemonic=='bl' and instruction.op_str=='#0xda84']
    assert len(callers)==1
    return bytes(patched), dict(entry=hex(entry), code_bytes=len(code), elf_growth_bytes=0,
        request_caller=hex(callers[0]),choice_descriptor=0x1d,choice_resource=13900,data_edits=data_edits,
        guards=[dict(address=hex(address), bytes=count, sha256=hashlib.sha256(patched[offset(base,address,count):offset(base,address,count)+count]).hexdigest()) for address,count in ((0x4d8100,len(code)),(0x405304,4))],
        source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (source,'tools/wireless_init_bridge.py')})
