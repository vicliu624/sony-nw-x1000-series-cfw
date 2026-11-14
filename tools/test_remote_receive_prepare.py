"""Execute actual pairing/encrypted owner preparation with modeled stock calls.

This checks shared receive membership admission and cleanup. It cannot establish
physical MAC filtering, ciphertext admission or successful session negotiation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host-only', action='store_true',
                    help='Run the source-only caller check without Sony libraries or ARM tools')
options = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
owner = ROOT / 'runtime/apps/wireless-remote/rf_owner.c'
fixture = ROOT / 'tools/fixtures/remote_receive_prepare.c'
source = owner.read_text()
out = ROOT / 'work/remote-receive-prepare' / str(time.time_ns())
out.mkdir(parents=True)

start = source.index('#include <net/if.h>')
end = source.index('/* Only the managed owner loop', start)
membership = source[start:end]
start = source.index('static int owner_prepare(')
end = source.index('\nstatic int owner_close_data(', start)
prepare = source[start:end]
generated = out / 'actual-prepare.c'
generated.write_text(fixture.read_text().replace('/* ACTUAL_RECEIVE_MEMBERSHIP */', membership)
                     .replace('/* ACTUAL_OWNER_PREPARE */', prepare))
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
         '-I', str(ROOT)]
host = out / 'test.host'
subprocess.run(['gcc', *flags, '-fsanitize=address,undefined', str(generated),
                '-o', str(host)], check=True)
result = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
(out / 'host.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stdout + result.stderr
if not options.host_only:
    lib = ROOT / 'work/arm-signal-tests/lib'
    arm = out / 'test.arm'
    subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-U_FORTIFY_SOURCE',
                    '-D_FORTIFY_SOURCE=0', '-march=armv5te', '-marm', '-mfloat-abi=soft',
                    '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-no-pie',
                    '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none', str(generated),
                    str(ROOT / 'runtime/store/start.c'), str(ROOT / 'runtime/store/start.S'),
                    str(lib / 'libc.so.6'), str(lib / 'ld-linux.so.3'), '-lgcc',
                    '-o', str(arm)], check=True)
    result = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(lib / 'ld-linux.so.3'),
                             '--library-path', str(lib), str(arm)],
                            capture_output=True, text=True, timeout=10)
    (out / 'arm.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
report = dict(passed=True, host_sanitizers=True, original_libc_arm926=not options.host_only,
              actual_owner_prepare=True, shared_pairing_and_encrypted_paths=True,
              device_accessed=False, firmware_created=False,
              parent_observation_modeled=True,
              stop_and_parent_denial_block_ready=True,
              limits=['Socket operations, security setup and peer admission are modeled.',
                      'No physical MAC filtering or encrypted RF qualification.'],
              source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (owner, fixture, Path(__file__).resolve())})
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, report=str(out / 'report.json')), indent=2))
