"""Original dispatch/allocator replay of the exact maintained frame-transaction image."""

import contextlib
import ctypes
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import time
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R4,
    UC_ARM_REG_R5,
    UC_ARM_REG_R7,
    UC_ARM_REG_SP,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
)

from app_registry import ROOT as root
from radio_test_profile import selected_radio
from build_espnow_full_radio import build

out = root / "work/radio-frame-transaction-tests" / str(time.time_ns())
out.mkdir(parents=True)
selected = selected_radio()
if selected:
    payload, manifest = selected
else:
    folder = out / "radio-build"
    manifest = build(
        root / "work/targets-jp/sd8686.bin",
        root / "work/espnow-full-radio-review-3/stock/helper_sd.bin",
        folder,
        rx_diagnostics=True,
        frame_transactions=True,
    )
    payload = folder / "radio.elf"
assert manifest.get("frame_transactions") and manifest["rx_diagnostics"]
with contextlib.redirect_stdout(io.StringIO()):
    env = runpy.run_path(str(root / "tools/test_radio_packet_ownership.py"))
cpu, put, word, call, free_count = [
    env[n] for n in ("cpu", "put", "word", "call", "free_count")
]
with payload.open("rb") as stream:
    elf = ELFFile(stream)
    sections = [
        (s["sh_addr"], s.data())
        for s in elf.iter_sections()
        if s["sh_flags"] & 2 and s["sh_size"]
    ]
    symbols = {
        s.name: s["st_value"]
        for s in elf.get_section_by_name(".symtab").iter_symbols()
        if s.name
    }
assert max(a + len(b) for a, b in sections) <= 0xC000A8FC
for a, b in sections:
    cpu.mem_write(a, b)
for patch in manifest["patches"]:
    cpu.mem_write(patch["address"], bytes.fromhex(patch["after"]))
tx = symbols["xnow_full_tx"]
completion = symbols["xnow_tx_completion"]
request, response = 0xC00155B8, 0xC0014E4C
copies = []
saved = {}


def hook(u, pc, n, unused):
    if pc == 0x88D6:
        saved.update(
            (r, u.reg_read(r))
            for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R7, UC_ARM_REG_SP)
        )
    elif pc == 0x9A46:
        assert all(u.reg_read(r) == v for r, v in saved.items())
    elif pc == 0x9A70:
        u.emu_stop()
    elif pc == 0x9C90:
        dst, src, length = [
            u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)
        ]
        assert 0 <= length <= (1500 if dst == response else 1536)
        copies.append((dst, src, length))
        u.mem_write(dst, bytes(u.mem_read(src, length)))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))


cpu.hook_add(UC_HOOK_CODE, hook)


