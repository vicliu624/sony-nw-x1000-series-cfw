"""Exhaustive byte-state sweeps of the candidate's original mode helper, PC only."""
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


def main():
    code = Path('work/fm-mcu-candidate/candidate.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    visited = set()
    digest = hashlib.sha256()
    cases = 0
    # Sweep requests independently of existing mode; then all existing mode/phase
    # pairs without a request, including every computed jump-table index.
    for sweep in ('request_mode', 'mode_phase'):
        for first in range(256):
            for second in range(256):
                model = StreamReplay(code)
                model.pc = 0x958
                model.mem[0x2b] = second if sweep == 'request_mode' else first
                model.mem[0x2c] = 0 if sweep == 'request_mode' else second
                model.mem[0x2e] = first if sweep == 'request_mode' else 0
                model.run(limit=1000)
                assert not model.calls and not model.transactions and not model.usb_writes
                assert not model.stack
                assert all(0x958 <= pc <= 0xbe0 for pc in model.visited)
                visited.update(model.visited)
                digest.update(model.mem)
                cases += 1
    # Exercise nonzero countdown and representative peripheral boundary values.
    for delay in (1, 2, 255):
        model = StreamReplay(code)
        model.pc = 0x958
        model.mem[0x2d] = delay
        model.run()
        assert model.mem[0x2d] == delay-1 and not model.transactions
        cases += 1
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False, cases=cases,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  visited_addresses=[hex(pc) for pc in sorted(visited)],
                  final_ram_digest=digest.hexdigest(),
                  scope='Independent exhaustive request/mode and mode/phase sweeps; zero initial countdown and peripheral SFRs',
                  limits=['Not exhaustive across all joint RAM/SFR states.',
                          'Peripheral effects and physical board wiring are not modeled.'],
                  tuner_transactions=0, helper_calls=0, usb_writes=0)
    Path('work/fm-mcu-candidate/mode-replay.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{cases} mode-helper scenarios passed; {len(visited)} instruction addresses; no tuner transactions')


if __name__ == '__main__':
    main()
