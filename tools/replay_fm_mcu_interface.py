"""PC-only SET_INTERFACE handler sweeps using original candidate bytes."""
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


class ReadTrace(StreamReplay):
    def __init__(self, code):
        super().__init__(code)
        self.indirect_reads = set()

    def indirect_read(self, addr):
        self.indirect_reads.add(addr)
        return super().indirect_read(addr)


def case(code, request_type=1, index=1, value=0, length=0):
    model = StreamReplay(code)
    model.pc = 0x1a25
    model.mem[0x6f] = request_type
    model.mem[0x71:0x77] = value.to_bytes(2, 'big')+index.to_bytes(2, 'big')+length.to_bytes(2, 'big')
    model.indirect_write(0x8a, 0xa5)
    model.run(stop={0x1a37, 0x1a5c})
    stalled = model.pc == 0x1a37
    stored = model.indirect_read(0x8a)
    assert stalled == (request_type != 1 or length != 0)
    assert stored == ((value & 255) if not stalled and index == 1 else 0xa5)
    assert not model.transactions and not model.calls
    return dict(type=request_type, index=index, value=value, length=length,
                stalled=stalled, alternate_byte=stored)


def main():
    code = Path('work/fm-mcu-candidate/candidate.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    cases = [case(code, request_type=t) for t in range(256)]
    cases += [case(code, value=v) for v in range(65536)]
    cases += [case(code, index=i, value=7) for i in range(65536)]
    cases += [case(code, length=n) for n in (1, 255, 256, 65535)]
    starts = []
    for alternate in range(256):
        model = ReadTrace(code)
        model.pc = 0x1668
        model.indirect_write(0x8a, alternate)
        model.run()
        assert not model.stack and not model.call_stack
        assert 0x8a not in model.indirect_reads
        assert model.fifo == [0xc4, 0x10, 0x8a, 0x81]
        assert model.bit(0xca) and not model.transactions
        starts.append(dict(alternate=alternate, fifo=model.fifo,
                           usb_writes=model.usb_writes,
                           adc_mux=model.mem[0xbb], timer_running=bool(model.bit(0xca))))
    assert all(row['usb_writes'] == starts[0]['usb_writes'] for row in starts)
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False, cases=len(cases),
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Independent type, value and index sweeps; stops before stall helper or successful epilogue',
                  examples=[case(code, value=v) for v in (0, 1, 2, 255, 256, 257, 65535)],
                  stream_start_cases=starts,
                  limits=['Stored alternate byte is not proof that the mode is implemented.',
                          'No USB hardware or downstream sample scheduler is executed.'])
    Path('work/fm-mcu-candidate/interface-replay.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{len(cases)} SET_INTERFACE scenarios passed')


if __name__ == '__main__':
    main()
