"""Pinned native confirmation composition; no firmware archive or deployment."""
import hashlib,io,struct,subprocess
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
ENTRY=0x4d8500
POINTER=0x405438
def offset(raw,address,count):
    matches=[s for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']]
    if len(matches)!=1:raise ValueError('Expected one file-backed mapping')
    s=matches[0];return int(s['p_offset']+address-s['p_vaddr'])
def compose(base,out):
    out.mkdir(parents=True,exist_ok=True)
    ld=out/'callback.ld';helper=out/'callback.elf';binary=out/'callback.bin'
    ld.write_text('''ENTRY(xw_wireless_native_confirm)
SECTIONS { . = 0x4d8500; .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
ASSERT(SIZEOF(.data)==0, "No data")
ASSERT(SIZEOF(.bss)==0, "No BSS")
ASSERT(. < 0x4d8600, "Callback exceeds slot")
xw_native_mode_request = 0xda84;
xw_native_stock_confirm = 0x88494;
xw_native_selected_row = 0x4ee5d8;
''')
    source='runtime/platform/wireless/native_callback.c'
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(ld),source,'-o',str(helper)],cwd=ROOT,check=True)
    subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(helper),str(binary)],check=True)
    code=binary.read_bytes();at=offset(base,ENTRY,len(code));pointer=offset(base,POINTER,4)
    callers=[instruction.address+4 for instruction in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,ENTRY) if instruction.mnemonic=='bl' and instruction.op_str=='#0xda84']
    if len(callers)!=1:raise ValueError('Expected one request anchor')
    if base[at:at+len(code)]!=bytes(len(code)):raise ValueError('Callback slot already occupied')
    if struct.unpack_from('<I',base,pointer)[0]!=0x88494:raise ValueError('Unexpected original confirm callback')
    # Reject an overlapping file mapping that aliases this slot elsewhere.
    aliases=[]
    for s in ELFFile(io.BytesIO(base)).iter_segments():
        if s['p_type']!='PT_LOAD':continue
        lo=max(at,s['p_offset']);hi=min(at+len(code),s['p_offset']+s['p_filesz'])
        if lo<hi:aliases.append((s['p_vaddr']+lo-s['p_offset'],s['p_flags']))
    if aliases!=[(ENTRY,5)]:raise ValueError('Unexpected callback mapping/permissions')
    patched=bytearray(base);patched[at:at+len(code)]=code;struct.pack_into('<I',patched,pointer,ENTRY)
    restored=bytearray(patched);restored[at:at+len(code)]=base[at:at+len(code)];restored[pointer:pointer+4]=base[pointer:pointer+4]
    assert restored==base and len(patched)==len(base)
    original=ELFFile(io.BytesIO(base));result=ELFFile(io.BytesIO(patched))
    assert original.header==result.header and [dict(s.header) for s in original.iter_segments()]==[dict(s.header) for s in result.iter_segments()]
    report=dict(entry=hex(ENTRY),pointer=hex(POINTER),request_caller=hex(callers[0]),code_bytes=len(code),elf_growth_bytes=0,
                base_sha256=hashlib.sha256(base).hexdigest(),candidate_sha256=hashlib.sha256(patched).hexdigest(),
                code_sha256=hashlib.sha256(code).hexdigest(),pointer_sha256=hashlib.sha256(patched[pointer:pointer+4]).hexdigest(),
                source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [source,'tools/wireless_callback_bridge.py']})
    return bytes(patched),report
