"""Offline normalized-observation storage preflight tests, no device/filesystem writer."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-storage';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_storage.c','tools/fixtures/qqmusic_storage.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'storage-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)],cwd=ROOT,check=True,timeout=15)
host=work/'storage-tests.sanitized'
subprocess.run(['gcc-12','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=15)
report={'passed':True,'scope':'pure normalized observations and space planning',
        'device_access':False,'writes_implemented':False,'ready_to_flash':False,
        'cases':['matching mounted vfat and distinct root/user devices','single old-kernel rootfs underlay before actual root accepted; duplicate/reversed roots rejected','duplicate user mount still rejected','missing/wrong/readonly/nested mounts',
                 'root-backed destination, symlink mode, invalid or missing directory prefixes',
                 'cluster rounding, retained source peak, low space and uint64 overflow','truncated mount snapshots'],
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_storage.h','tools/test_qqmusic_storage.py']},
        'limits':['Caller-supplied observations: no native mount/statvfs/ABI implementation.',
                  'Not a write capability or protection against concurrent mounts/path replacement.',
                  'Space is preflight, not reserved against concurrent users.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
