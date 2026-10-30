"""Prepare a local RADIO-only candidate; never installs or contacts hardware.

Requires exact original inputs. One stock large packet block is removed from
its free list and reserved; scatter zeroing skips that block. No partition,
kernel, module, system updater or Sony application image is generated/modified.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
from elftools.elf.elffile import ELFFile
from marvell_firmware import Record, parse, serialize

ROOT = Path(__file__).resolve().parents[1]
STOCK_SHA = '08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
HELPER_SHA = 'b0157d1f4518e806c0bc5128ab302a7f97d78ee34b84cb41cb4f2bbbb2a00e6d'
RESERVED_START, RESERVED_END = 0xc000a190, 0xc000a8fc
BSS_START, BSS_END = 0xc0006e70, 0xc0017da4


def memory(records):
    result = {}
    for record in records:
        if record.command != 1:
            continue
        for offset, byte in enumerate(record.data):
            address = record.address + offset
            if address in result:
                raise ValueError('overlapping loaded records')
            result[address] = byte
    return result


def construct(stock: bytes, elf_path: Path):
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA:
        raise ValueError('unqualified original radio image')
    records = parse(stock)
    if serialize(records) != stock:
        raise ValueError('original roundtrip mismatch')
    original = memory(records)
    reservation = bytearray(RESERVED_END - RESERVED_START)
    with elf_path.open('rb') as f:
        elf = ELFFile(f)
        if elf['e_machine'] != 'EM_ARM':
            raise ValueError('radio payload is not ARM')
        allowed = {'.text', '.state'}
        for section in elf.iter_sections():
            if not section['sh_flags'] & 2 or not section['sh_size']:
                continue
            if section.name not in allowed or section['sh_type'] == 'SHT_NOBITS':
                raise ValueError('unexpected payload section')
            start = section['sh_addr']
            end = start + section['sh_size']
            if not RESERVED_START <= start < end <= RESERVED_END:
                raise ValueError('payload exceeds reserved block')
            reservation[start-RESERVED_START:end-RESERVED_START] = section.data()
        symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        entry, state = symbols['xnow_radio_receive'], symbols['xnow_radio_state']
    if not entry & 1 or not RESERVED_START <= (entry & ~1) < RESERVED_END:
        raise ValueError('invalid Thumb entry')
    if not RESERVED_START <= state <= RESERVED_END-92:
        raise ValueError('invalid mailbox range')
    if struct.unpack_from('<I', reservation, state-RESERVED_START)[0] != 0x31524e58:
        raise ValueError('mailbox identity missing')
    patches = [
        (0x163ee, bytes.fromhex('0422'), bytes.fromhex('0322'), 'large pool four blocks to three'),
        (0xc00026b0, struct.pack('<I', 0xa315), struct.pack('<I', entry), 'management receive veneer target'),
        (0x17328, struct.pack('<II', BSS_START, BSS_END-BSS_START),
         struct.pack('<II', BSS_START, RESERVED_START-BSS_START), 'first BSS zero range'),
        (0x17338, struct.pack('<II', 0x17340, 0),
         struct.pack('<II', RESERVED_END, BSS_END-RESERVED_END), 'remaining BSS zero range'),
    ]
    plan = []
    expected_changes = {}
    for address, before, after, purpose in patches:
        actual = bytes(original[address+i] for i in range(len(before)))
        if actual != before or len(before) != len(after):
            raise ValueError('patch precondition failed: '+purpose)
        for i, value in enumerate(after):
            expected_changes[address+i] = value
        plan.append({'address': hex(address), 'before': before.hex(), 'after': after.hex(), 'purpose': purpose})
    for i, record in enumerate(records):
        if record.command == 1:
            data = bytes(expected_changes.get(record.address+j, value) for j, value in enumerate(record.data))
            records[i] = replace(record, data=data)
    extra = [Record(1, RESERVED_START+i, bytes(reservation[i:i+508])) for i in range(0, len(reservation), 508)]
    records[-1:-1] = extra
    image = serialize(records)
    verified = memory(parse(image))
    for address, byte in original.items():
        if verified[address] != expected_changes.get(address, byte):
            raise ValueError('unexpected original-image change')
    added = set(verified) - set(original)
    if added != set(range(RESERVED_START, RESERVED_END)):
        raise ValueError('unexpected loaded-memory addition')
    # Set equality of zeroed addresses proves no unrelated BSS byte is skipped.
    old_zero = set(range(BSS_START, BSS_END))
    new_zero = set(range(BSS_START, RESERVED_START)) | set(range(RESERVED_END, BSS_END))
    if old_zero - new_zero != added or new_zero - old_zero:
        raise ValueError('incorrect BSS exclusion')
    report = {
        'radio_only': True, 'original_sha256': STOCK_SHA,
        'candidate_sha256': hashlib.sha256(image).hexdigest(),
        'original_bytes': len(stock), 'candidate_bytes': len(image),
        'pool_blocks_before': 4, 'pool_blocks_after': 3,
        'reserved_start': hex(RESERVED_START), 'reserved_end': hex(RESERVED_END),
        'reserved_bytes': len(reservation), 'mailbox_address': hex(state),
        'mailbox_bytes': 92, 'thumb_entry': hex(entry), 'patches': plan,
        'all_other_loaded_bytes_unchanged': True, 'crc_roundtrip_passed': True,
        'all_other_bss_zeroing_preserved': True,
        'other_users_audited': False, 'driver_reload_qualified': False,
        'hardware_tested': False, 'device_written': False,
    }
    return image, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--payload', type=Path, default=ROOT/'work/espnow-radio-bridge/bridge.elf')
    parser.add_argument('--output', type=Path, default=ROOT/'work/espnow-radio-candidate')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'work').resolve()) or output.exists():
        raise ValueError('output must be a new directory under project work/')
    helper = args.helper.read_bytes()
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA:
        raise ValueError('unqualified original helper')
    stock = args.original.read_bytes()
    image, report = construct(stock, args.payload)
    for name, data in [('candidate', image), ('stock', stock)]:
        folder = output/name
        folder.mkdir(parents=True)
        (folder/'sd8686.bin').write_bytes(data)
        (folder/'helper_sd.bin').write_bytes(helper)
    (output/'review.json').write_text(json.dumps(report, indent=2))
    (output/'README.txt').write_text('RADIO-ONLY LOCAL CANDIDATE. NOT INSTALLED.\n'
        'Never use the Sony system updater for these files.\n'
        'One large packet block is reserved; throughput/ownership/reload need hardware qualification.\n'
        'No loader or automatic installation script is supplied at this stage.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
