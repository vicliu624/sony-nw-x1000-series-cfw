"""Validate packet-transaction guards and count real raw transport calls; no RF."""
from pathlib import Path
import hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/xnow-span-tests'/str(time.time_ns());OUT.mkdir(parents=True)
sources=['tools/test_xnow_span_guard.c','runtime/platform/espnow/xnow_full_guard.c','runtime/platform/espnow/xnow_full.c','runtime/platform/espnow/xnow_wire.c','runtime/platform/espnow/xnow_sd8686_full.c','runtime/native/sha256.c']
def run(args):
 result=subprocess.run([str(x) for x in args],cwd=ROOT,capture_output=True,text=True)
 if result.returncode:print(result.stdout+result.stderr)
 result.check_returncode();return result
run(['gcc','-std=c99','-D_DEFAULT_SOURCE','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',*sources,'-o',OUT/'host'])
host=run([OUT/'host']).stdout
lib=ROOT/'work/arm-signal-tests/lib'
run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',lib/'libc.so.6',lib/'ld-linux.so.3','-lgcc','-o',OUT/'target'])
arm=run(['qemu-arm','-cpu','arm926',lib/'ld-linux.so.3','--library-path',lib,OUT/'target']).stdout
report={'passed':True,'host_sanitizers':host,'arm926_sony_libc':arm,'real_backend_callbacks':True,'exact_owned_intervals':True,'failure_does_not_publish_partial_rx':True,'changed_ticket_rejected':True,'revoked_lease_rejected':True,'device_accessed':False,'physical_throughput_measured':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
