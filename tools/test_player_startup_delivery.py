"""Private one-start rendezvous, host sanitizers and original-libc ARM; no device."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/player-startup-delivery'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/startup_delivery.c','runtime/platform/services/descriptor.c','tools/fixtures/player_startup_delivery.c']
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'tools/fixtures/player_host_clock.c','-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=10);assert run.returncode==0,run.stdout+run.stderr
libs=stock_libraries(include_rt=True);arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/deadline.c','runtime/store/start.c','runtime/store/start.S',str(libs['librt.so.1']),str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
paths=':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
checked=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',paths,str(arm)],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10)
assert checked.returncode==0,checked.stdout+checked.stderr
report=dict(passed=True,device_accessed=False,host_sanitizers=True,original_libc_arm926=True,sony_kernel=False,cases=['connected datagram carries SDK stream descriptor','wrong nonce rejected','absent accept times out','existing endpoint retained','non-RAM path rejected'],stdout=checked.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/startup_delivery.h','tools/test_player_startup_delivery.py']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
