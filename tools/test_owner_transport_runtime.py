"""Real owner/pipe scheduling with modeled RF and sideband policy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', action='store_true')
options = parser.parse_args()
out = ROOT / 'work/owner-transport-runtime' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/fixtures/owner_transport_runtime.c', 'tools/fixtures/xnow_control_platform.c']
sources += ['runtime/platform/espnow/' + name + '.c' for name in
    ('xnow_owner_runtime', 'xnow_owner_gate', 'xnow_handoff_owner', 'xnow_owner_stream',
     'xnow_owner_commands', 'xnow_owner_commands_control', 'xnow_full_control', 'xnow_session',
     'xnow_manager', 'xnow_endpoint', 'xnow_peer', 'xnow_wire', 'xnow_full')]
sources += ['runtime/store/stock_fs_bridge.c', 'runtime/store/stock_stat64.c']
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
         '-DXNOW_OWNER_GATE_NAMESPACE="x1000-owner-transport-runtime-test-v1"']
if options.baseline: flags += ['-DXNOW_TRANSPORT_BASELINE']
host = out / 'test.host'
subprocess.run(['gcc-12', *flags, '-fsanitize=address,undefined', *sources, '-o', str(host)], check=True)
result = subprocess.run([str(host)], capture_output=True, text=True, timeout=20)
(out / 'host.log').write_text(result.stdout + result.stderr)
assert not result.returncode, result.stdout + result.stderr
marker = 'BASELINE_PREMATURE_SEND_ACK' if options.baseline else 'OWNER_TRANSPORT_RUNTIME_PASS'
assert marker in result.stdout
libs = stock_libraries()
arm = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC',
    '-D_DEFAULT_SOURCE=', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te',
    '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-stack-protector', '-fno-pie',
    '-no-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none', *sources,
    'runtime/store/start.c', 'runtime/store/start.S', str(libs['libc.so.6']),
    str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)], check=True)
result = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
    '--library-path', str(libs['libc.so.6'].parent), str(arm)],
    capture_output=True, text=True, timeout=20)
(out / 'arm.log').write_text(result.stdout + result.stderr)
assert not result.returncode and marker in result.stdout, result.stdout + result.stderr
report = dict(passed=True, baseline=options.baseline, original_libc_arm926=True,
    real_pipes_and_owner=True, radio_modeled=True, device_accessed=False,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
        [*sources, 'tools/test_owner_transport_runtime.py', 'runtime/platform/espnow/xnow_owner_runtime.h',
         'runtime/platform/espnow/xnow_owner_stream.h', 'tools/fixtures/full_owner_ipc.c', 'tools/test_xnow_full.c']})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, baseline=options.baseline, report=(out / 'report.json').relative_to(ROOT).as_posix())))
