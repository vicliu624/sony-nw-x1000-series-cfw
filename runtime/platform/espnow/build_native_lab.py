"""PC-only build. No installation or device access."""
import hashlib
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'work/espnow-native-lab'
OUT.mkdir(parents=True, exist_ok=True)
LIB = ROOT / 'work/arm-signal-tests/lib'
for name, digest in {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest() == digest
objects = []
for i, source in enumerate(['runtime/platform/espnow/native_lab.c', 'runtime/platform/espnow/xnow_mailbox.c', 'runtime/platform/espnow/xnow_sd8686.c', 'runtime/native/sha256.c', 'runtime/store/start.c', 'runtime/store/start.S']):
    obj = OUT / f'{i}.o'
    subprocess.run(['arm-linux-gnueabi-gcc', '-Os', '-Wall', '-Wextra', '-Werror',
                    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-pie',
                    '-fno-stack-protector', '-fno-builtin', '-D_DEFAULT_SOURCE',
                    '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-I'+str(ROOT/'work/espnow-radio-bridge'),
                    '-c', source, '-o', str(obj)], cwd=ROOT, check=True)
    objects.append(str(obj))
app = OUT/'xnow-lab'
subprocess.run(['arm-linux-gnueabi-gcc', '-nostdlib', '-no-pie',
                '-Wl,--hash-style=sysv', '-Wl,--build-id=none',
                '-Wl,--dynamic-linker=/lib/ld-linux.so.3', *objects,
                str(LIB/'libc.so.6'), str(LIB/'ld-linux.so.3'), '-lgcc',
                '-o', str(app)], cwd=ROOT, check=True)
for flag in ['--help', '--version']:
    subprocess.run(['qemu-arm', '-cpu', 'arm926', str(LIB/'ld-linux.so.3'),
                    '--library-path', str(LIB), str(app), flag], check=True)
print(app, hashlib.sha256(app.read_bytes()).hexdigest())