def command(action, body, size=None, count=0, address=0xC000D5A8):
    size = 16 + len(body) if size is None else size
    packet = (
        struct.pack("<4H", 0x86, size, 0x55AA, 0)
        + struct.pack("<HHI", action, count, address)
        + body
    )
    cpu.mem_write(request, packet)
    cpu.mem_write(response, b"\xa5" * 1600)
    cpu.mem_write(0xC0007859, b"\x01")
    cpu.mem_write(0xC000EDF4, b"\0")
    cpu.mem_write(0xC001452A, b"\x01")
    cpu.reg_write(UC_ARM_REG_SP, 0x208000)
    cpu.emu_start(0x8079, 0x9B40, count=50000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x9A70
    returned = struct.unpack("<H", cpu.mem_read(response + 2, 2))[0]
    assert 16 <= returned <= 1500 and copies[-1] == (response, request, returned)
    assert bytes(cpu.mem_read(response + returned, 4)) == b"\xa5" * 4
    result = bytes(cpu.mem_read(response, returned))
    assert struct.unpack_from("<H", result)[0] == 0x8086
    return struct.unpack_from("<H", result, 6)[0], result


def fragment(
    total, data, offset=0, kind=4, wanted=None, mac=bytes.fromhex("0266778899aa"), **kw
):
    wanted = word(tx + 8) if wanted is None else wanted
    wire = (
        struct.pack("<III", total, wanted, kind)
        + mac
        + b"\0\0"
        + data
        + bytes((-len(data)) % 4)
    )
    status, result = command(2, wire, count=offset, **kw)
    if status:
        return status, None
    assert len(result) == 36 and struct.unpack_from("<I", result, 16)[0] == 0x314D5246
    assert struct.unpack_from("<I", result, 28)[0] == wanted
    return 0, dict(
        ack=struct.unpack_from("<I", result, 20)[0],
        result=ctypes.c_int32(struct.unpack_from("<I", result, 24)[0]).value,
        packet=struct.unpack_from("<I", result, 32)[0],
    )


def finish():
    p = word(completion)
    assert p and free_count() == 2
    token = word(completion + 4)
    claim = call(symbols["xnow_radio_tx_observe"], p, 0, 0x70302)
    assert call(0x1360, p) == 0 and free_count() == 3
    call(symbols["xnow_radio_tx_released"], claim)
    status, data = command(3, struct.pack("<7I", token, 0, 0, 0, 0, 0, 0))
    assert (
        not status
        and len(data) == 44
        and struct.unpack_from("<4I", data, 16) == (0x314D5246, token, 0, 0)
    )
    assert word(completion + 20) == token and not word(completion)


def abort():
    status, result = fragment(0, b"")
    assert (
        not status
        and result["result"] == 0
        and not result["packet"]
        and free_count() == 3
    )


env["queue_result"][0] = 0
cases = []
for n in (31, 120, 1208, 1424, 1464, 1465, 1520, 1536):
    body = bytearray((i * 17 + 3) & 255 for i in range(n))
    body[2:4] = b"\0\x20"
    count = len(env["queued"])
    initial = word(tx + 8)
    for offset in range(0, n, 1464):
        part = body[offset : offset + 1464]
        status, result = fragment(n, part, offset)
        assert not status and not result["result"]
        if offset + len(part) < n:
            assert (
                result["packet"] and free_count() == 2 and len(env["queued"]) == count
            )
            # The same fragment cannot be silently appended/committed twice.
            status, repeat = fragment(n, part, offset, wanted=initial)
            assert not status and repeat["result"] == -7
    assert (
        len(env["queued"]) == count + 1 and free_count() == 2 and not result["packet"]
    )
    p = word(completion)
    assert bytes(cpu.mem_read(p + 32, n)) == body
    assert struct.unpack("<H", cpu.mem_read(p, 2))[0] == n
    assert bytes(cpu.mem_read(p + 2, 2)) == b"\xd0\x40"
    finish()
    cases.append(
        dict(body_bytes=n, commands_to_submit=(n + 1463) // 1464, byte_exact=True)
    )
# A retained fragment must finish without allocating again when native traffic
# owns the two remaining blocks. Completion returns only our own packet.
body = bytearray(1536)
body[3] = 0x20
status, stage = fragment(len(body), body[:1464])
assert not status and not stage["result"]
neighbors = [call(0xD458, 1900) for _ in range(2)]
assert all(neighbors) and free_count() == 0
status, submitted = fragment(len(body), body[1464:], 1464)
assert not status and not submitted["result"] and free_count() == 0
p = word(completion)
token = word(completion + 4)
assert p not in neighbors and bytes(cpu.mem_read(p + 32, len(body))) == body
claim = call(symbols["xnow_radio_tx_observe"], p, 0, 0x70302)
assert call(0x1360, p) == 0 and free_count() == 1
call(symbols["xnow_radio_tx_released"], claim)
status, _ = command(3, struct.pack("<7I", token, 0, 0, 0, 0, 0, 0))
assert not status
for neighbor in neighbors:
    assert call(0x1360, neighbor) == 0
assert free_count() == 3
status, stage = fragment(1536, bytes(1464))
assert not status and not stage["result"] and free_count() == 2
status, bad = fragment(1536, bytes(72), 1464, mac=b"\0" * 6)
assert not status and bad["result"] == -5 and word(tx + 24) and free_count() == 2
abort()
abort()
# Frame shape/offset rejection must not allocate or mutate the retained stage.
for kw in (
    dict(total=31, data=bytes(31), size=1552),
    dict(total=31, data=bytes(31), size=35),
    dict(total=31, data=bytes(31), offset=4),
    dict(total=31, data=bytes(31), address=0x8000A300),
    dict(total=1537, data=bytes(1464)),
    dict(total=31, data=b""),
):
    before = free_count()
    status, result = fragment(**kw)
    assert (
        (status == 2 or result["result"] == -7)
        and free_count() == before
        and not word(tx + 24)
    )
env["queue_result"][0] = 1
body = bytearray(31)
body[3] = 0x20
status, rejected = fragment(len(body), body)
assert (
    not status
    and rejected["result"] == -1
    and free_count() == 3
    and not word(completion)
)
put(0xC000D5A8, 0x0004076C)
status, _ = fragment(31, body)
assert status == 2 and free_count() == 3 and not word(tx + 24)
put(0xC000D5A8, 0x0003076C)
# Read-vector results remain read-only and echo their addresses.
addresses = [symbols["xnow_radio_frame_commands"], 0xC000D5A8, tx, tx + 8, completion]
vector = b"".join(struct.pack("<II", a, 0) for a in addresses)
status, data = command(0x100, vector, count=2 * len(addresses))
assert not status
for i, a in enumerate(addresses):
    assert struct.unpack_from("<II", data, 16 + i * 8) == (a, word(a))
inputs = [
    *manifest["source_hashes"],
    "tools/test_radio_frame_transactions.py",
    "tools/test_radio_packet_ownership.py",
    "tools/radio_test_profile.py",
    "tools/generate_espnow_full_profile.py",
]
report = dict(
    passed=True,
    occupied_span_bytes=manifest["occupied_span_bytes"],
    cases=cases,
    explicit_abort=True,
    retains_rx_diagnostics=True,
    original_dispatch_response_allocator_header_submit_release=True,
    queue_rejection_frees_once=True,
    duplicate_fragment_refused=True,
    read_vector_tested=True,
    full_pool_fragment_completion_preserves_neighbors=True,
    unreserved_pool_refused=True,
    rom_queue_irq_and_memcpy_modeled=True,
    hardware_qualified=False,
    device_accessed=False,
    native_adapter_tested=False,
    payload_sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),
    candidate_sha256=manifest["candidate_sha256"],
    source_hashes={
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in sorted(set(inputs))
    },
)
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(output=str(out), **report), indent=2))
