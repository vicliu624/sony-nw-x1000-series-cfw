"""Execute file checks with pinned Sony libc under QEMU, on PC temp files only."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/espnow-file-check-arm'
LIB = ROOT / 'work/arm-signal-tests/lib'
OUT.mkdir(parents=True, exist_ok=True)
for name, digest in {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    if hashlib.sha256((LIB / name).read_bytes()).hexdigest() != digest:
        raise ValueError('unqualified Sony libc input')
sources = ['tools/test_xnow_file_check.c', 'runtime/platform/espnow/xnow_file_check.c',
           'runtime/native/sha256.c', 'runtime/store/stock_fs_bridge.c',
           'runtime/store/stock_stat64.c', 'runtime/store/start.c', 'runtime/store/start.S']
objects = []
for index, source in enumerate(sources):
    obj = OUT / f'{index}.o'
    subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
                    '-D_DEFAULT_SOURCE', '-DHB_STORE_SONY_LIBC', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                    '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie',
                    '-fno-stack-protector', '-c', source, '-o', str(obj)], cwd=ROOT, check=True)
    objects.append(str(obj))
app = OUT / 'test'
subprocess.run(['arm-linux-gnueabi-gcc', '-nostdlib', '-no-pie', '-Wl,--hash-style=sysv',
                '-Wl,--build-id=none', '-Wl,--dynamic-linker=/lib/ld-linux.so.3', *objects,
                str(LIB / 'libc.so.6'), str(LIB / 'ld-linux.so.3'), '-lgcc', '-o', str(app)],
               cwd=ROOT, check=True)
run = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(LIB / 'ld-linux.so.3'),
                      '--library-path', str(LIB), str(app)],
                     capture_output=True, text=True, timeout=20, check=True)
report = {'passed': True, 'stdout': run.stdout, 'stderr': run.stderr,
          'sha256': hashlib.sha256(app.read_bytes()).hexdigest(),
          'source_hashes': {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in sources},
          'sony_libc': True, 'stock_stat_bridge': True, 'qemu_arm926': True,
          'host_temporary_files_only': True, 'device_accessed': False,
          'usb_ownership_qualified': False}
(OUT / 'report.json').write_text(json.dumps(report, indent=2))
print(run.stdout.strip())
