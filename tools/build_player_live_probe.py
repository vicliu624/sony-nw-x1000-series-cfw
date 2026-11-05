"""Build a bounded read-only startup client; never deploys or activates it."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/player-live-probe'/str(time.time_ns());out.mkdir(parents=True)
names=('client','managed_remote','managed_client','managed_codec','managed_clock','rpc_wire','startup_delivery')
sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/descriptor.c','runtime/store/deadline.c','runtime/store/start.c','runtime/store/start.S','runtime/apps/wireless-remote/probe.c']
libs=stock_libraries(include_rt=True);artifact=out/'player-readonly-probe.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-I'+str(ROOT/'sdk/include'),'-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,str(libs['librt.so.1']),str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
paths=':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',paths,str(artifact),'--help'],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10)
assert run.returncode==0 and 'player probe:' in run.stdout,run.stdout+run.stderr
report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),original_libc_arm_help_passed=True,device_accessed=False,activated=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},limits=['No real-player session executed by this builder.','Explicit temporary IPC directory and startup peer required.','Read grant only; no playback command is sent.'])
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
