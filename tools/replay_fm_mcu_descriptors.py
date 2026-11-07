"""Original descriptor selection prefixes; no USB transfer or guessed memory."""
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


def main():
    code = Path('work/fm-mcu-candidate/candidate.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    rows = []
    for kind in range(256):
        for index in range(256):
            model = StreamReplay(code)
            model.pc = 0x1133
            model.mem[0x71:0x73] = bytes((kind, index))
            model.run(stop={0x11a9, 0x11e0, 0x11e3})
            stalled = model.pc == 0x11e0
            assert stalled == (kind not in (1, 2, 3, 0x21, 0x22))
            pointer = [model.indirect_read(a) for a in (0x7f, 0x80, 0x81)]
            if kind == 3:
                offset = 0xd99+3*index
                assert pointer == list(code[offset:offset+3])
            assert not model.transactions and not model.calls
            if not stalled:
                rows.append(dict(kind=kind, index=index, pointer=pointer,
                                 stop_pc=hex(model.pc)))
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False, cases=65536,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  selected=rows,
                  scope='Descriptor selection only; stops before string pointer dereference or length/transfer logic',
                  limits=['Out-of-range string index selects code bytes as a pointer; not proof of successful memory disclosure.',
                          'No hidden descriptor or IQ stream established.'])
    Path('work/fm-mcu-candidate/descriptor-selection-replay.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('65536 descriptor-selection cases passed; string index is not range-checked before table lookup')


if __name__ == '__main__':
    main()
