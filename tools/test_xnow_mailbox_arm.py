"""Build/run mailbox mock tests using the original Sony libc on ARM QEMU."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/espnow-mailbox-arm'
OUT.mkdir(parents=True, exist_ok=True)
LIB = ROOT/'work/arm-signal-tests/lib'
for name, digest in {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest() == digest
objects = []
for i, source in enumerate(['tools/test_xnow_mailbox.c', 'runtime/platform/espnow/xnow_mailbox.c',
                            'runtime/store/start.c', 'runtime/store/start.S']):
    obj = OUT/f'{i}.o'
    subprocess.run(['arm-linux-gnueabi-gcc', '-Os', '-Wall', '-Wextra', '-Werror',
                    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-ffreestanding',
                    '-fno-pie', '-fno-builtin', '-fno-stack-protector',
                    '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-D_DEFAULT_SOURCE',
                    '-c', source, '-o', str(obj)], cwd=ROOT, check=True)
    objects.append(str(obj))
app = OUT/'mailbox-test'
subprocess.run(['arm-linux-gnueabi-gcc', '-nostdlib', '-no-pie', '-Wl,--hash-style=sysv',
                '-Wl,--build-id=none', '-Wl,--dynamic-linker=/lib/ld-linux.so.3',
                *objects, str(LIB/'libc.so.6'), str(LIB/'ld-linux.so.3'), '-lgcc',
                '-o', str(app)], cwd=ROOT, check=True)
r = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(LIB/'ld-linux.so.3'),
                    '--library-path', str(LIB), str(app)], capture_output=True, text=True, timeout=15)
assert r.returncode == 0, (r.stdout, r.stderr)
report = {'passed': True, 'cpu': 'arm926', 'original_libc': True, 'stdout': r.stdout,
          'mailbox_backend_mocked': True, 'device_accessed': False}
(OUT/'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
