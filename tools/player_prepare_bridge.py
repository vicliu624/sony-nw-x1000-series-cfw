"""Analysis-only ARM bridge bytes; does not patch an ELF or install firmware."""
import struct
import hashlib
import io
from elftools.elf.elffile import ELFFile
from build_player_met_anchor import branch
PREPARE_BRIDGE=0x4d7fc0
PREPARE_HANDLED=0x58575052
PREPARE_COMPOSITION_SHA='ab2b31b56b4b70c793491f3a33fa4edbee8ab337b0794389abc61db168551e61'
BUILTIN_COMPOSITION_SHA='a207541d1099e5d470fa094f438723c3f3743b1db999720fbb446340c196f530'
REMOTE_SETTINGS_COMPOSITION_SHA='97a3f8dfe64743431db98de0668b6a52f1967cedf68ece79b6d2137ce4b82f23'


def prepare_bridge(address=PREPARE_BRIDGE):
    if address!=PREPARE_BRIDGE:
        raise ValueError('Only the planned analysis address is supported')
    # Save native arguments/LR. Ordinary PID/failure results restore the exact
    # arguments and tail-call original prepare. Only the explicit handled marker
    # restores the caller and returns0 without entering original prepare.
    # Non-marker means permission for original cleanup, NOT a generic safe
    # error path. An owning/faulted SDK dispatcher must suppress cleanup until
    # its resource policy is satisfied. This byte generator supplies no policy.
    return struct.pack('<11I',0xe92d500f,branch(address+4,0xda84,True),
                       0xe59fc018,0xe150000c,0x0a000001,0xe8bd500f,
                       branch(address+24,0x112fc,False),0xe8bd500f,
                       0xe3a00000,0xe12fff1e,PREPARE_HANDLED)


def patch_prepare_bridge(raw,original,*,profile='external-language'):
    """Patch only a source-composed analysis ELF with an existing mapped slot.

    No DSO dispatcher, authorization/lifetime policy or installer is enabled.
    """
    stock_hash='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
    if hashlib.sha256(original).hexdigest()!=stock_hash:
        raise ValueError('Pinned original Japanese1.11 image required')
    image=ELFFile(io.BytesIO(raw));stock=ELFFile(io.BytesIO(original))
    if image.elfclass!=32 or not image.little_endian or image['e_machine']!='EM_ARM' or image['e_type']!='ET_EXEC':
        raise ValueError('Expected fixed-address ARM32 executable')

    def at(elf,address,count,executable=False):
        segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']]
        if len(segments)!=1 or (executable and not segments[0]['p_flags']&1):
            raise ValueError('Range is not uniquely mapped with required permissions')
        s=segments[0]
        return int(s['p_offset']+address-s['p_vaddr'])

    spans=[]
    for address,count in ((0x112fc,0x378),(0x718c0,0x30),(0x71a3c,0x88),(0xda84,12)):
        location=at(image,address,count,True);baseline=at(stock,address,count,True)
        if raw[location:location+count]!=original[baseline:baseline+count]:
            raise ValueError('Original prepare/action/PID span mismatch')
        spans.append(dict(address=hex(address),bytes=count,sha256=hashlib.sha256(raw[location:location+count]).hexdigest()))
    bridge=prepare_bridge();slot=at(image,PREPARE_BRIDGE,len(bridge),True)
    if raw[slot:slot+len(bridge)]!=bytes(len(bridge)):
        raise ValueError('Planned prepare bridge slot occupied')
    profiles={'external-language':PREPARE_COMPOSITION_SHA,
              'builtin-language':BUILTIN_COMPOSITION_SHA,
              'native-settings':REMOTE_SETTINGS_COMPOSITION_SHA}
    if profile not in profiles or hashlib.sha256(raw).hexdigest()!=profiles[profile]:
        raise ValueError('Source composition profile mismatch')
    result=bytearray(raw);result[slot:slot+len(bridge)]=bridge;sites=[]
    for address in (0x718e0,0x71aa4):
        location=at(image,address,4,True)
        if struct.unpack_from('<I',raw,location)[0]!=branch(address,0x112fc,True):
            raise ValueError('Unexpected original prepare call')
        struct.pack_into('<I',result,location,branch(address,PREPARE_BRIDGE,True));sites.append(hex(address))
    check=ELFFile(io.BytesIO(result))
    if check.header!=image.header or [dict(s.header) for s in check.iter_segments()]!=[dict(s.header) for s in image.iter_segments()]:
        raise ValueError('ELF headers changed')
    return bytes(result),dict(analysis_only=True,ready_to_flash=False,additional_elf_bytes=0,
                             stub=hex(PREPARE_BRIDGE),stub_bytes=len(bridge),callsites=sites,
                             original_spans=spans,stock_sha256=stock_hash)
