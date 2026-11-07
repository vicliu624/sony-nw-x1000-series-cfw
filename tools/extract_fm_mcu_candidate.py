"""Extract a pinned, third-party-retained USB-radio MCU image for PC analysis.

No hardware access, updater execution or firmware publication. XOR decoding is
a candidate backed by recognizable MCS-51 code, not CRC-authenticated firmware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PIN = 'b3b833cfcdb2e2f16e497784e6bcac58281717aebcc2889252ab4009f7485f89'
IMAGE_PIN = '858660efc61badf83544b4c00a4f393d813d3e7abbb31d1228430a828fe3f0a5'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('work/fm-driver-comparison/iancass-FMRadioMCUImage.h'))
    parser.add_argument('--output', type=Path, default=Path('work/fm-mcu-candidate'))
    args = parser.parse_args()
    source = args.input.read_bytes()
    if hashlib.sha256(source).hexdigest() != PIN:
        raise ValueError('Input differs from inspected MCU image header')
    body = source.decode('ascii').split('g_MCUCurrentImage[] = {', 1)[1].split('};', 1)[0]
    encoded = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', body))
    assert len(encoded) == 15*515
    pages = [encoded[i:i+515] for i in range(0, len(encoded), 515)]
    assert sorted(p[0] for p in pages) == list(range(15))
    image = bytearray(15*512)
    metadata = []
    for page in pages:
        address = page[0]*512
        image[address:address+512] = bytes(x ^ 0x55 for x in page[1:513])
        metadata.append(dict(page=page[0], address=address, stored_crc_hex=page[513:].hex()))
    assert hashlib.sha256(image).hexdigest() == IMAGE_PIN
    assert image[:3] == bytes.fromhex('021563')  # LJMP 1563h
    assert image[0x1563:0x156a] == bytes.fromhex('787fe4f6d8fd75')
    # Standard Intel HEX records; reconstruct them independently before output.
    records = []
    restored = bytearray(len(image))
    for address in range(0, len(image), 16):
        payload = image[address:address+16]
        record = bytes((len(payload), address >> 8, address & 255, 0))+payload
        line = ':'+(record+bytes((-sum(record) & 255,))).hex().upper()
        check = bytes.fromhex(line[1:])
        assert sum(check) & 255 == 0
        target = int.from_bytes(check[1:3], 'big')
        restored[target:target+check[0]] = check[4:-1]
        records.append(line)
    assert restored == image
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'candidate.bin').write_bytes(image)
    (args.output/'candidate.hex').write_text('\n'.join(records+[':00000001FF'])+'\n', encoding='ascii')
    report = dict(input_sha256=PIN, decoded_candidate_sha256=IMAGE_PIN,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  page_size=512, record_size=515, page_count=15, decoded_bytes=len(image),
                  payload_xor=85, pages=metadata, stored_crc_validated=False,
                  reset_target='0x1563', hardware_access=False,
                  limitations=['Third-party-retained header; vendor-release provenance not authenticated.',
                               'Page CRC algorithm/coverage unresolved; no CRC pass claimed.',
                               'Not a Si4702/03 internal firmware image or a demonstrated IQ mode.',
                               'Uncovered bootloader/flash space is not silently padded into the artifact.'])
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'Extracted {len(image)} candidate bytes; 15 unique pages; Intel HEX round trip passed; CRC unresolved')


if __name__ == '__main__':
    main()
