"""Run offline firmware/SDK regressions and retain independent test receipts.

This command never installs firmware, connects to a player or flashes a remote.
Each check keeps its own log and exit status. The aggregate records a source
inventory so a report cannot be reused after editing the checked tree.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from app_registry import ROOT
from evidence_checks import source_inventory, write_source_snapshot


SUITES = {
    # No Sony inputs, ARM toolchain, network bootstrap or firmware composition.
    # These are a subset of remote/workers, so exclude host from the default run.
    "host": [
        ["test_xnow_span_guard.py", "--host-only"],
        ["test_xnow_span_guard.py", "--bulk", "--host-only"],
        ["test_xnow_span_guard.py", "--bulk", "--frames", "--host-only"],
        ["test_xnow_span_guard.py", "--bulk", "--frames", "--vector", "--host-only"],
        ["test_player_hello_compat.py"],
        ["test_xnow_link.py", "--host-only"],
        ["test_core2_link.py"],
        ["test_core2_tx_frame.py"],
        ["test_remote_receive_prepare.py", "--host-only"],
        ["test_player_metadata_async.py"],
        ["test_player_metadata_async.py", "--artwork"],
        ["test_player_metadata_async.py", "--ownership"],
        ["test_player_metadata_async.py", "--ownership", "--cleanup-failure"],
        ["test_player_metadata_async.py", "--ownership", "--read-success-cleanup"],
        ["test_player_metadata_async.py", "--ownership", "--queued-close-failure"],
        ["test_player_metadata_async.py", "--ownership", "--start-failure-cleanup"],
        ["test_player_broker.py", "--host-only"],
        ["test_owner_wait.py", "--host-only"],
    ],
    "lifecycle": [
        ["test_shared_owner_retirement.py"],
        ["test_remote_retirement_summary.py"],
        ["test_xnow_full_control.py"],
        ["test_xnow_link.py"],
        ["test_xnow_link_counter.py"],
        ["test_xnow_owner_link.py"],
        ["test_wireless_mode_channel.py"],
        ["test_wireless_mode_policy.py"],
        ["test_stock_wireless_lifecycle.py"],
        ["test_native_environment.py"],
        ["test_owner_startup_recheck.py"],
        ["test_remote_receive_prepare.py"],
        ["test_remote_pairing_rx_filter.py"],
        ["test_owner_running_observation.py"],
        ["test_owner_retirement.py"],
        ["test_player_handoff_bridge.py"],
        ["test_native_snapshot_dispatch.py", "--input", "work/targets-jp/SpiderApp"],
        ["test_native_stop.py"],
        ["test_sleep_retirement.py"],
        ["test_sleep_native.py"],
        ["test_wireless_auto_exit.py"],
        ["test_wireless_mode_refresh.py"],
        ["test_owner_wait.py"],
        ["test_owner_wait_anchor.py"],
        ["test_owner_wait_loader.py"],
        ["test_stock_owner_idle.py", "--lease"],
    ],
    "sdk": [
        ["test_sdk.py"],
        ["test_sdk_storage_stop.py"],
        ["test_sdk_services.py"],
        ["test_sdk_text.py"],
        ["test_sdk_player_service.py"],
        ["test_sdk_managed_channel.py"],
        ["test_sdk_managed_channel.py", "--managed-example"],
        ["test_sdk_espnow.py"],
        ["test_sdk_espnow_full.py"],
        ["test_sdk_espnow_owner.py"],
        ["audit_sdk_adoption.py"],
        ["tests/test_system_consumer_catalog.py"],
        ["tests/test_sdk_source_relocations.py"],
        ["tests/test_sdk_shared_dependencies.py"],
    ],
    "remote": [
        ["test_xnow_span_guard.py"],
        ["test_xnow_span_guard.py", "--bulk"],
        ["test_xnow_span_guard.py", "--bulk", "--frames"],
        ["test_xnow_span_guard.py", "--bulk", "--frames", "--vector"],
        ["test_player_hello_compat.py"],
        ["test_stock_mode_control.py"],
        ["test_stock_provider.py"],
        ["test_stock_info.py", "--engine-control"],
        ["test_stock_gui_host.py"],
        ["test_stock_gui_host.py", "--engine-provider"],
        ["test_stock_engine_control.py"],
        ["test_stock_engine_control.py", "--provider"],
        ["test_stock_volume_host.py"],
        ["test_stock_host_refusal.py"],
        ["test_player_metadata_async.py"],
        ["test_player_metadata_async.py", "--artwork"],
        ["test_status_sender.py"],
        ["test_status_sender.py", "--fairness"],
        ["test_artwork_timing.py"],
        ["test_remote_worker.py"],
        ["test_service_stop_observation.py"],
        ["test_remote_link.py"],
        ["test_stock_media.py"],
        ["test_xnow_pn.py"],
        ["test_native_choice_view.py"],
        ["tests/test_sony_settings_boundary.py"],
        ["test_run_profile.py"],
    ],
    "integration": [
        ["test_radio_profiles.py"],
        ["test_xnow_client.py"],
        ["test_xnow_owner_stream.py"],
        ["test_owner_transport_runtime.py"],
        ["test_core2_owner_bus.py"],
        ["test_full_owner_runtime.py", "--stop-boundaries"],
        ["test_full_owner_runtime.py", "--power-off", "--mode-admission", "--pairing-policy", "--stop-boundaries"],
        ["test_service_lifecycle.py"],
        ["test_remote_service.py", "--play-mode-control"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--device-pairing", "--play-mode-control"],
        ["test_remote_observation_chain.py"],
        ["test_player_service_drain.py", "--host-wrapper", "--wait-backpressure"],
        ["test_player_service_drain.py", "--host-wrapper", "--handoff-revocation"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-after-sdk-drain"],
        ["test_player_service_drain.py", "--host-wrapper", "--native-exit-forward"],
        ["test_player_service_drain.py", "--host-wrapper", "--native-exit-forward-fault"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-fault"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-dependency", "--revoke-context", "drain"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-dependency", "--revoke-context", "retirement"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-dependency", "--revoke-context", "drain", "--native-retry-after-revoke"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-dependency", "--revoke-context", "radio-wait", "--native-retry-after-revoke"],
        ["test_player_service_drain.py", "--host-wrapper", "--exit-dependency", "--revoke-context", "radio-ready", "--native-retry-after-revoke"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--artwork-transfer"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--sleep-retirement"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--sleep-retirement"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--device-pairing", "--delayed-pairing-ready"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--exit-idle-progress"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--native-exit-bridge"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--native-owner-wait"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--application-handoff"],
        ["test_remote_supervisor.py", "--automatic-factory", "--owner-view-forward", "--shared-wifi", "--exit-idle-progress", "--revoked-exit-context"],
    ],
    "workers": [
        ["test_player_metadata_async.py", "--ownership"],
        ["test_player_metadata_async.py", "--ownership", "--cleanup-failure"],
        ["test_player_metadata_async.py", "--ownership", "--read-success-cleanup"],
        ["test_player_metadata_async.py", "--ownership", "--queued-close-failure"],
        ["test_player_metadata_async.py", "--ownership", "--start-failure-cleanup"],
        ["test_audio_check_async.py"],
        ["test_source_intent_async.py", "--managed"],
        ["test_player_worker_system.py"],
        ["test_media_reader_ownership_system.py"],
        ["test_player_broker.py"],
    ],
    "layout": [["check_repository_layout.py"]],
    "artifact": [
        ["test_player_host_anchor.py", "--engine-provider"],
        ["test_shared_wifi_auto_off.py"],
        ["test_remote_binding_menu.py"],
    ],
}
SUITES["unit"] = [[path.relative_to(ROOT).as_posix()]
                  for path in sorted((ROOT / "tests").glob("test_*.py"))]


def plan_checks(suites, host_review=None):
    """Deduplicate only identical commands in this run; never reuse old passes."""
    planned, duplicates, seen = [], [], {}
    for suite in suites:
        for selected in SUITES[suite]:
            command = list(selected)
            if suite == "artifact":
                command += ["--host-review", str(host_review.resolve())]
            key = tuple(command)
            if key in seen:
                duplicates.append({"suite": suite, "command": command, "kept_in": seen[key]})
                continue
            seen[key] = suite
            planned.append((suite, command))
    return planned, duplicates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=SUITES, action="append")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", action="store_true", help="Print selected checks without executing or creating output")
    parser.add_argument("--host-review", type=Path,
                        help="Explicit immutable analysis-library receipt for the artifact suite")
    args = parser.parse_args()
    suites = args.suite or [name for name in SUITES if name not in ("artifact", "host")]
    if "artifact" in suites and args.host_review is None:
        parser.error("--suite artifact requires --host-review; no existing artifact is selected implicitly")
    if args.host_review is not None and "artifact" not in suites:
        parser.error("--host-review requires --suite artifact")
    planned, duplicates = plan_checks(suites, args.host_review)
    if args.plan:
        print(json.dumps({"suites": suites, "checks": [dict(suite=s, command=c) for s, c in planned],
                          "duplicate_checks_omitted": duplicates}, indent=2))
        return 0
    if sys.flags.optimize:
        raise RuntimeError("Regression assertions must remain enabled")
    output = args.output or ROOT / "work/firmware-regressions" / str(time.time_ns())
    output = output.resolve()
    if not output.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Regression output must stay under work/")
    output.mkdir(parents=True, exist_ok=False)
    began = time.monotonic()
    before = source_inventory(ROOT)
    snapshot = output / "checked-source.zip"
    snapshot_hash = write_source_snapshot(ROOT, before, snapshot)
    report = {
        "version": (ROOT / "VERSION").read_text().strip(),
        "sdk_version": (ROOT / "sdk/VERSION").read_text().strip(),
        "device_accessed": False,
        "hardware_qualified": False,
        "firmware_created": False,
        "checks": [],
        "requested_suites": suites,
        "duplicate_checks_omitted": duplicates,
        "source_hashes": before,
        "source_snapshot": snapshot.relative_to(ROOT).as_posix(),
        "source_snapshot_sha256": snapshot_hash,
    }
    for suite, command in planned:
        index = len(report["checks"]) + 1
        label = " ".join(command)
        log = output / f"{index:02d}-{Path(command[0]).stem}.log"
        print(f"[{suite}] {label}", flush=True)
        started = time.monotonic()
        script = ROOT / command[0] if len(Path(command[0]).parts) > 1 else ROOT / "tools" / command[0]
        if not script.resolve().is_relative_to(ROOT):
            raise ValueError("Regression script must stay in the checkout")
        invocation = [sys.executable, str(script), *command[1:]]
        if command[0].startswith("tests/"):
            invocation = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", script.name, *command[1:]]
        radio_review = None
        if command[0] == "test_radio_profiles.py":
            radio_output = output / "radio-profiles"
            invocation += ["--output", str(radio_output), "--source-snapshot", str(snapshot)]
            radio_review = radio_output / "report.json"
        with log.open("wb") as stream:
            run = subprocess.run(invocation, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        check = {
            "suite": suite, "command": command, "invocation": invocation, "exit_code": run.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "log": log.relative_to(ROOT).as_posix(),
            "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        }
        if radio_review is not None and run.returncode == 0:
            check["radio_review"] = radio_review.relative_to(ROOT).as_posix()
            check["radio_review_sha256"] = hashlib.sha256(radio_review.read_bytes()).hexdigest()
        report["checks"].append(check)
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"{'PASS' if run.returncode == 0 else 'FAIL'} {label}", flush=True)
    report["source_changed_during_run"] = source_inventory(ROOT) != before
    report["total_seconds"] = round(time.monotonic() - began, 3)
    report["passed"] = not report["source_changed_during_run"] and all(
        check["exit_code"] == 0 for check in report["checks"]
    )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {output / 'report.json'}", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
