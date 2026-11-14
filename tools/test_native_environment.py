"""Exercise the real private process adapter with modeled filesystem/RF effects."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time
from player_arm_guest import ROOT, stock_libraries

OUT = ROOT / 'work/native-environment-tests' / str(time.time_ns())
OUT.mkdir(parents=True)
sources = ['runtime/platform/espnow/native_environment.c', 'tools/fixtures/native_environment.c']
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
wraps = ['fopen', 'fopen64', 'fgets', 'ferror', 'fclose', 'readlink', 'open', 'open64',
         'close', 'read', 'gettimeofday']
checks = []


def run(name, command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
    log = OUT / (name + '.log')
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    checks.append(dict(name=name, exit_code=result.returncode, log=log.relative_to(ROOT).as_posix()))
    if result.returncode:
        raise RuntimeError(name + ' failed: ' + str(log))
    return result.stdout


host = OUT / 'test.host'
run('host-build', ['gcc', *flags, '-fsanitize=address,undefined', *sources,
                   *['-Wl,--wrap=' + name for name in wraps + ['lstat', 'fstat']], '-o', str(host)])
host_output = run('host', [str(host)])
libs = stock_libraries()
arm = OUT / 'test.arm'
run('arm-build', ['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC',
    '-D_DEFAULT_SOURCE=', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-march=armv5te',
    '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie', '-fno-stack-protector',
    '-nostdlib', '-no-pie', '-Wl,--hash-style=sysv,--build-id=none', *sources,
    *['-Wl,--wrap=' + name for name in wraps + ['hb_target_lstat', 'hb_target_fstat']],
    'runtime/store/start.c', 'runtime/store/start.S', str(libs['libc.so.6']),
    str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)])
search = ':'.join(dict.fromkeys(str(path.parent) for path in libs.values()))
arm_output = run('arm', ['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                          '--library-path', search, str(arm)])
expected = ['stock-root', 'user-candidate', 'shared-root-no-load', 'cold-root-load',
    'restore-without-user-volume', 'writable-root-refused', 'wrong-user-volume',
    'nested-mount-refused', 'wrong-stock-link', 'system-volume-refused',
    'child-symlink-refused', 'exact-keys-after-eintr', 'key-hardlink-refused',
    'fresh-security', 'resume-never-provisions', 'partial-prepare-retains-directory',
    'retained-security-callbacks', 'log-failure-after-reservation',
    'random-short-read-closes', 'original-timeval-layout']
for output in (host_output, arm_output):
    assert 'NATIVE_ENVIRONMENT_PASS' in output
    assert re.findall(r'^NATIVE_ENVIRONMENT_CASE (.+)$', output, re.M) == expected
inputs = [*sources, 'tools/test_native_environment.py', 'runtime/store/start.c', 'runtime/store/start.S',
          'runtime/store/target_abi.h', 'runtime/store/stock_fs_bridge.h', 'runtime/store/stock_stat64.h']
inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT / 'runtime/platform/espnow').glob('*.h')]
report = dict(passed=True, device_accessed=False, firmware_created=False,
    host_sanitizers=True, original_libc_arm926=True, actual_private_environment_module=True,
    filesystem_crypto_counters_and_radio_effects_modeled=True, cases=expected, checks=checks,
    source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs},
    limits=['This is the real process adapter with explicit syscall/crypto/PN/radio models.',
            'It does not qualify physical mounts, USB exclusion, cryptographic primitives or FAT durability.',
            'The counter reservation already happened when logging fails; no retry/reset is manufactured.'])
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, cases=len(expected), report=(OUT / 'report.json').relative_to(ROOT).as_posix())))
