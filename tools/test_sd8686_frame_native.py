"""Native C adapter + exact MCU instructions over a private PC-only test socket."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_SP,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
)
from app_registry import ROOT
from build_espnow_full_radio import build
from generate_espnow_full_profile import render
from marvell_firmware import parse

out = ROOT / "work/sd8686-frame-native" / str(time.time_ns())
out.mkdir(parents=True)
if "--radio-review" in sys.argv:
    directory = Path(sys.argv[sys.argv.index("--radio-review") + 1]).resolve()
else:
    directory = out / "radio-build"
    build(
        ROOT / "work/targets-jp/sd8686.bin",
        ROOT / "work/espnow-full-radio-review-3/stock/helper_sd.bin",
        directory,
        rx_diagnostics=True,
        frame_transactions=True,
    )
    sys.argv += ["--radio-review", str(directory)]
with contextlib.redirect_stdout(io.StringIO()):
    radio = runpy.run_path(str(ROOT / "tools/test_radio_frame_transactions.py"))
cpu, put, word, call, free_count = [
    radio[name] for name in ("cpu", "put", "word", "call", "free_count")
]
symbols, sections, manifest = [
    radio[name] for name in ("symbols", "sections", "manifest")
]
records = parse((directory / "candidate/sd8686.bin").read_bytes())
completion, tx, rx = [
    symbols[name] for name in ("xnow_tx_completion", "xnow_full_tx", "xnow_full_rx")
]
original_env = radio["env"]
copy_hook = radio["copies"]
deferred = None
pending_release = None
pause_release = False
frees = [0]


def trace(machine, pc, size, unused):
    if pc == 0x3A12 or (pause_release and pc == (symbols["xnow_radio_tx_released"] & ~1)):
        machine.emu_stop()
    elif pc == 0x1360:
        frees[0] += 1


cpu.hook_add(UC_HOOK_CODE, trace)


def reset():
    global deferred, pending_release
    deferred = None
    pending_release = None
    cpu.mem_write(0xC0000000, bytes(0x20000))
    for record in records:
        if record.command == 1:
            cpu.mem_write(record.address, record.data)
    cpu.ctl_remove_cache(0, 0x20000)
    cpu.ctl_remove_cache(0xC0000000, 0xC0020000)
    call(0xC0004B6C)
    put(0x04001BC8, 0x200400)
    put(0x04001BC4, 0x200420)
    cpu.mem_write(0x200400, bytes(32))
    cpu.mem_write(0x200420, bytes.fromhex("021122334455"))
    put(0x040015E0 + 3 * 4, 0x12340003)
    original_env["queue_result"][0] = 0
    original_env["queued"].clear()
    original_env["notified"].clear()
    frees[0] = 0
    assert free_count() == 3 and word(tx) == 0x3254584E and word(rx) == 0x3252584E


def command(payload):
    assert 16 <= len(payload) <= 1500 and struct.unpack_from("<H", payload, 2)[
        0
    ] == len(payload)
    request, response = 0xC00155B8, 0xC0014E4C
    cpu.mem_write(request, payload)
    cpu.mem_write(response, b"\xa5" * 1600)
    cpu.mem_write(0xC0007859, b"\x01")
    cpu.mem_write(0xC000EDF4, b"\0")
    cpu.mem_write(0xC001452A, b"\x01")
    cpu.reg_write(UC_ARM_REG_SP, 0x208000)
    cpu.emu_start(0x8079, 0x9B40, count=50000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x9A70
    length = struct.unpack("<H", cpu.mem_read(response + 2, 2))[0]
    assert 16 <= length <= 1500 and copy_hook[-1] == (response, request, length)
    assert bytes(cpu.mem_read(response + length, 4)) == b"\xa5" * 4
    return bytes(cpu.mem_read(response, length))


def complete(status, raw, pause=False):
    global pending_release, pause_release
    packet = word(completion)
    if not packet:
        return
    original_sp = 0x207000 if pause else 0x208000
    cpu.mem_write(original_sp + 8, struct.pack("<II", status, raw))
    cpu.reg_write(UC_ARM_REG_SP, original_sp)
    cpu.reg_write(UC_ARM_REG_LR, 0x3A13)
    cpu.reg_write(UC_ARM_REG_R0, packet)
    pause_release = pause
    cpu.emu_start(0xD51D, 0x3A18, count=30000)
    pause_release = False
    if pause:
        assert word(completion) == packet + 1 and cpu.reg_read(UC_ARM_REG_PC) == (symbols["xnow_radio_tx_released"] & ~1)
        pending_release = cpu.context_save()
        return
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x3A12
    assert cpu.reg_read(UC_ARM_REG_SP) == original_sp and not word(completion)


def inject(flags, payload):
    source, body = payload[:6], payload[6:]
    assert len(source) == 6 and 15 <= len(body) <= 1536 and flags in (0, 1, 2)
    # The stock singleton work origin is explicitly supplied. Ring/DMA and IRQ
    # concurrency remain models; the maintained RX hook/allocator execute.
    put(0xC000D5F0, 0x000106A4)
    put(0xC000CDB8, 0xC000CE08)
    put(0xC000CDC8, 0xC0014710)
    frame = bytearray(32 + len(body))
    struct.pack_into("<H", frame, 0, len(body) + 48)
    frame[2] = 0xD0
    frame[3] = 0x40 if flags & 1 else 0
    frame[6:12] = b"\xff" * 6 if flags & 2 else bytes.fromhex("021122334455")
    frame[12:18] = source
    frame[18:24] = b"\xff" * 6
    frame[32:] = body
    cpu.mem_write(0xC000CE08, bytes(frame))
    before = word(rx + 4)
    assert call(symbols["xnow_radio_full_receive"], 0xC000CE08, 0xC000CDD4) == 0
    assert word(rx + 4) == (before + 1) & 0xFFFFFFFF


def receive_exact(connection, count):
    result = bytearray()
    while len(result) < count:
        part = connection.recv(count - len(result))
        if not part:
            if not result:
                return None
            raise RuntimeError("partial native test request")
        result.extend(part)
    return bytes(result)


def serve(connection, errors):
    global deferred, pending_release
    try:
        while True:
            header = receive_exact(connection, 12)
            if header is None:
                return
            operation, count, argument = struct.unpack("<III", header)
            payload = receive_exact(connection, count) if count else b""
            output = b""
            if operation == 1:
                reset()
            elif operation == 2:
                output = command(payload)
                if deferred is not None:
                    late, deferred = deferred, None
                    command(late)  # A late data command must lose to its ticket fence.
            elif operation == 3:
                inject(argument, payload)
            elif operation == 4:
                complete(argument, struct.unpack("<I", payload)[0])
            elif operation == 5:
                output = struct.pack(
                    "<6I",
                    free_count(),
                    len(original_env["notified"]),
                    frees[0],
                    word(rx + 4),
                    word(rx + 8),
                    word(completion),
                )
            elif operation == 6:
                original_env["queue_result"][0] = argument
            elif operation == 7:
                assert deferred is None
                deferred = payload
            elif operation == 8:
                packet = word(completion)
                assert packet and call(0xD51C, packet) == 0 and not word(completion)
            elif operation == 9:
                complete(0, 0x70302, pause=True)
            elif operation == 10:
                assert pending_release is not None
                cpu.context_restore(pending_release)
                pending_release = None
                cpu.emu_start(symbols["xnow_radio_tx_released"] | 1, 0x3A18, count=30000)
                assert cpu.reg_read(UC_ARM_REG_PC) == 0x3A12 and not word(completion)
            else:
                raise RuntimeError("unexpected test control")
            connection.sendall(struct.pack("<II", 0, len(output)) + output)
    except BaseException as error:
        errors.append(traceback.format_exc())
    finally:
        connection.close()


(out / "full_profile.h").write_text(render(directory))
sources = ["tools/fixtures/sd8686_frame_native.c"] + [
    "runtime/platform/espnow/" + name + ".c"
    for name in (
        "xnow_full",
        "xnow_full_guard",
        "xnow_wire",
        "xnow_sd8686_full",
        "xnow_sd8686_frames",
    )
]
sources += ["runtime/native/sha256.c"]
flags = [
    "-std=c99",
    "-D_DEFAULT_SOURCE",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-Wno-misleading-indentation",
    "-I" + str(out),
    "-I" + str(ROOT / "runtime/platform/espnow"),
]


def exercise(arguments, label):
    server, client = socket.socketpair()
    errors = []
    worker = threading.Thread(target=serve, args=(server, errors), daemon=True)
    worker.start()
    process = subprocess.Popen(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        pass_fds=[client.fileno()],
        env=dict(os.environ, XNOW_TEST_BRIDGE_FD=str(client.fileno())),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    client.close()
    try:
        stdout, stderr = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        process.kill()  # Dedicated PC test child; never a device/owner process.
        stdout, stderr = process.communicate()
        raise RuntimeError("Native test timed out: " + stdout + stderr)
    finally:
        worker.join(10)
    (out / (label + ".log")).write_text(stdout + stderr)
    assert not worker.is_alive() and not errors, errors
    assert process.returncode == 0 and "SD8686_FRAME_NATIVE_PASS" in stdout, (
        stdout + stderr
    )
    return stdout


binary = out / "native.host"
subprocess.run(
    [
        "gcc-12",
        *flags,
        "-O1",
        "-fsanitize=address,undefined",
        *sources,
        "-o",
        str(binary),
    ],
    cwd=ROOT,
    check=True,
)
stdout = exercise([binary], "host")
arm_stdout = None
if "--host-only" not in sys.argv:
    from player_arm_guest import stock_libraries

    libraries = stock_libraries()
    target = out / "native.arm"
    native_version = (ROOT / "runtime/platform/espnow/VERSION").read_text().strip()
    native_sdk = ROOT / "work/espnow-native-library" / native_version / "sdk"
    archive = native_sdk / "lib/libxnow.a"
    native_receipt = json.loads((native_sdk / "build.json").read_text())
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == native_receipt["archive_sha256"]
    for name, expected in native_receipt["source_hashes"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    arm_flags = [
        "-Os",
        "-DHB_STORE_SONY_LIBC",
        "-U_FORTIFY_SOURCE",
        "-D_FORTIFY_SOURCE=0",
        "-march=armv5te",
        "-marm",
        "-mfloat-abi=soft",
        "-fno-builtin",
        "-fno-pie",
        "-fno-stack-protector",
        "-nostdlib",
        "-no-pie",
        "-Wl,--hash-style=sysv,--build-id=none",
        "-Wl,--dynamic-linker=/lib/ld-linux.so.3",
    ]
    subprocess.run(
        [
            "arm-linux-gnueabi-gcc",
            *flags,
            *arm_flags,
            sources[0],
            "runtime/store/start.c",
            "runtime/store/start.S",
            str(archive),
            str(libraries["libc.so.6"]),
            str(libraries["ld-linux.so.3"]),
            "-lgcc",
            "-o",
            str(target),
        ],
        cwd=ROOT,
        check=True,
    )
    arm_stdout = exercise(
        [
            "qemu-arm",
            "-cpu",
            "arm926",
            libraries["ld-linux.so.3"],
            "--library-path",
            libraries["libc.so.6"].parent,
            target,
        ],
        "arm",
    )
inputs = [
    *sources,
    "runtime/platform/espnow/xnow_full.h",
    "runtime/platform/espnow/xnow_sd8686_full.h",
    "runtime/platform/espnow/sd8686_private.h",
    "runtime/platform/espnow/xnow_frame_protocol.h",
    "tools/test_sd8686_frame_native.py",
    "tools/test_radio_frame_transactions.py",
    "tools/test_radio_packet_ownership.py",
    "tools/radio_test_profile.py",
    *manifest["source_hashes"],
]
if arm_stdout is not None:
    inputs += ["runtime/store/start.c", "runtime/store/start.S"]
report = dict(
    passed=True,
    native_host_sanitizers=True,
    original_mcu_dispatch_and_packet_code=True,
    lost_submit_during_claimed_release_reconciled=True,
    candidate_sha256=manifest["candidate_sha256"],
    modeled=[
        "ioctl envelope",
        "IRQ",
        "ROM queues",
        "work origin",
        "ciphertext contents",
    ],
    hardware_tested=False,
    device_accessed=False,
    stdout=stdout,
    original_libc_arm926=arm_stdout,
    source_hashes={
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(inputs))
    },
)
report["native_host_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
report["radio_elf_sha256"] = manifest["payload_elf_sha256"]
report["host_compiler"] = subprocess.check_output(
    ["gcc-12", "--version"], text=True
).splitlines()[0]
if arm_stdout is not None:
    report["native_arm_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    report["native_archive_sha256"] = native_receipt["archive_sha256"]
    report["arm_compiler"] = subprocess.check_output(
        ["arm-linux-gnueabi-gcc", "--version"], text=True
    ).splitlines()[0]
    report["original_libraries"] = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in libraries.items()
    }
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(passed=True, report=str(out / "report.json"), stdout=stdout)))
