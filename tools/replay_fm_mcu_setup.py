"""PC-only setup dispatch prefixes; stops before handlers or standard switch."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


def main():
    code = Path('work/fm-mcu-candidate/candidate.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    boundaries = {0x77f: 'class_handler_1971', 0x784: 'class_handler_1bcb',
                  0x78f: 'class_get_report', 0x794: 'class_set_report_setup',
                  0x799: 'class_set_report_setup_9', 0x7f2: 'stall',
                  0x7a3: 'nonclass_standard_switch'}
    counts = Counter()
    for request_type in range(256):
        for request in range(256):
            model = StreamReplay(code)
            model.pc, model.mem[0xd0] = 0x766, 8
            model.mem[0x6f:0x71] = bytes((request_type, request))
            model.run(stop=set(boundaries))
            result = boundaries[model.pc]
            expected = 'nonclass_standard_switch'
            if request_type & 0x60 == 0x20:
                expected = {1: 'class_get_report' if request_type & 0x80 else 'class_set_report_setup',
                            9: 'class_set_report_setup_9', 10: 'class_handler_1bcb',
                            129: 'class_handler_1971'}.get(request, 'stall')
            assert result == expected, (request_type, request, result)
            assert not model.transactions and not model.calls
            counts[result] += 1
    # Replay compiler switch helper with its original inline table and abstract
    # return-address bytes. This does not fake the helper's chosen destination.
    table = {0: 0x7c5, 1: 0x7ca, 3: 0x7cf, 5: 0x7d4, 6: 0x7d9,
             8: 0x7de, 9: 0x7e3, 10: 0x7e8, 11: 0x7ed}
    switch_cases = []
    for request in range(256):
        model = StreamReplay(code)
        model.pc, model.mem[0xd0], model.mem[0xe0] = 0x153d, 8, request
        model.stack = [0xa6, 0x07]  # return address after LCALL at 07a3
        model.run(stop=set(table.values()) | {0x7f2})
        assert model.pc == table.get(request, 0x7f2)
        assert not model.stack and not model.transactions
        switch_cases.append(dict(request=request, destination=hex(model.pc)))
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  setup_prefix_cases=65536, outcomes=dict(counts), switch_cases=switch_cases,
                  scope='After setup FIFO read/normalization, before handler execution; compiler switch independently replayed',
                  limits=['Does not validate USB recipient/index/length within downstream handlers.',
                          'Nonclass types share a switch; this does not prove vendor requests are accepted.'])
    Path('work/fm-mcu-candidate/setup-replay.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('65792 setup/switch prefix cases passed')
    print(dict(counts))


if __name__ == '__main__':
    main()
