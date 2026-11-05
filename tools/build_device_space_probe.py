"""Build read-only fixed-partition space probe; never executes on device."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/device-space-probe'/str(time.time_ns());out.mkdir(parents=True)
libs=stock_libraries();source='runtime/apps/device-info/space_probe.c';artifact=out/'device-space-probe.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',source,'runtime/apps/device-info/device_info_space.c','runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(artifact),'--help'],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert run.returncode==0
report=dict(artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (source,'runtime/apps/device-info/device_info_space.c','runtime/apps/device-info/device_info_data.h','tools/build_device_space_probe.py')},help_original_libc_arm=True,device_accessed=False)
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
