"""Private JP1.11 Homebrew switch-mode composition, never an installer."""
import hashlib
import io
import struct
from elftools.elf.elffile import ELFFile
from app_registry import ROOT

SWITCH_ARGUMENTS = 0x4d61a0
SWITCH_ARGUMENT_BYTES = 48
SWITCH_ARGUMENT_SHA256 = '19465b18364e4b8ad4f41f3885c4b1235b2bb04c575e8734b0160d2208ecf928'
MODE_INSTRUCTION = 0x4d61c0
QUIT_RELAUNCH = 0xe3a03001
RETAIN_PROCESS = 0xe3a03000


def compose(raw):
    elf = ELFFile(io.BytesIO(raw))
    if elf['e_machine'] != 'EM_ARM' or elf.elfclass != 32 or not elf.little_endian:
        raise ValueError('Expected JP1.11 ARM32 image')
    spans = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'
             and s['p_vaddr'] <= SWITCH_ARGUMENTS
             and SWITCH_ARGUMENTS + SWITCH_ARGUMENT_BYTES <= s['p_vaddr'] + s['p_filesz']]
    if len(spans) != 1 or spans[0]['p_flags'] != 5:
        raise ValueError('Homebrew mode must occupy one read/execute mapping')
    segment = spans[0]
    start = segment['p_offset'] + SWITCH_ARGUMENTS - segment['p_vaddr']
    body = raw[start:start + SWITCH_ARGUMENT_BYTES]
    if hashlib.sha256(body).hexdigest() != SWITCH_ARGUMENT_SHA256:
        raise ValueError('Homebrew argument adapter differs from the reviewed JP1.11 body')
    offset = segment['p_offset'] + MODE_INSTRUCTION - segment['p_vaddr']
    aliases = [(s['p_vaddr'] + offset - s['p_offset'], s['p_flags'])
               for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'
               and s['p_offset'] < offset + 4 and offset < s['p_offset'] + s['p_filesz']]
    if aliases != [(MODE_INSTRUCTION, 5)]:
        raise ValueError('Homebrew mode instruction has an aliased file mapping')
    if struct.unpack_from('<I', raw, offset)[0] != QUIT_RELAUNCH:
        raise ValueError('Expected original quit/relaunch mode')
    result = bytearray(raw)
    struct.pack_into('<I', result, offset, RETAIN_PROCESS)
    restored = bytearray(result)
    restored[offset:offset + 4] = raw[offset:offset + 4]
    assert restored == raw and len(result) == len(raw)
    report = {'analysis_only': True, 'device_accessed': False, 'firmware_created': False,
              'hardware_qualified': False, 'mode': 'retain-process',
              'entry_mode': 0, 'original_entry_mode': 1,
              'instruction_address': hex(MODE_INSTRUCTION), 'elf_growth_bytes': 0,
              'base_sha256': hashlib.sha256(raw).hexdigest(),
              'candidate_sha256': hashlib.sha256(result).hexdigest(),
              'source_hashes': {'tools/homebrew_handoff.py': hashlib.sha256((ROOT / 'tools/homebrew_handoff.py').read_bytes()).hexdigest()},
              'limits': ['Changes only the Homebrew target switch mode; original stock callbacks and manager remain in use.',
                         'Requires complete command6 drain, native resource release and command7 return validation.',
                         'Not a physical Wi-Fi, display/input or application-return qualification.']}
    return bytes(result), report
