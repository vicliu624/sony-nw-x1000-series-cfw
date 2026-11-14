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
from evidence_checks import source_inventory, verify_source_snapshot, write_source_snapshot
from generate_espnow_full_profile import reviewed_radio
from review_managed_remote_profile import digest, native_sdk_build, private


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
    sdk_input = parser.add_mutually_exclusive_group()
    sdk_input.add_argument("--sdk-review", type=Path, help="Verified native SDK build.json to use for ARM replay")
    sdk_input.add_argument("--mailbox-review", type=Path, help="Verified mailbox review.json to use for a fresh SDK build")
    parser.add_argument("--source-snapshot", type=Path, help="Reuse an exact source ZIP below work/")
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError("Radio regression assertions must remain enabled")
    output = (args.output or ROOT / "work/radio-profile-tests" / str(time.time_ns())).resolve()
    if not output.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Output must remain under work/")
    before = source_inventory(ROOT)
    reused = review_profiles(args.radio_reviews) if args.radio_reviews is not None else {}
    sdk = native_sdk_build(args.sdk_review) if args.sdk_review is not None else None
    snapshot = private(args.source_snapshot) if args.source_snapshot is not None else output / "checked-source.zip"
    snapshot_hash = verify_source_snapshot(before, snapshot) if args.source_snapshot is not None else None
    output.mkdir(parents=True, exist_ok=False)
    if snapshot_hash is None:
        snapshot_hash = write_source_snapshot(ROOT, before, snapshot)
    report = dict(version=(ROOT / "VERSION").read_text().strip(), checks=[], profiles={},
                  device_accessed=False, update_package_created=False,
                  hardware_qualified=False, source_hashes=before,
                  source_snapshot=snapshot.relative_to(ROOT).as_posix(), source_snapshot_sha256=snapshot_hash)
    checked_inputs = {report["source_snapshot"]: snapshot_hash}

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
                                 ROOT / "work/targets-jp/helper_sd.bin",
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
            options = ["--output", native]
            if args.mailbox_review is not None:
                options.extend(("--mailbox-review", args.mailbox_review))
            run("native-library", "runtime/platform/espnow/build_library.py", *options)
            sdk = native_sdk_build(native / "sdk/build.json")
        sdk_path, archive, sdk_report = sdk
        report["native_sdk"] = dict(review=sdk_path.relative_to(ROOT).as_posix(),
                                    archive_sha256=sdk_report["archive_sha256"], reused=args.sdk_review is not None)
        checked_inputs[sdk_path.relative_to(ROOT).as_posix()] = digest(sdk_path)
        checked_inputs[archive.relative_to(ROOT).as_posix()] = sdk_report["archive_sha256"]
        directories = {name: path.relative_to(ROOT).as_posix() for name, path in directories.items()}
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
            "--radio-review", directories["frame"], "--sdk-review", report["native_sdk"]["review"])
        run("secure-native-arm-chain", "tools/test_xnow_secure_chain.py", "--arm",
            "--radio-review", directories["vector"])
    finally:
        report["source_changed_during_run"] = source_inventory(ROOT) != before
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
