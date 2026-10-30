"""PC-only ABI-pinned read-only probe build. No installation/device calls."""
import hashlib
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'work/espnow-current-connection-probe';OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
for path,digest in {
    LIB/'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    LIB/'ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
    STOCK/'libcnmgr.so.1':'688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1',
    RESOLVER/'libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474',
}.items():
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('unqualified library')
sources=['runtime/platform/espnow/current_connection_probe.c','runtime/store/stock_fs_bridge.c',
         'runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
app=OUT/'current-connection-probe'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                '-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
                '-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
                *sources,str(STOCK/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0'),
                str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',f'{LIB}:{STOCK}:{RESOLVER}',str(app)]
subprocess.run(base+['--help'],check=True)
test=subprocess.run(base+['--query'],capture_output=True,text=True,timeout=10)
assert test.returncode==69 and 'no client initialized' in test.stdout,(test.stdout,test.stderr)
print(app,hashlib.sha256(app.read_bytes()).hexdigest())
