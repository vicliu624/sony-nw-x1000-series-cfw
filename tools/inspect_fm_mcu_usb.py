"""Decode actual USB descriptors in the pinned MCU candidate, PC-only."""
import argparse
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=Path('work/fm-mcu-candidate/candidate.bin'))
    parser.add_argument('--output', type=Path, default=Path('work/fm-mcu-candidate/usb-descriptors.json'))
    args = parser.parse_args()
    b = args.image.read_bytes()
    assert hashlib.sha256(b).hexdigest() == IMAGE_PIN
    device = b[0xbe1:0xbf3]
    assert device[:2] == bytes((18, 1))
    assert device[8:12] == bytes.fromhex('c4108a81')
    start = 0xbf3
    end = start+int.from_bytes(b[start+2:start+4], 'little')
    descriptors, interfaces, endpoints, formats = [], [], [], []
    p, interface, alternate = start, None, None
    while p < end:
        n, kind = b[p:p+2]
        assert n >= 2 and p+n <= end
        d = b[p:p+n]
        descriptors.append(dict(offset=hex(p), kind=kind, bytes=d.hex()))
        if kind == 4:
            interface, alternate = d[2:4]
            interfaces.append(dict(number=interface, alternate=alternate, endpoints=d[4],
                                   usb_class=d[5], subclass=d[6], protocol=d[7]))
        elif kind == 5:
            endpoints.append(dict(interface=interface, alternate=alternate, address=hex(d[2]),
                                  transfer_type=d[3] & 3,
                                  max_packet=int.from_bytes(d[4:6], 'little'), interval=d[6]))
        elif kind == 0x24 and interface == 1 and d[2] == 2:
            assert d[3] == 1 and d[7] > 0
            formats.append(dict(channels=d[4], subframe_bytes=d[5], resolution_bits=d[6],
                                sample_rates=[int.from_bytes(d[i:i+3], 'little')
                                              for i in range(8, 8+3*d[7], 3)]))
        p += n
    assert p == end == 0xc84
    # HID short items: all encountered descriptors use the ordinary format.
    report_end = end+0xcb
    state = dict(size=0, count=0, report=0)
    reports = {}
    while p < report_end:
        prefix = b[p]
        assert prefix != 0xfe, 'Unexpected HID long item'
        size = (0, 1, 2, 4)[prefix & 3]
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        assert p+1+size <= report_end
        value = int.from_bytes(b[p+1:p+1+size], 'little')
        if kind == 1:
            if tag in (7, 8, 9):
                state[{7: 'size', 8: 'report', 9: 'count'}[tag]] = value
            assert tag not in (10, 11), 'HID global stack not implemented'
        elif kind == 0 and tag in (8, 9, 11):
            key = (state['report'], {8: 'input', 9: 'output', 11: 'feature'}[tag])
            reports[key] = reports.get(key, 0)+state['size']*state['count']
        p += 1+size
    assert p == report_end
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False, original_crc_validated=False,
                  device=dict(vid='0x10c4', pid='0x818a', usb_version=hex(int.from_bytes(device[2:4], 'little'))),
                  interfaces=interfaces, endpoints=endpoints, audio_formats=formats,
                  hid_reports=[dict(id=k[0], kind=k[1], payload_bits=v,
                                    wire_bytes=(v+7)//8+int(k[0] != 0))
                               for k, v in sorted(reports.items())], descriptors=descriptors,
                  limits=['Descriptors identify advertised formats, not actual stream producer or RF samples.',
                          'HID report IDs are MCU protocol identifiers, not Si470x command opcodes.'])
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('audio_formats', 'endpoints', 'hid_reports')}, indent=2))


if __name__ == '__main__':
    main()
