"""JP1.11 UTF-16 PIC/APIC terminator alignment fix; no image size/ABI growth."""
import hashlib,io,struct
from elftools.elf.elffile import ELFFile
PATCHES=((0x3139cc,0xe2822001,0xe2822002),
         (0x313b00,0xe2811001,0xe2811002),
         (0x313b08,0xe2822001,0xe2822002))
def compose(data):
    elf=ELFFile(io.BytesIO(data));result=bytearray(data);changes=[]
    if elf.elfclass!=32 or not elf.little_endian or elf['e_machine']!='EM_ARM':raise ValueError('Expected pinned JP ARM executable')
    for address,before,after in PATCHES:
        segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address<address+4<=s['p_vaddr']+s['p_filesz'])
        offset=segment['p_offset']+address-segment['p_vaddr']
        if struct.unpack_from('<I',result,offset)[0]!=before:raise ValueError(f'Unexpected original PIC/APIC instruction at {address:#x}')
        struct.pack_into('<I',result,offset,after);changes.append(dict(address=hex(address),offset=offset,before=hex(before),after=hex(after)))
    return bytes(result),dict(patches=changes,growth_bytes=0,base_sha256=hashlib.sha256(data).hexdigest(),sha256=hashlib.sha256(result).hexdigest(),hardware_qualified=False)
