"""Replay the original driver payload copy and networking ioctl copyback."""

from pathlib import Path
import hashlib
import json
import struct
import time
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R4,
    UC_ARM_REG_R5,
    UC_ARM_REG_R6,
    UC_ARM_REG_R7,
    UC_ARM_REG_R10,
    UC_ARM_REG_SP,
    UC_ARM_REG_R11,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
)
from app_registry import ROOT

module = ROOT / "work/targets-jp/sd8686.ko"
assert (
    hashlib.sha256(module.read_bytes()).hexdigest()
    == "2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69"
)
kernel = (ROOT / "work/upg-jp/verified-1.bin").read_bytes()
kernel_sha = hashlib.sha256(kernel).hexdigest()
assert kernel_sha == "6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645"
kernel_base, net_begin, net_end = 0xC0008000, 0xC01A0C20, 0xC01A0C7C
net_copy, net_unlock = 0xC00F58B0, 0xC01A7C38
base, start, end = 0x100000, 0x3F38, 0x3FA0
stubs = {"__arch_copy_to_user": 0x700000, "kfree": 0x700010}
with module.open("rb") as stream:
    elf = ELFFile(stream)
    code = bytearray(elf.get_section_by_name(".text").data())
    relocs = elf.get_section_by_name(".rel.text")
    symbols = elf.get_section(relocs["sh_link"])
    relocated = []
    for relocation in relocs.iter_relocations():
        offset = relocation["r_offset"]
        if not start <= offset < end:
            continue
        assert relocation["r_info_type"] == 1  # Original ARM PC24 module relocation.
        symbol = symbols.get_symbol(relocation["r_info_sym"])
        instruction = struct.unpack_from("<I", code, offset)[0]
        immediate = instruction & 0xFFFFFF
        if immediate & 0x800000:
            immediate -= 1 << 24
        if symbol["st_shndx"] == "SHN_UNDEF":
            target = stubs[symbol.name] + immediate * 4 + 8
        else:
            assert elf.get_section(symbol["st_shndx"]).name == ".text"
            target = base + symbol["st_value"] + immediate * 4 + 8
        displacement = target - (base + offset + 8)
        assert not displacement & 3
        struct.pack_into(
            "<I",
            code,
            offset,
            (instruction & 0xFF000000) | ((displacement // 4) & 0xFFFFFF),
        )
        relocated.append(
            dict(offset=hex(offset), target=hex(target), symbol=symbol.name)
        )

cases = []
for input_bytes, length, copy_fault in (
    (1500, 16, False),
    (148, 36, False),
    (44, 44, False),
    (360, 360, False),
    (1500, 1500, False),
    (148, 36, True),
):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for address, size in (
        (base, 0x30000),
        (0x200000, 0x10000),
        (0x300000, 0x10000),
        (0x400000, 0x10000),
        (0x500000, 0x10000),
        (0x700000, 0x10000),
    ):
        cpu.mem_map(address, size)
    net_page = net_begin & ~4095
    cpu.mem_map(net_page, 4096)
    cpu.mem_write(net_page, kernel[net_page - kernel_base:net_page - kernel_base + 4096])
    for address in (net_copy, net_unlock):
        cpu.mem_map(address & ~4095, 4096)
    cpu.mem_write(base, bytes(code))
    original_sp, request, response, user, finished = (
        0x208FF0,
        0x400000,
        0x300000,
        0x500000,
        0x700100,
    )
    frame = bytearray((i * 11 + 7) & 255 for i in range(length))
    struct.pack_into("<4H", frame, 0, 0x8086, length, 19, 0)
    cpu.mem_write(response, bytes(frame))
    cpu.mem_write(user, b"\xa5" * 1600)
    cpu.mem_write(request + 16, struct.pack("<IHH", user, input_bytes, 0))
    fp = original_sp - 4
    cpu.mem_write(fp - 84, struct.pack("<I", request))
    # Original thread_info.addr_limit, not a permissive changed instruction.
    cpu.mem_write(0x208008, struct.pack("<I", 0x80000000))
    saved = list(range(0x44, 0x4C)) + [original_sp, finished, 0]
    cpu.mem_write(original_sp - 44, struct.pack("<11I", *saved))
    cpu.reg_write(UC_ARM_REG_SP, original_sp - 96)
    cpu.reg_write(UC_ARM_REG_R11, fp)
    cpu.reg_write(UC_ARM_REG_R7, response)
    copies, releases, net_copies = [], [], []

    def hook(machine, pc, size, unused):
        if pc == finished:
            machine.emu_stop()
        elif pc == stubs["__arch_copy_to_user"]:
            destination, source, count = [
                machine.reg_read(register)
                for register in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)
            ]
            assert (destination, source, count) == (user, response, length)
            copies.append(count)
            if not copy_fault:
                machine.mem_write(destination, bytes(machine.mem_read(source, count)))
            machine.reg_write(UC_ARM_REG_R0, count if copy_fault else 0)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
        elif pc == stubs["kfree"]:
            releases.append(machine.reg_read(UC_ARM_REG_R0))
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
        elif pc == net_unlock:
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
        elif pc == net_copy:
            destination, source, count = [machine.reg_read(register) for register in
                                          (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            assert (destination, source, count) == (user + 0x800, request, 32)
            net_copies.append(count)
            machine.mem_write(destination, bytes(machine.mem_read(source, count)))
            machine.reg_write(UC_ARM_REG_R0, 0)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(base + start, finished + 4, count=1000)
    assert cpu.reg_read(UC_ARM_REG_PC) == finished
    assert (
        cpu.reg_read(UC_ARM_REG_R0) == 0 and cpu.reg_read(UC_ARM_REG_SP) == original_sp
    )
    assert copies == [length] and releases == [response]
    assert struct.unpack("<H", cpu.mem_read(request + 20, 2))[0] == length
    assert bytes(cpu.mem_read(user, length)) == (
        b"\xa5" * length if copy_fault else frame
    )
    assert bytes(cpu.mem_read(user + length, 4)) == b"\xa5" * 4
    # Enter dev_ioctl after wireless_process_ioctl returned the replayed driver result.
    # The adjacent odd command is a control for the networking copyback branch.
    outer = struct.pack("<16sIHH8x", b"eth0", user, input_bytes, 0)
    for command, expected in ((0x8BE4, input_bytes), (0x8BE5, length)):
        cpu.mem_write(user + 0x800, outer)
        for reg, value in ((UC_ARM_REG_R0, 0), (UC_ARM_REG_R4, command), (UC_ARM_REG_R5, 0),
                           (UC_ARM_REG_R6, user + 0x800), (UC_ARM_REG_R10, request)):
            cpu.reg_write(reg, value)
        cpu.emu_start(net_begin, net_end, count=1000)
        assert cpu.reg_read(UC_ARM_REG_PC) == net_end and cpu.reg_read(UC_ARM_REG_R0) == 0
        assert struct.unpack("<H", cpu.mem_read(user + 0x800 + 20, 2))[0] == expected
        assert net_copies == ([32] if command & 1 else [])
    cases.append(
        dict(
            request_bytes=input_bytes,
            response_bytes=length,
            copy_fault=copy_fault,
            ioctl_result=0,
            kernel_iwreq_length=length,
            user_iwreq_length=input_bytes,
            trailing_user_bytes_unchanged=True,
        )
    )

out = ROOT / "work/sd8686-hostcmd-response" / str(time.time_ns())
out.mkdir(parents=True)
report = dict(
    passed=True,
    cases=cases,
    original_response_path=[hex(start), hex(end)],
    module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
    original_network_copyback_path=[hex(net_begin), hex(net_end)],
    kernel_sha256=kernel_sha,
    relocations=relocated,
    user_copy_and_kfree_modeled=True,
    command_queue_wait_and_hardware_not_executed=True,
    device_accessed=False,
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
)
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(passed=True, cases=len(cases), report=str(out / "report.json"))))
