"""Build the explicit-capability remote service; never deploys or starts RF."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from app_registry import ROOT
from evidence_checks import gcc_project_dependencies
from player_arm_guest import stock_libraries
from review_managed_remote_profile import component_build, digest
from sdk_build import fresh_work


SERVICE_LEAF = 'wireless-remote-service.arm'
SERVICE_SOURCES = [
    f'runtime/apps/wireless-remote/{name}.c'
    for name in ('service', 'worker', 'radio_retirement', 'status_sender', 'session_wire',
                 'player_status', 'link', 'status_auth', 'control', 'control_player',
                 'mode_wire', 'library_wire', 'library_player', 'artwork_wire')
] + [
    f'runtime/platform/player/{name}.c'
    for name in ('client', 'managed_remote', 'managed_client', 'managed_codec', 'managed_clock', 'rpc_wire')
] + [
    'runtime/platform/espnow/xnow_client.c', 'runtime/platform/espnow/xnow_handoff.c',
    'runtime/native/sha256.c', 'runtime/store/deadline.c', 'runtime/store/stock_fs_bridge.c',
    'runtime/store/stock_stat64.c', 'runtime/store/start.c', 'runtime/store/start.S',
]


def build(output=None, *, fixture_sources=(), fixture_flags=()):
    out = fresh_work(output or ROOT / 'work/remote-service-build' / str(time.time_ns()))
    libs = stock_libraries(include_rt=True)
    artifact = out / SERVICE_LEAF
    flags = [
        '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
        '-DHB_STORE_SONY_LIBC', '-DHB_STORE_LIBC_CLOCK', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
        '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector',
        '-no-pie', '-fno-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none',
    ]
    sources = [*SERVICE_SOURCES, *fixture_sources]
    compiler = ['arm-linux-gnueabi-gcc', *flags, *fixture_flags]
    inputs = gcc_project_dependencies(ROOT, compiler, sources)
    inputs.update(('tools/build_remote_service.py', 'tools/evidence_checks.py'))
    source_hashes = {p: digest(ROOT / p) for p in sorted(inputs)}
    linked_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in libs.values()}
    subprocess.run([*compiler, *sources, str(libs['librt.so.1']),
                    str(libs['libpthread.so.0']), str(libs['libc.so.6']), str(libs['ld-linux.so.3']),
                    '-lgcc', '-o', str(artifact)], cwd=ROOT, check=True)
    base = ['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']), '--library-path',
            ':'.join(dict.fromkeys(str(p.parent) for p in libs.values())), str(artifact)]
    env = dict(os.environ, QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    for args, expected in ((['--help'], 0), ([], 64), (['--run', '3', '3', '5', '6', '7'], 64)):
        run = subprocess.run(base + args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        if run.returncode != expected:
            raise RuntimeError(run.stdout + run.stderr)

    for name, expected in {**source_hashes, **linked_hashes}.items():
        if digest(ROOT / name) != expected:
            raise ValueError('Remote service input changed during build: ' + name)
    report = dict(built=True, artifact=artifact.relative_to(ROOT).as_posix(), bytes=artifact.stat().st_size,
                  sha256=digest(artifact), original_libc_arm_entry_checks=not (fixture_sources or fixture_flags),
                  device_accessed=False, radio_started=False, live_capability_run_verified=False,
                  command_negotiation_supported=True,
                  linked_library_hashes=linked_hashes, source_hashes=source_hashes)
    if fixture_sources or fixture_flags:
        report['fixture_only'] = True
    (out / 'build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return artifact, report


def reviewed_service(review):
    path, report, artifact = component_build(review, SERVICE_LEAF)
    if report.get('fixture_only') or report.get('original_libc_arm_entry_checks') is not True:
        raise ValueError('Expected an original-libc service build')
    return path, ROOT / artifact['local'], report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New build directory below work/')
    args = parser.parse_args()
    _, report = build(args.output)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
