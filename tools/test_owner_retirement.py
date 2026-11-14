"""Actual shared-sleep restore caller after data revocation, without hardware."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time

from player_arm_guest import stock_libraries

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/owner-retirement' / str(time.time_ns())
OUT.mkdir(parents=True)
owner_path = ROOT / 'runtime/apps/wireless-remote/rf_owner.c'
owner = owner_path.read_text(encoding='utf-8')


def function(name):
    begin = owner.index('static int ' + name + '(')
    brace = owner.index('{', begin)
    depth, end = 1, brace + 1
    while depth:
        depth += (owner[end] == '{') - (owner[end] == '}')
        end += 1
    return owner[begin:end]


fixture_path = ROOT / 'tools/fixtures/owner_retirement.c'
fixture = fixture_path.read_text(encoding='utf-8').replace(
    '/* ACTUAL_OWNER_FUNCTIONS */', '\n\n'.join(function(name) for name in
                                               ('owner_mode_await', 'restore_shared_sleep')))
generated = OUT / 'actual-owner-retirement.c'
generated.write_text(fixture, encoding='utf-8')
sources = [str(generated.relative_to(ROOT)),
           'runtime/apps/wireless-remote/owner_admission.c',
           'runtime/platform/wireless/mode_client.c',
           'runtime/platform/wireless/mode_channel.c',
           'runtime/platform/wireless/mode_policy.c',
           'runtime/platform/espnow/xnow_owner_gate.c',
           'runtime/store/stock_fs_bridge.c', 'runtime/store/stock_stat64.c']
inputs = [*sources, str(owner_path.relative_to(ROOT)), str(fixture_path.relative_to(ROOT)),
          'runtime/apps/wireless-remote/owner_admission.h',
          'runtime/platform/espnow/xnow_owner_gate.h', 'tools/test_owner_retirement.py']
inputs += [p.relative_to(ROOT).as_posix() for directory in
           ('runtime/platform/wireless', 'runtime/platform/espnow')
           for p in (ROOT / directory).glob('*.h')]
inputs += ['runtime/platform/player/wireless_host.h', 'runtime/store/target_abi.h',
           'runtime/store/stock_fs_bridge.h', 'runtime/store/stock_stat64.h']
inputs = sorted(set(inputs))
report = dict(passed=False, device_accessed=False, firmware_created=False,
              real_observer_datagrams=True, real_retained_owner_gate=True,
              actual_shared_sleep_restore_caller=True, native_power_effects_modeled=True,
              actual_functions=['owner_mode_await', 'restore_shared_sleep'],
              outer_owner_runtime_executed=False, controller_state_is_fixture=True,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
              checks=[])
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
         '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-I', str(ROOT),
         '-DXNOW_OWNER_GATE_NAMESPACE="x1000-owner-retirement-test"']


def run_check(name, command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    (OUT / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    report['checks'].append(dict(name=name, exit_code=result.returncode,
                                 log=(OUT / (name + '.log')).relative_to(ROOT).as_posix()))
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if result.returncode:
        raise RuntimeError(name + ' failed; see ' + str(OUT / (name + '.log')))
    return result.stdout


host = OUT / 'test.host'
run_check('host-build', ['gcc', *flags, '-fsanitize=address,undefined', '-pthread',
                       *sources, '-o', str(host)])
host_output = run_check('host', [str(host)])
libs = stock_libraries()
arm = OUT / 'test.arm'
run_check('arm-build', ['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC',
                      '-D_DEFAULT_SOURCE=', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                      '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin',
                      '-fno-pie', '-fno-stack-protector', '-no-pie', '-nostdlib',
                      '-Wl,--hash-style=sysv,--build-id=none', *sources,
                      'runtime/store/start.c', 'runtime/store/start.S',
                      str(libs['libpthread.so.0']), str(libs['libc.so.6']),
                      str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)])
search = ':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
arm_output = run_check('arm', ['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                             '--library-path', search, str(arm)])
expected = [
    'expired-data-retained-borrow', 'stable-stop-revokes-data', 'draining-retained-lease',
    'failed-policy-not-repaired', 'associated-native-owner-not-slept', 'already-sleeping-no-write',
    'replacement-lease-refused', 'queued-old-proof-not-reused',
    'queued-old-proof-needs-fresh-serial', 'queued-proof-does-not-extend-timeout',
    'independent-owner-identity-lost', 'observer-descriptor-replaced', 'cleanup-query-timeout',
    'clock-regression-refused', 'unknown-native-state-refused',
    'fork-copy-refused-parent-can-clean', 'never-authorized-refused',
    'native-restore-error-retained',
]
for output in (host_output, arm_output):
    assert re.findall(r'^OWNER_RETIREMENT_CASE (.+)$', output, re.M) == expected
    assert 'OWNER_RETIREMENT_PASS' in output
report['cases'] = expected
report['passed'] = True
report['limits'] = ['Radio sleep/power effects and clock progression are fixtures.',
                    'No system ownership is inferred from the cooperative owner gate alone.',
                    'This does not qualify physical USB handoff, RF, sleep or installation.']
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, report=(OUT / 'report.json').relative_to(ROOT).as_posix())))
