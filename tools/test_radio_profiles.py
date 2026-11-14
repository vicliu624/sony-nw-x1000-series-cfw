"""Offline radio profiles and native/MCU replay; never access devices or build an updater."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from app_registry import ROOT
from build_espnow_full_radio import build
from test_firmware_regressions import source_inventory, write_source_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError("Radio regression assertions must remain enabled")
    output = (args.output or ROOT / "work/radio-profile-tests" / str(time.time_ns())).resolve()
    if not output.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Output must remain under work/")
    output.mkdir(parents=True, exist_ok=False)
    before = source_inventory()
    report = dict(version=(ROOT / "VERSION").read_text().strip(), checks=[], profiles={},
                  device_accessed=False, update_package_created=False,
                  hardware_qualified=False, source_hashes=before)
    report["source_snapshot_sha256"] = write_source_snapshot(ROOT, before, output / "checked-source.zip")

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(label, script, *arguments):
        log = output / f"{len(report['checks']) + 1:02d}-{label}.log"
        start = time.monotonic()
        print(label, flush=True)
        with log.open("wb") as stream:
            process = subprocess.run([sys.executable, str(ROOT / script), *map(str, arguments)],
                                     cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        report["checks"].append(dict(label=label, command=[script, *map(str, arguments)],
                                     exit_code=process.returncode,
                                     seconds=round(time.monotonic() - start, 3),
                                     log=log.relative_to(ROOT).as_posix(),
                                     log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        save()
        if process.returncode:
            raise RuntimeError(f"{label} failed; see {log}")

    save()
    try:
        for name, options in (
            ("scalar", {}),
            ("bulk", dict(bulk_commands=True)),
            ("vector", dict(bulk_commands=True, read_vector=True)),
            ("frame", dict(frame_transactions=True)),
        ):
            directory = output / name
            manifest = build(ROOT / "work/targets-jp/sd8686.bin",
                             ROOT / "work/espnow-full-radio-review-3/stock/helper_sd.bin",
                             directory, rx_diagnostics=True, **options)
            report["profiles"][name] = dict(
                directory=directory.relative_to(ROOT).as_posix(),
                candidate_sha256=manifest["candidate_sha256"],
                payload_sha256=manifest["payload_elf_sha256"],
                occupied_span_bytes=manifest["occupied_span_bytes"],
                tail_free_bytes=manifest["tail_free_bytes"],
                pool_blocks=manifest["pool_blocks_after"],
                in_place_command=manifest["in_place_command"])
            save()
        run("native-library", "runtime/platform/espnow/build_library.py")
        run("original-hostcmd-response", "tools/test_sd8686_hostcmd_response.py")
        run("original-packet-ownership", "tools/test_radio_packet_ownership.py")
        run("word-tx", "tools/test_radio_full_tx.py")
        for name in ("scalar", "bulk", "vector"):
            run(name + "-completion", "tools/test_radio_completion_hook.py",
                "--radio-review", output / name)
            run(name + "-release-preemption", "tools/test_radio_completion_preemption.py",
                "--legacy", "--radio-review", output / name)
            run(name + "-native-word-chain", "tools/test_xnow_full_integration.py",
                "--radio-review", output / name)
        run("frame-transactions", "tools/test_radio_frame_transactions.py",
            "--radio-review", output / "frame")
        run("frame-release-preemption", "tools/test_radio_completion_preemption.py",
            "--radio-review", output / "frame")
        run("frame-original-rx", "tools/test_radio_full_rx.py", "--radio-review", output / "frame")
        run("frame-native-arm-chain", "tools/test_sd8686_frame_native.py",
            "--radio-review", output / "frame")
        run("secure-native-arm-chain", "tools/test_xnow_secure_chain.py", "--arm",
            "--radio-review", output / "vector")
    finally:
        report["source_changed_during_run"] = source_inventory() != before
        report["passed"] = (len(report["checks"]) == 18 and
                            all(item["exit_code"] == 0 for item in report["checks"]) and
                            not report["source_changed_during_run"])
        save()
    if not report["passed"]:
        raise RuntimeError("Radio checks incomplete, failed or source changed")
    print("PASS " + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
