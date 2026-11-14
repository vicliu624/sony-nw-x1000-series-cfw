"""Real SDK IPC through actual service sampling/sender/worker; modeled media and RF."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time
from player_arm_guest import ROOT, stock_libraries

OUT = ROOT / 'work/remote-observation-chain' / str(time.time_ns())
OUT.mkdir(parents=True)
sources = ['tools/fixtures/remote_observation_chain.c']
sources += ['runtime/apps/wireless-remote/' + name + '.c' for name in (
    'worker', 'status_sender', 'link', 'player_status', 'artwork_wire', 'status_auth',
    'receiver', 'control', 'control_player', 'session_wire', 'library_wire', 'library_player', 'mode_wire')]
sources += ['runtime/platform/player/' + name + '.c' for name in (
    'client', 'managed', 'managed_rpc', 'rpc_wire', 'managed_channel', 'managed_control',
    'managed_codec', 'managed_remote', 'managed_client')]
sources += ['runtime/platform/services/' + name + '.c' for name in ('session', 'request', 'events')]
sources += ['runtime/native/sha256.c']
flags = ['-std=c99', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
         '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections']
checks = []


def run(name, command, timeout=30):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    log = OUT / (name + '.log')
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    checks.append(dict(name=name, exit_code=result.returncode, log=log.relative_to(ROOT).as_posix()))
    if result.returncode:
        raise RuntimeError(name + ' failed: ' + str(log))
    return result.stdout


host = OUT / 'test.host'
run('host-build', ['gcc-12', *flags, '-fsanitize=address,undefined', '-pthread', *sources,
                    '-lrt', '-o', str(host)])
host_output = run('host', [str(host)])
libs = stock_libraries(include_rt=True)
arm = OUT / 'test.arm'
run('arm-build', ['arm-linux-gnueabi-gcc', *flags, '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie', '-fno-stack-protector',
    '-nostdlib', '-no-pie', '-Wl,--hash-style=sysv,--build-id=none', *sources,
    'runtime/store/start.c', 'runtime/store/start.S', str(libs['libpthread.so.0']),
    str(libs['librt.so.1']), str(libs['libc.so.6']), str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)])
search = ':'.join(dict.fromkeys(str(path.parent) for path in libs.values()))
arm_output = run('arm', ['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                          '--library-path', search, str(arm)])
expected = ['live-unavailable-recovery-no-heartbeat', 'media-io-stops-with-close-receipt',
            'transport-eof-is-not-a-live-observation']
for output in (host_output, arm_output):
    assert 'REMOTE_OBSERVATION_CHAIN_PASS' in output
    assert re.findall(r'^REMOTE_OBSERVATION_CASE (.+)$', output, re.M) == expected
inputs = [*sources, 'runtime/apps/wireless-remote/service.c', 'tools/test_remote_observation_chain.py',
          'runtime/store/start.c', 'runtime/store/start.S']
inputs += [path.relative_to(ROOT).as_posix() for folder in (
    'runtime/apps/wireless-remote', 'runtime/platform/player', 'runtime/platform/services',
    'runtime/platform/espnow') for path in (ROOT / folder).glob('*.h')]
report = dict(passed=True, device_accessed=False, firmware_created=False,
    actual_service_callbacks=True, actual_worker_sender_receiver=True,
    real_sdk_request_reply_and_close=True, real_local_processes=True,
    host_sanitizers=True, original_libc_arm926=True,
    media_radio_and_schedule_clock_modeled=True, transport_clock_is_real=True,
    cases=expected, checks=checks,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(set(inputs))},
    limits=['Backend observations and RF completions are models; service callbacks, codecs and local IPC execute.',
            'Worker scheduling uses an explicit clock; SDK request deadlines use the original libc monotonic clock.',
            'This excludes a response-classification failure at this software seam, not a physical GUI/RF timeout.',
            'No original media engine, Wi-Fi, RF, display, USB or firmware installation is qualified.'])
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, cases=3, report=(OUT / 'report.json').relative_to(ROOT).as_posix())))
