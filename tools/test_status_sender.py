"""Actual low-traffic sender under host sanitizers and original Sony libc."""
import hashlib,json,os,subprocess,time,sys
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/status-sender-tests'/str(time.time_ns());out.mkdir(parents=True)
sources=['tools/test_status_sender.c','runtime/apps/wireless-remote/status_sender.c',
 'runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/player_status.c','runtime/apps/wireless-remote/artwork_wire.c','runtime/apps/wireless-remote/artwork_client.c','runtime/apps/wireless-remote/artwork_image.c',
 'runtime/apps/wireless-remote/status_auth.c','runtime/apps/wireless-remote/receiver.c',
 'runtime/apps/wireless-remote/control.c','runtime/apps/wireless-remote/control_player.c','runtime/apps/wireless-remote/session_wire.c',
 'runtime/apps/wireless-remote/library_wire.c','runtime/apps/wireless-remote/library_player.c',
 'runtime/apps/wireless-remote/mode_wire.c','runtime/platform/player/client.c','runtime/native/sha256.c']
if '--fairness' in sys.argv:
 sources[0]='tools/test_artwork_fairness.c';sources+=['runtime/apps/wireless-remote/worker.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0']
host=out/'test.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=20)
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft',
 '-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',
 *sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm)],
 cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
assert run.returncode==0,run.stdout+run.stderr
headers=list((ROOT/'runtime/apps/wireless-remote').glob('*.h'))
inputs=[ROOT/p for p in sources]+headers+[ROOT/'tools/test_status_sender.py',ROOT/'runtime/platform/player/artwork.h']
if '--fairness' in sys.argv:inputs.append(ROOT/'tools/test_status_sender.c')
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,device_accessed=False,rf_qualified=False,
 stdout=run.stdout,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
