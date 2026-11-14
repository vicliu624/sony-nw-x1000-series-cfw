"""Replay packet reuse at original-free boundaries; task scheduling is modeled."""
import hashlib
import json
import struct
import sys
import time
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)
from app_registry import ROOT
from build_espnow_full_radio import build
from radio_test_profile import frame_fixture, legacy_completion_fixture, selected_radio

legacy = "--legacy" in sys.argv
output = ROOT / "work/radio-completion-preemption" / str(time.time_ns())
selected = selected_radio()
if legacy:
    fixture = legacy_completion_fixture(output / "legacy-build", selected)
    provenance = fixture["provenance"]["source_hashes"]
else:
    if selected:
        payload, manifest = selected
    else:
        directory = output / "radio-build"
        manifest = build(ROOT / "work/targets-jp/sd8686.bin",
                         ROOT / "work/targets-jp/helper_sd.bin",
                         directory, rx_diagnostics=True, frame_transactions=True)
        payload = directory / "radio.elf"
    fixture = frame_fixture(payload, manifest)
    provenance = manifest["source_hashes"]
original = fixture["env"]
cpu, word, put, call, free_count = (original[name] for name in ("cpu", "word", "put", "call", "free_count"))
symbols = fixture["symbols"]
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


preemption_hook = cpu.hook_add(UC_HOOK_CODE, hook)


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
original["queue_result"][0] = 0
body = bytearray(31)
body[3] = 0x20
if legacy:
    fixture["submit"]()
else:
    status, submitted = fixture["fragment"](len(body), body)
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
queued_before = len(original["queued"])
if legacy:
    assert fixture["operation"](1) == -2
else:
    status, blocked = fixture["fragment"](len(body), body)
    assert not status and blocked["result"] == -2
assert len(original["queued"]) == queued_before
reused = other_task(0xD458, 1900)
assert reused == packet and free_count() == 0
assert other_task(0xD51C, reused) == 0 and free_count() == 1
assert word(state) == packet + 1 and word(state + 8) == previous_done
assert word(state + 12) == 0 and word(state + 16) == 0x70302
cpu.context_restore(saved)
cpu.emu_start((symbols["xnow_radio_tx_released"] & ~1) | 1, 0x3A18, count=30000)
assert cpu.reg_read(UC_ARM_REG_PC) == 0x3A12
assert not word(state) and word(state + 8) == token
if legacy:
    fixture["command"](state + 20, token)
    assert word(state + 12) == 0 and word(state + 16) == 0x70302
else:
    status, reply = fixture["command"](3, struct.pack("<7I", token, 0, 0, 0, 0, 0, 0))
    assert not status and struct.unpack_from("<II", reply, 28) == (0, 0x70302)

# Rejection is a different original free path, before any MAC ownership.
if legacy:
    assert fixture["operation"](1) == 0
    packet = word(fixture["state"] + 24)
    cpu.mem_write(packet + 32, b"\x7f\x18\xfe\x34" + bytes(11))
    fixture["command"](fixture["state"] + 20, 15)
original["queue_result"][0] = 1
schedule["free_return"] = "capture"
try:
    if legacy:
        fixture["operation"](2)
    else:
        fixture["fragment"](len(body), body)
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
assert cpu.reg_read(UC_ARM_REG_PC) == (0x9A46 if legacy else 0x9A70)
assert not word(state) and word(state + 8) == word(state + 20)
for neighbor in held:
    assert call(0x1360, neighbor) == 0
assert free_count() == 3
cpu.hook_del(preemption_hook)
original["queue_result"][0] = 0
if legacy:
    packet, token = fixture["submit"]()
    fixture["finish"](packet, 0, 0x70302)
    fixture["command"](state + 20, token)
else:
    status, submitted = fixture["fragment"](len(body), body)
    assert not status and not submitted["result"]
    fixture["finish"]()

report = dict(
    passed=True, completion_survives_packet_reuse=True,
    nested_release_cannot_publish_another_claim=True,
    new_send_blocked_until_claim_retired=True,
    rejection_cancels_before_original_free=True, next_send_and_pool_restored=True,
    task_interleaving_manually_scheduled=True, irq_dma_and_rom_queue_modeled=True,
    device_accessed=False, hardware_qualified=False,
    legacy_word_profile=legacy,
    source_hashes={**provenance, **{name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                   for name in ("tools/radio_test_profile.py", "tools/marvell_firmware.py",
                                                "tools/test_radio_completion_preemption.py")}},
)
if legacy:
    report["radio_identity"] = fixture["provenance"].get("exact_selected_radio")
else:
    report["candidate_sha256"] = manifest["candidate_sha256"]
    report["payload_sha256"] = manifest["payload_elf_sha256"]
output.mkdir(parents=True, exist_ok=True)
(output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(output=str(output), **report), indent=2))
