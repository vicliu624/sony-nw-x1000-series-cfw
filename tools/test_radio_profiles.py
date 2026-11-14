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
from radio_test_profile import reviewed_radio
from review_managed_remote_profile import digest, native_sdk_build, private
from test_firmware_regressions import source_inventory, write_source_snapshot


PROFILES = {
    "scalar": {},
    "bulk": {"bulk_commands": True},
    "vector": {"bulk_commands": True, "read_vector": True},
    "frame": {"frame_transactions": True},
}


def review_profiles(folder):
    profiles = {}
    for name, options in PROFILES.items():
        payload, manifest = reviewed_radio(folder / name)
        bulk = manifest.get("bulk_word_commands") or {}
        shape = (bool(bulk), bool(bulk.get("read_vector")), bool(manifest.get("frame_transactions")))
        expected = tuple(options.get(key, False) for key in ("bulk_commands", "read_vector", "frame_transactions"))
        if shape != expected or not manifest.get("rx_diagnostics") or not {"xnow_rx_seen", "xnow_rx_eligible"} <= manifest["controls"].keys():
            raise ValueError("Unexpected radio profile: " + name)
        profiles[name] = (payload.parent, manifest)
    return profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--radio-reviews", type=Path, help="Directory containing verified scalar, bulk, vector and frame builds")
    parser.add_argument("--sdk-review", type=Path, help="Verified native SDK build.json to use for ARM replay")
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError("Radio regression assertions must remain enabled")
    output = (args.output or ROOT / "work/radio-profile-tests" / str(time.time_ns())).resolve()
    if not output.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Output must remain under work/")
    before = source_inventory()
    reused = review_profiles(args.radio_reviews) if args.radio_reviews is not None else {}
    sdk = native_sdk_build(args.sdk_review) if args.sdk_review is not None else None
    output.mkdir(parents=True, exist_ok=False)
    report = dict(version=(ROOT / "VERSION").read_text().strip(), checks=[], profiles={},
                  device_accessed=False, update_package_created=False,
                  hardware_qualified=False, source_hashes=before)
    report["source_snapshot_sha256"] = write_source_snapshot(ROOT, before, output / "checked-source.zip")
    checked_inputs = {}

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
        directories = {}
        for name, options in PROFILES.items():
            if reused:
                directory, manifest = reused[name]
            else:
                directory = output / name
                manifest = build(ROOT / "work/targets-jp/sd8686.bin",
                                 ROOT / "work/espnow-full-radio-review-3/stock/helper_sd.bin",
                                 directory, rx_diagnostics=True, **options)
            directories[name] = directory
            for leaf in ("manifest.json", "radio.elf", "stock/sd8686.bin", "candidate/sd8686.bin", "candidate/helper_sd.bin"):
                path = private(directory / leaf)
                checked_inputs[path.relative_to(ROOT).as_posix()] = digest(path)
            report["profiles"][name] = dict(
                directory=directory.relative_to(ROOT).as_posix(),
                reused=bool(reused),
                candidate_sha256=manifest["candidate_sha256"],
                payload_sha256=manifest["payload_elf_sha256"],
                occupied_span_bytes=manifest["occupied_span_bytes"],
                tail_free_bytes=manifest["tail_free_bytes"],
                pool_blocks=manifest["pool_blocks_after"],
                in_place_command=manifest["in_place_command"])
            save()
        if sdk is None:
            native = output / "native-sdk"
            run("native-library", "runtime/platform/espnow/build_library.py", "--output", native)
            sdk = native_sdk_build(native / "sdk/build.json")
        sdk_path, archive, sdk_report = sdk
        report["native_sdk"] = dict(review=sdk_path.relative_to(ROOT).as_posix(),
                                    archive_sha256=sdk_report["archive_sha256"], reused=args.sdk_review is not None)
        checked_inputs[sdk_path.relative_to(ROOT).as_posix()] = digest(sdk_path)
        checked_inputs[archive.relative_to(ROOT).as_posix()] = sdk_report["archive_sha256"]
        run("original-hostcmd-response", "tools/test_sd8686_hostcmd_response.py")
        run("original-packet-ownership", "tools/test_radio_packet_ownership.py")
        run("word-tx", "tools/test_radio_full_tx.py")
        for name in ("scalar", "bulk", "vector"):
            run(name + "-completion", "tools/test_radio_completion_hook.py",
                "--radio-review", directories[name])
            run(name + "-release-preemption", "tools/test_radio_completion_preemption.py",
                "--legacy", "--radio-review", directories[name])
            run(name + "-native-word-chain", "tools/test_xnow_full_integration.py",
                "--radio-review", directories[name])
        run("frame-transactions", "tools/test_radio_frame_transactions.py",
            "--radio-review", directories["frame"])
        run("frame-release-preemption", "tools/test_radio_completion_preemption.py",
            "--radio-review", directories["frame"])
        run("frame-original-rx", "tools/test_radio_full_rx.py", "--radio-review", directories["frame"])
        run("frame-native-arm-chain", "tools/test_sd8686_frame_native.py",
            "--radio-review", directories["frame"], "--sdk-review", sdk_path)
        run("secure-native-arm-chain", "tools/test_xnow_secure_chain.py", "--arm",
            "--radio-review", directories["vector"])
    finally:
        report["source_changed_during_run"] = source_inventory() != before
        report["input_hashes"] = checked_inputs
        report["inputs_changed_during_run"] = any(not (ROOT / name).is_file() or digest(ROOT / name) != sha
                                                  for name, sha in checked_inputs.items())
        expected_checks = 17 if args.sdk_review is not None else 18
        report["passed"] = (len(report["checks"]) == expected_checks and
                            all(item["exit_code"] == 0 for item in report["checks"]) and
                            not report["source_changed_during_run"] and not report["inputs_changed_during_run"])
        save()
    if not report["passed"]:
        raise RuntimeError("Radio checks incomplete, failed or source changed")
    print("PASS " + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
