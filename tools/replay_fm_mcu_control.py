"""PC-only bounded GET/SET handler-prefix replay; external flash fails closed."""
import hashlib
import json
from pathlib import Path
from collections import Counter
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


def trace(code, direction, report_id, command=0):
    model = StreamReplay(code)
    model.pc = 0xda6 if direction == 'get' else 0xf14
    model.mem[0x72] = model.mem[0x2f] = report_id
    model.mem[0x30] = command
    stops = ({0xf11: 'response_epilogue', 0xef2: 'stall',
              } if direction == 'get' else
             {0xffe: 'register_write_epilogue', 0x103b: 'stall',
              0x102f: 'mode_helper_boundary', 0x1036: 'flash_writer_boundary',
              0x103e: 'return'})
    try:
        count = model.run(stop=set(stops))
        outcome = stops[model.pc]
    except RuntimeError as error:
        if error.args[0][0] != 'uncovered code read':
            raise
        outcome = 'uncovered_code_read'
        count = None
    return dict(direction=direction, report_id=report_id, command=command,
                outcome=outcome, stop_pc=hex(model.pc), instructions=count,
                transactions=model.transactions)


def main():
    code = Path('work/fm-mcu-candidate/candidate.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    cases = [trace(code, direction, rid) for direction in ('get', 'set')
             for rid in range(256)]
    commands = [trace(code, 'set', 19, command) for command in range(256)]
    for direction in ('get', 'set'):
        subset = [c for c in cases if c['direction'] == direction]
        for case in subset:
            rid = case['report_id']
            expected = ('response_epilogue' if direction == 'get' else
                        'register_write_epilogue') if 1 <= rid <= 17 else 'stall'
            if direction == 'get' and rid == 20:
                expected = 'uncovered_code_read'
            if direction == 'get' and rid == 22:
                expected = 'response_epilogue'
            if direction == 'set' and rid == 20:
                expected = 'flash_writer_boundary'
            assert case['outcome'] == expected, case
            assert len(case['transactions']) == (16 if rid == 17 else 1 if 1 <= rid <= 16 else 0), case
    for case in commands:
        expected = {0x34: 'uncovered_code_read', 0x35: 'mode_helper_boundary'}.get(case['command'], 'stall')
        assert case['outcome'] == expected, case
        assert not case['transactions'], case
    # Indirect upper IRAM must not alias SFRs, including SP and port 0.
    model = StreamReplay(code)
    model.indirect_write(0x80, 0x55)
    model.indirect_write(0x81, 0x66)
    assert model.mem[0x80] == model.mem[0x81] == 0
    assert model.indirect_read(0x80) == 0x55 and model.indirect_read(0x81) == 0x66
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Handler prefixes from original bytes, synthetic SPI/USB readiness; helper boundaries stop before execution',
                  limits=['Not an end-to-end USB request replay.',
                          'External flash reads are not filled with guessed bytes.',
                          'Mode helper and flash writer are not executed.'],
                  report_cases=cases, command_cases=commands)
    Path('work/fm-mcu-candidate/control-replay.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{len(cases)+len(commands)} handler-prefix cases passed')
    print(dict(Counter(c['outcome'] for c in cases+commands)))


if __name__ == '__main__':
    main()
