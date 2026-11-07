"""PC-only original MCS-51 ADC-to-USB fragments, with inert synthetic SFRs."""
import argparse
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_init import InitReplay


class StreamReplay(InitReplay):
    def __init__(self, code):
        super().__init__(code, [0]*16)
        self.fifo = []
        self.usb_writes = []
        self.allowed_calls = {0x1af7, 0x1bfd}

    def read(self, addr):
        if addr == 0x96:
            return self.mem[addr] & 127  # indirect USB register access completes
        return super().read(addr)

    def write(self, addr, value):
        super().write(addr, value)
        if addr == 0x97:
            target = self.mem[0x96] & 127
            self.usb_writes.append(dict(pc=hex(self.pc), register=hex(target), value=value & 255))
            if target == 0x23:
                self.fifo.append(value & 255)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=Path('work/fm-mcu-candidate/candidate.bin'))
    parser.add_argument('--output', type=Path, default=Path('work/fm-mcu-candidate/stream-replay.json'))
    args = parser.parse_args()
    code = args.image.read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    producer_cases = []
    for write_index, read_index in ((0, 0), (254, 0), (255, 1), (20, 21)):
        model = StreamReplay(code)
        model.mem[1:3] = bytes((write_index, read_index))
        model.mem[0xbb] = 9
        for sample in (0x1234, 0xabcd):
            model.mem[0xbd], model.mem[0xbe] = sample & 255, sample >> 8
            model.pc = 0x1a5f
            model.run()
            assert not model.stack and not model.call_stack
        observed = [model.xram[page*256+write_index] for page in range(4)]
        assert observed == [0x34, 0x92, 0xcd, 0x2b]
        expected_index = (write_index+1) & 255
        if expected_index == read_index:
            expected_index = write_index
        assert model.mem[1] == expected_index
        # Use the actual producer output in the actual consumer fragment.
        if write_index == 0:
            model.pc = 0x17a5
            model.run(stop=0x17ff)
            assert model.fifo == observed
            assert model.mem[2] == 1
        producer_cases.append(dict(write_index=write_index, read_index=read_index,
                                   bytes_by_page=observed, producer_after=model.mem[1],
                                   mux_after=model.mem[0xbb]))
    consumers = []
    for available in (0, 1, 2, 96, 97, 98, 200):
        model = StreamReplay(code)
        read_index = 240
        model.mem[1] = (read_index+available) & 255
        model.mem[2] = read_index
        for page in range(4):
            for i in range(256):
                model.xram[page*256+i] = (i+page*31) & 255
        model.pc = 0x17a5
        count = model.run(stop=0x17ff)
        frames = min(available, 97) if available else 256
        expected = [model.xram[page*256+((read_index+i) & 255)]
                    for i in range(frames) for page in range(4)]
        assert model.fifo == expected
        assert model.mem[2] == (read_index+frames) & 255
        assert not model.transactions
        consumers.append(dict(available=available, instructions=count, frames_copied=frames,
                              bytes_to_fifo=len(model.fifo), consumer_after=model.mem[2],
                              bytes_sha256=hashlib.sha256(bytes(model.fifo)).hexdigest()))
    out_irq_cases = []
    for endpoint2_pending in (False, True):
        for timer_running in (False, True):
            model = StreamReplay(code)
            model.mem[0x12] = 4 if endpoint2_pending else 0
            model.mem[0xc8] = 4 if timer_running else 0
            model.mem[0x11] = 8
            model.pc = 0x12b8
            model.run(stop=0x12c6)
            active = endpoint2_pending and timer_running
            assert model.calls == ([0x1af7, 0x1bfd] if active else [])
            assert model.mem[0x11] == (0 if active else 8)
            assert not model.fifo and not model.transactions
            # No read of OUT FIFO 2 occurs in this interrupt branch.
            out_irq_cases.append(dict(endpoint2_pending=endpoint2_pending, timer_running=timer_running,
                                      calls=[hex(c) for c in model.calls], usb_writes=model.usb_writes))
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False, original_crc_validated=False,
                  tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  producer_cases=producer_cases, consumer_cases=consumers,
                  endpoint2_out_interrupt_cases=out_irq_cases,
                  scope='Original bytes, synthetic ADC/registers/RAM, immediate USB readiness, abstract stack; no concurrent interrupts',
                  limits=['Endpoint-2 IRQ fragment does not prove every possible use of HID report 23.',
                          'FIFO byte writes are not USB bus delivery or measured audio/IQ.',
                          'Zero available frames underflow DJNZ and copy 256 frames in this fixed-pointer model.'])
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{len(producer_cases)+len(consumers)+len(out_irq_cases)} original-byte scenarios passed; ADC producer -> FIFO 3 byte order verified')


if __name__ == '__main__':
    main()
