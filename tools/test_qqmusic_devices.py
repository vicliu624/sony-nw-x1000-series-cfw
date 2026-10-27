"""Native GUI platform adapter with actual common logic, mocked raw IO only."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-devices';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
core=['runtime/apps/qqmusic/qqmusic_devices.c','runtime/native/linux_devices.c','runtime/native/frontend.c','tools/fixtures/qqmusic_devices.c']
host=work/'devices-tests.sanitized'
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-g','-O1','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
arm=work/'devices-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],cwd=ROOT,check=True,timeout=15)
report={'passed':True,'scope':'native_devices_to_app_loop_callbacks','physical_device_tested':False,
 'checks':['open validation','tap once on release','hold no repeated tap','movement cancels tap','raw Y overflow rejects saturated false hit','busy framebuffer defers then flushes','surface identity bound','clock and poll error propagation','stop signal','close idempotence','geometry reject cleanup','close failure propagation'],
 'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['runtime/apps/qqmusic/qqmusic_devices.h']}}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
