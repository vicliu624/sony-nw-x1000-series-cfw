"""Replay packet reuse at original-free boundaries; task scheduling is modeled."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import time
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)
from app_registry import ROOT

with contextlib.redirect_stdout(io.StringIO()):
    fixture = runpy.run_path(str(ROOT / "tools/test_radio_frame_transactions.py"))
cpu, word, put, call, free_count, fragment, symbols = [fixture[name] for name in (
    "cpu", "word", "put", "call", "free_count", "fragment", "symbols")]
state = symbols["xnow_tx_completion"]
schedule = {"pause": None, "free_return": None}


def hook(machine, pc, size, unused):
    if pc == schedule["pause"] or pc == 0x3A12:
        machine.emu_stop()
    if schedule["free_return"] == "capture" and pc == 0x1360:
        # Queue rejection must cancel tracking before original free exposes the
        # block to another task. Stop at its original return instruction next.
        assert not word(state)
        schedule["pause"] = machine.reg_read(UC_ARM_REG_LR) & ~1
        schedule["free_return"] = None


cpu.hook_add(UC_HOOK_CODE, hook)


def other_task(entry, *arguments):
    cpu.reg_write(UC_ARM_REG_SP, 0x206000)
    cpu.reg_write(UC_ARM_REG_LR, 0x1F001)
    for register, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), arguments):
        cpu.reg_write(register, value)
    cpu.emu_start(entry if entry == 0x1360 else entry | 1, 0x1F002, count=30000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x1F000
    return cpu.reg_read(UC_ARM_REG_R0)


held = [call(0xD458, 1900) for _ in range(2)]
assert all(held) and free_count() == 1
fixture["env"]["queue_result"][0] = 0
body = bytearray(31)
body[3] = 0x20
status, submitted = fragment(len(body), body)
assert not status and not submitted["result"]
packet, token = word(state), word(state + 4)
previous_done = word(state + 8)
schedule["pause"] = symbols["xnow_radio_tx_released"] & ~1
cpu.reg_write(UC_ARM_REG_SP, 0x207000)
cpu.reg_write(UC_ARM_REG_LR, 0x3A13)
cpu.reg_write(UC_ARM_REG_R0, packet)
cpu.mem_write(0x207008, struct.pack("<II", 0, 0x70302))
cpu.emu_start(0xD51D, 0x3A18, count=30000)
assert cpu.reg_read(UC_ARM_REG_PC) == schedule["pause"]
assert free_count() == 1 and word(state) == packet + 1
saved = cpu.context_save()
schedule["pause"] = None
queued_before = len(fixture["env"]["queued"])
status, blocked = fragment(len(body), body)
assert not status and blocked["result"] == -2 and len(fixture["env"]["queued"]) == queued_before
reused = other_task(0xD458, 1900)
assert reused == packet and free_count() == 0
assert other_task(0xD51C, reused) == 0 and free_count() == 1
assert word(state) == packet + 1 and word(state + 8) == previous_done
assert word(state + 12) == 0 and word(state + 16) == 0x70302
cpu.context_restore(saved)
cpu.emu_start((symbols["xnow_radio_tx_released"] & ~1) | 1, 0x3A18, count=30000)
assert cpu.reg_read(UC_ARM_REG_PC) == 0x3A12
assert not word(state) and word(state + 8) == token
status, reply = fixture["command"](3, struct.pack("<7I", token, 0, 0, 0, 0, 0, 0))
assert not status and struct.unpack_from("<II", reply, 28) == (0, 0x70302)

# Rejection is a different original free path, before any MAC ownership.
fixture["env"]["queue_result"][0] = 1
schedule["free_return"] = "capture"
try:
    fragment(len(body), body)
    raise AssertionError("rejection failed to stop at original free return")
except AssertionError:
    assert schedule["pause"] is not None
    assert cpu.reg_read(UC_ARM_REG_PC) == schedule["pause"] and free_count() == 1
saved = cpu.context_save()
resume = schedule["pause"]
schedule["pause"] = None
reused = other_task(0xD458, 1900)
assert reused == packet
assert other_task(0xD51C, reused) == 0 and free_count() == 1
assert not word(state) and word(state + 8) == word(state + 20)
cpu.context_restore(saved)
cpu.emu_start(resume | 1, 0x9B40, count=30000)
assert cpu.reg_read(UC_ARM_REG_PC) == 0x9A70
assert not word(state) and word(state + 8) == word(state + 20)
for neighbor in held:
    assert call(0x1360, neighbor) == 0
assert free_count() == 3
fixture["env"]["queue_result"][0] = 0
status, submitted = fragment(len(body), body)
assert not status and not submitted["result"]
fixture["finish"]()

report = dict(
    passed=True, completion_survives_packet_reuse=True,
    nested_release_cannot_publish_another_claim=True,
    new_send_blocked_until_claim_retired=True,
    rejection_cancels_before_original_free=True, next_send_and_pool_restored=True,
    task_interleaving_manually_scheduled=True, irq_dma_and_rom_queue_modeled=True,
    device_accessed=False, hardware_qualified=False,
    candidate_sha256=fixture["manifest"]["candidate_sha256"],
    payload_sha256=fixture["manifest"]["payload_elf_sha256"],
    source_hashes={**fixture["report"]["source_hashes"],
                   "tools/test_radio_completion_preemption.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
)
output = ROOT / "work/radio-completion-preemption" / str(time.time_ns())
output.mkdir(parents=True)
(output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(output=str(output), **report), indent=2))
