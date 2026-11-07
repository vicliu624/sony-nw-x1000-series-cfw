"""Bounded PC replay of original candidate MCS-51 tuner initialization bytes.

SPI, status transitions and readiness are synthetic. No USB or player access.
Unsupported opcodes fail rather than being silently skipped.
"""
import argparse
import hashlib
import json
from pathlib import Path
from extract_fm_mcu_candidate import IMAGE_PIN


class InitReplay:
    def __init__(self, code, seed, complete=True):
        self.code, self.pc = code, 0x46
        self.mem = bytearray(256)
        self.regs = list(seed)
        self.carry = 0
        self.spi = []
        self.transactions = []
        self.selected = False
        self.response = 0
        self.complete = complete
        self.delay_calls = 0
        self.visited = set()
        self.stack = []
        self.call_stack = []
        self.allowed_calls = set()
        self.calls = []
        self.xram = bytearray(65536)
        self.upper_iram = bytearray(128)

    def indirect_read(self, addr):
        return self.mem[addr] if addr < 128 else self.upper_iram[addr-128]

    def indirect_write(self, addr, value):
        if addr < 128:
            self.mem[addr] = value & 255
        else:
            self.upper_iram[addr-128] = value & 255

    def read_code(self, addr):
        if not 0 <= addr < len(self.code):
            raise RuntimeError(('uncovered code read', hex(addr), hex(self.pc)))
        return self.code[addr]

    def register(self, n):
        return (self.mem[0xd0] & 0x18)+n

    def read(self, addr):
        if addr == 0xd0:
            return (self.mem[addr] & 127) | (self.carry << 7)
        if addr == 0xa3:
            return self.response
        if addr == 0xb1:
            return self.mem[addr] | 0x80  # synthetic ready
        return self.mem[addr]

    def write(self, addr, value):
        value &= 255
        self.mem[addr] = value
        if addr == 0xd0:
            self.carry = value >> 7
        if addr != 0xa3 or not self.selected:
            return
        self.spi.append(value)
        if len(self.spi) >= 2:
            reg = ((self.spi[0] & 7) << 1) | (self.spi[1] >> 7)
            word = self.regs[reg]
            self.response = {2: word >> 9, 3: (word >> 1) & 255,
                             4: (word & 1) << 7}.get(len(self.spi), 0)

    def bit(self, addr, value=None):
        if addr == 0xff and value is None:
            return 1  # synthetic SPI completion
        byte = (0x20+addr//8) if addr < 128 else (addr & 0xf8)
        mask = 1 << (addr & 7)
        if value is None:
            return bool(self.read(byte) & mask)
        self.write(byte, (self.read(byte) | mask) if value else (self.read(byte) & ~mask))
        if addr == 0x93:
            if not value:
                self.selected, self.spi = True, []
            elif self.selected:
                assert len(self.spi) == 4, self.spi
                control = (self.spi[0] << 1) | (self.spi[1] >> 7)
                reg, reading = control & 15, bool(control & 0x20)
                word = self.regs[reg] if reading else ((self.spi[1] & 127) << 9) | (self.spi[2] << 1) | (self.spi[3] >> 7)
                self.transactions.append(dict(pc=hex(self.pc), read=reading, register=reg,
                                              value=word, spi_hex=bytes(self.spi).hex()))
                if not reading:
                    self.regs[reg] = word
                    if reg == 3:
                        self.regs[10] = (self.regs[10] | 0x4000) if (word & 0x8000 and self.complete) else (self.regs[10] & ~0x4000)
                self.selected = False

    def run(self, limit=100000, stop=None):
        for count in range(limit):
            pc = self.pc
            if pc == stop or isinstance(stop, (set, tuple)) and pc in stop:
                return count
            self.visited.add(pc)
            op, x, y = self.code[pc:pc+3]
            a = self.read(0xe0)
            step = 1
            branch = None
            if op == 0x12:
                target = x << 8 | y
                self.calls.append(target)
                if target == 0x1b8a:
                    self.delay_calls += 1
                else:
                    assert target in self.allowed_calls, ('unexpected call', hex(pc), hex(target))
                    self.call_stack.append(pc+3)
                    branch = target
                step = 3
            elif op == 0x02:
                branch = x << 8 | y; step = 3
            elif op in (0x22, 0x32):
                if self.call_stack and op == 0x22:
                    branch = self.call_stack.pop()
                else:
                    return count+1
            elif op == 0xc0:
                self.stack.append(self.read(x)); step = 2
            elif op == 0xd0:
                self.write(x, self.stack.pop()); step = 2
            elif op == 0xd3:
                self.carry = 1
            elif op == 0xb3:
                self.carry ^= 1
            elif op == 0xa2:
                self.carry = int(self.bit(x)); step = 2
            elif op == 0x92:
                self.bit(x, self.carry); step = 2
            elif op == 0x73:
                branch = ((self.read(0x83) << 8) | self.read(0x82))+a
            elif op == 0xf4:
                self.write(0xe0, a ^ 255)
            elif op == 0x15:
                self.write(x, self.read(x)-1); step = 2
            elif 0x28 <= op <= 0x2f:
                total = a+self.read(self.register(op-0x28))
                self.write(0xe0, total); self.carry = int(total > 255)
            elif op == 0x74:
                self.write(0xe0, x); step = 2
            elif op == 0x85:
                self.write(y, self.read(x)); step = 3
            elif 0x88 <= op <= 0x8f:
                self.write(x, self.read(self.register(op-0x88))); step = 2
            elif op in (0x76, 0x77):
                self.indirect_write(self.read(self.register(op-0x76)), x); step = 2
            elif op in (0xf6, 0xf7):
                self.indirect_write(self.read(self.register(op-0xf6)), a)
            elif op == 0x90:
                self.write(0x83, x); self.write(0x82, y); step = 3
            elif op == 0x93:
                self.write(0xe0, self.read_code(((self.read(0x83) << 8) | self.read(0x82))+a))
            elif op == 0xa3:
                pointer = ((self.read(0x83) << 8) | self.read(0x82))+1
                self.write(0x83, pointer >> 8); self.write(0x82, pointer)
            elif op in (0xb4, 0xb5):
                rhs = x if op == 0xb4 else self.read(x)
                self.carry = int(a < rhs); step = 3
                if a != rhs:
                    branch = pc+3+(y if y < 128 else y-256)
            elif op == 0x66:
                self.write(0xe0, a ^ self.indirect_read(self.read(self.register(0))))
            elif op == 0x46:
                self.write(0xe0, a | self.indirect_read(self.read(self.register(0))))
            elif op == 0xa4:
                product = a*self.read(0xf0)
                self.write(0xe0, product); self.write(0xf0, product >> 8)
                self.carry = 0
            elif op == 0x34:
                total = a+x+self.carry
                self.write(0xe0, total); self.carry = int(total > 255); step = 2
            elif 0x38 <= op <= 0x3f:
                total = a+self.read(self.register(op-0x38))+self.carry
                self.write(0xe0, total); self.carry = int(total > 255)
            elif op in (0xf2, 0xf3):
                self.xram[(self.read(0xaa) << 8) | self.read(self.register(op-0xf2))] = a
            elif op == 0xe0:
                self.write(0xe0, self.xram[(self.read(0x83) << 8) | self.read(0x82)])
            elif 0x68 <= op <= 0x6f:
                self.write(0xe0, a ^ self.read(self.register(op-0x68)))
            elif 0x18 <= op <= 0x1f:
                r = self.register(op-0x18)
                self.write(r, self.read(r)-1)
            elif 0x98 <= op <= 0x9f:
                total = a-self.read(self.register(op-0x98))-self.carry
                self.write(0xe0, total); self.carry = int(total < 0)
            elif 0xd8 <= op <= 0xdf:
                r = self.register(op-0xd8)
                self.write(r, self.read(r)-1); step = 2
                if self.read(r):
                    branch = pc+2+(x if x < 128 else x-256)
            elif op == 0x75:
                self.write(x, y); step = 3
            elif op == 0xe5:
                self.write(0xe0, self.read(x)); step = 2
            elif op == 0xf5:
                self.write(x, a); step = 2
            elif op == 0xe4:
                self.write(0xe0, 0)
            elif op in (0xe6, 0xe7):
                self.write(0xe0, self.indirect_read(self.read(self.register(op-0xe6))))
            elif op in (0xa6, 0xa7):
                self.indirect_write(self.read(self.register(op-0xa6)), self.read(x)); step = 2
            elif 0x78 <= op <= 0x7f:
                self.write(self.register(op-0x78), x); step = 2
            elif 0x08 <= op <= 0x0f:
                r = self.register(op-0x08)
                self.write(r, self.read(r)+1)
            elif op == 0x14:
                self.write(0xe0, a-1)
            elif op == 0x04:
                self.write(0xe0, a+1)
            elif op == 0xc3:
                self.carry = 0
            elif op in (0xc2, 0xd2):
                self.bit(x, op == 0xd2); step = 2
            elif op in (0x20, 0x30):
                step = 3
                if bool(self.bit(x)) == (op == 0x20):
                    branch = pc+3+(y if y < 128 else y-256)
            elif op == 0x05:
                self.write(x, self.read(x)+1); step = 2
            elif op in (0x53, 0x43, 0x63):
                self.write(x, {0x53: self.read(x) & y, 0x43: self.read(x) | y,
                               0x63: self.read(x) ^ y}[op]); step = 3
            elif op in (0x54, 0x44, 0x64):
                self.write(0xe0, {0x54: a & x, 0x44: a | x, 0x64: a ^ x}[op]); step = 2
            elif op == 0x42:
                self.write(x, self.read(x) | a); step = 2
            elif op in (0x24, 0x25):
                total = a+(x if op == 0x24 else self.read(x))
                self.write(0xe0, total); self.carry = int(total > 255); step = 2
            elif op == 0x94:
                total = a-x-self.carry
                self.write(0xe0, total); self.carry = int(total < 0); step = 2
            elif op == 0xc4:
                self.write(0xe0, (a >> 4) | (a << 4))
            elif op in (0x13, 0x33):
                old = self.carry
                self.carry = (a & 1) if op == 0x13 else (a >> 7)
                self.write(0xe0, ((a >> 1) | (old << 7)) if op == 0x13 else ((a << 1) | old))
            elif op in (0x40, 0x50, 0x60, 0x70, 0x80):
                step = 2
                yes = {0x40: self.carry, 0x50: not self.carry, 0x60: a == 0,
                       0x70: a != 0, 0x80: True}[op]
                if yes:
                    branch = pc+2+(x if x < 128 else x-256)
            elif 0xf8 <= op <= 0xff:
                self.write(self.register(op-0xf8), a)
            elif 0xe8 <= op <= 0xef:
                self.write(0xe0, self.read(self.register(op-0xe8)))
            elif 0x48 <= op <= 0x4f:
                self.write(0xe0, a | self.read(self.register(op-0x48)))
            elif 0xa8 <= op <= 0xaf:
                self.write(self.register(op-0xa8), self.read(x)); step = 2
            else:
                raise AssertionError(('unsupported instruction', hex(pc), hex(op)))
            self.pc = branch if branch is not None else pc+step
        raise RuntimeError(('instruction budget reached', hex(self.pc)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=Path('work/fm-mcu-candidate/candidate.bin'))
    parser.add_argument('--output', type=Path, default=Path('work/fm-mcu-candidate/init-replay.json'))
    args = parser.parse_args()
    code = args.image.read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    results = []
    for initial in (0, 0x1240, 0xa540):
        seed = [0]*16
        seed[2] = initial
        seed[5] = 0xa520
        model = InitReplay(code, seed)
        instructions = model.run()
        writes = [(t['register'], t['value']) for t in model.transactions if not t['read']]
        enabled = (initial & ~0x40) | 1
        assert writes == [(2, enabled), (5, seed[5] | 15), (2, enabled | 0x4000),
                          (3, 0x804a), (3, 0x004a)]
        assert {t['register'] for t in model.transactions} == {2, 3, 5, 10}
        results.append(dict(seed_powercfg=initial, instructions=instructions,
                            delay_calls=model.delay_calls, transactions=model.transactions,
                            visited_instruction_addresses=len(model.visited)))
    stalled = InitReplay(code, [0]*16, complete=False)
    try:
        stalled.run(limit=30000)
        raise AssertionError('Missing synthetic STC unexpectedly completed')
    except RuntimeError:
        assert not any(not t['read'] and t['register'] == 3 and t['value'] == 0x4a for t in stalled.transactions)
    report_writes = []
    for report_id in range(1, 18):
        model = InitReplay(code, [0]*16)
        model.pc = 0xf19  # after PSW save / bank selection in SET fragment
        model.mem[0xd0] = 8
        model.mem[0x2f] = report_id
        words = [(0x4100+i) for i in range(16)]
        for i, word in enumerate(words):
            model.mem[0x30+2*i:0x32+2*i] = word.to_bytes(2, 'big')
        count = model.run(stop=0xffe)
        expected = [(report_id-1, words[0])] if report_id <= 16 else list(enumerate(words))
        assert [(t['register'], t['value']) for t in model.transactions] == expected
        assert all(not t['read'] for t in model.transactions)
        report_writes.append(dict(report_id=report_id, instructions=count, transactions=model.transactions))
    report_reads = []
    read_seed = [0x3200+i for i in range(16)]
    for report_id in range(1, 17):
        model = InitReplay(code, read_seed)
        model.pc, model.mem[0xd0], model.mem[0x72] = 0xdd9, 8, report_id
        count = model.run(stop=0xe3e)
        assert [(t['register'], t['value']) for t in model.transactions] == [(report_id-1, read_seed[report_id-1])]
        assert int.from_bytes(model.mem[0x30:0x32], 'big') == read_seed[report_id-1]
        report_reads.append(dict(report_id=report_id, instructions=count, transactions=model.transactions))
    read_all = InitReplay(code, read_seed)
    read_all.pc, read_all.mem[0xd0] = 0xe48, 8
    read_all_count = read_all.run(stop=0xebf)
    assert [(t['register'], t['value']) for t in read_all.transactions] == list(enumerate(read_seed))
    assert bytes(read_all.mem[0x30:0x50]) == b''.join(v.to_bytes(2, 'big') for v in read_seed)
    assert code[0xebf:0xec6] == bytes.fromhex('78797600087621')
    report = dict(image_sha256=IMAGE_PIN, tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  hardware_access=False, scope='Original MCS-51 bytes at 0046h; synthetic SPI/readiness/status, delay helper omitted',
                  crc_validated=False, cases=results,
                  hid_set_fragment_cases=report_writes,
                  hid_get_fragment_cases=report_reads,
                  hid_get_all_fragment=dict(instructions=read_all_count, transactions=read_all.transactions,
                                            actual_transfer_length_assignment=33, registers_read=16),
                  missing_stc_case=dict(instruction_budget=30000, returned=False,
                                        tune_was_not_cleared=True, last_pc=hex(stalled.pc)))
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(results[0], indent=2))


if __name__ == '__main__':
    main()
