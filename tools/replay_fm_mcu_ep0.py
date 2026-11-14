"""Replay the pinned USB bridge's string descriptor reads through EP0 FIFO."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from extract_fm_mcu_candidate import IMAGE_PIN
from replay_fm_mcu_stream import StreamReplay


WORK = Path("work/fm-mcu-candidate")


class UncoveredRead(RuntimeError):
    pass


class Ep0Replay(StreamReplay):
    def __init__(self, code, index, requested, seed):
        super().__init__(code)
        self.allowed_calls = {0x1133, 0x14d5, 0x14ee, 0x18ec}
        self.accesses = []
        self.pending = bytearray()
        self.packets = []
        self.xram[:1024] = bytes((seed + offset * 13) & 255 for offset in range(1024))
        self.upper_iram[:] = bytes((seed + offset * 7) & 255 for offset in range(128))
        self.mem[0x6f:0x77] = bytes((0x80, 6, 3, index, 4, 9)) + requested.to_bytes(2, "big")
        self.mem[0xaa] = 0  # Synthetic EMI0CN page.
        self.mem[0xd0] = 8
        self.stack = [0]  # Saved PSW from the EP0 handler prologue.
        self.pc = 0x7d9  # Standard request switch destination for GET_DESCRIPTOR.

    def record(self, space, address, value):
        self.accesses.append(dict(pc=self.pc, space=space, address=address, value=value))
        if value is None:
            raise UncoveredRead
        return value

    def read_code(self, addr):
        return self.record("CODE", addr, self.code[addr] if addr < len(self.code) else None)

    def read_xram(self, addr):
        physical = addr & 0x07ff
        if physical >= 0x0400:
            return self.record("USB_FIFO_RAM_UNMODELED", addr, None)
        value = super().read_xram(physical)
        self.accesses.append(dict(pc=self.pc, space="XRAM", address=addr,
                                  physical_address=physical, value=value))
        return value

    def indirect_read(self, addr):
        value = super().indirect_read(addr)
        if self.pc in (0x14e0, 0x1503):
            return self.record("IRAM", addr, value)
        return value

    def read(self, addr):
        if addr == 0x97 and self.mem[0x96] & 127 == 0x11:
            return 0  # Synthetic EP0 IN ready, with no OUT/setup-end/stall flags.
        return super().read(addr)

    def write(self, addr, value):
        super().write(addr, value)
        if addr != 0x97:
            return
        target = self.mem[0x96] & 127
        if target == 0x20:
            self.pending.append(value & 255)
        if target == 0x11 and value & 2:
            self.packets.append(dict(data=self.pending.hex(), csr=value & 255))
            self.pending.clear()


def replay(code, index, requested, seed=130):
    model = Ep0Replay(code, index, requested, seed)
    table_offset = 0x0d99 + 3 * index
    pointer = code[table_offset:table_offset + 3].hex()
    raw_length = transfer_length = None
    outcome = "complete"
    try:
        model.run(stop=0x11e3)
        raw_length = int.from_bytes(model.mem[0x79:0x7b], "big")
        model.run(stop=0x7f5)
        transfer_length = int.from_bytes(model.mem[0x79:0x7b], "big")
        assert transfer_length == min(raw_length, requested), (index, requested, raw_length, transfer_length)
        model.run()
        while model.mem[0x7b] == 1:
            assert len(model.packets) <= 4
            model.pc = 0x6ba
            model.run()
        assert not model.pending
        payload = bytes.fromhex("".join(packet["data"] for packet in model.packets))
        assert len(payload) == transfer_length, (index, requested, transfer_length)
        assert payload == bytes(read["value"] for read in model.accesses[4:])
    except UncoveredRead:
        failure = model.accesses[-1]
        if failure["space"] == "USB_FIFO_RAM_UNMODELED":
            outcome = "usb_fifo_ram_unmodeled"
        elif failure["space"] == "CODE" and failure["address"] > 0x3dff:
            outcome = "flash_error_reset_boundary"
        else:
            outcome = "missing_code_bytes"
    assert not model.transactions
    return dict(index=index, requested=requested, seed=seed, outcome=outcome,
                pointer=pointer,
                raw_length=raw_length, transfer_length=transfer_length, packets=model.packets,
                pending_fifo=model.pending.hex(), reads=model.accesses)


def main():
    code = (WORK / "candidate.bin").read_bytes()
    assert hashlib.sha256(code).hexdigest() == IMAGE_PIN
    cases = [replay(code, index, size) for index in range(256)
             for size in (0, 1, 63, 64, 65, 128, 255, 256, 65535)]
    for index, address in enumerate((0x0d4f, 0x0d53, 0x0d87)):
        for case in (row for row in cases if row["index"] == index):
            expected = code[address:address + min(code[address], case["requested"])]
            assert bytes.fromhex("".join(p["data"] for p in case["packets"])) == expected
    # Independently verify real code payloads and synthetic XRAM across packet boundaries.
    code_case = replay(code, 202, 255)
    assert [len(p["data"]) // 2 for p in code_case["packets"]] == [64, 64, 64, 63]
    assert bytes.fromhex("".join(p["data"] for p in code_case["packets"])) == code[0x0fef:0x10ee]
    xram_case = replay(code, 3, 255, seed=128)
    assert [len(p["data"]) // 2 for p in xram_case["packets"]] == [64, 64, 0]
    assert bytes.fromhex("".join(p["data"] for p in xram_case["packets"])) == bytes(
        (128 + offset * 13) & 255 for offset in range(128))
    # Address decoding and first-access failures are independent of wLength.
    for index in range(256):
        selected = [case for case in cases if case["index"] == index]
        assert len({case["outcome"] for case in selected}) == 1
    assert replay(code, 42, 255)["reads"][3]["physical_address"] == 0x215
    assert replay(code, 50, 255)["reads"][3]["physical_address"] == 0x216
    assert replay(code, 123, 255)["outcome"] == "usb_fifo_ram_unmodeled"
    assert replay(code, 210, 255)["outcome"] == "usb_fifo_ram_unmodeled"
    assert replay(code, 135, 255)["outcome"] == "missing_code_bytes"
    index_outcomes = dict(Counter(case["outcome"] for case in cases
                                  if case["requested"] == 255))
    cases.append(xram_case)
    report = dict(image_sha256=IMAGE_PIN, hardware_access=False,
                  index_outcomes=index_outcomes,
                  source_hashes={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in (Path(__file__).name, "replay_fm_mcu_stream.py",
                                              "replay_fm_mcu_init.py")},
                  scope="Original instructions, synthetic EP0-ready events, IRAM and implemented 1 KiB XRAM; no USB bus",
                  cases=cases)
    (WORK / "ep0-string-replay.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cases)} original-byte EP0 scenarios recorded")
    print(index_outcomes)


if __name__ == "__main__":
    main()
