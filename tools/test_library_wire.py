"""Authenticated library request/reply codec on host and original-libc ARM; no RF."""
import hashlib,json,os,subprocess,time,sys
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/remote-library-wire'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/apps/wireless-remote/library_wire.c','runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/status_auth.c','runtime/native/sha256.c','tools/test_library_wire.c']
dispatch='--player-dispatch' in sys.argv
if dispatch:sources=['runtime/apps/wireless-remote/library_player.c','runtime/platform/player/client.c','tools/test_library_player.c']
client='--client' in sys.argv
if client:
 assert not dispatch
 sources=[p for p in sources if p!='tools/test_library_wire.c']+['runtime/apps/wireless-remote/library_client.c','tools/test_library_client.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'test.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],capture_output=True,text=True,check=True)
libs=stock_libraries();arm=out/'test.arm';startup=['runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none',*sources,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,check=True)
assert ('REMOTE_LIBRARY_CLIENT_CORRELATION_PASS' if client else 'REMOTE_LIBRARY_PLAYER_DISPATCH_PASS' if dispatch else 'REMOTE_LIBRARY_WIRE_PASS') in run.stdout
report=dict(passed=True,host_sanitizers=True,original_libc_arm=True,device_accessed=False,radio_started=False,integrated_into_service=False,
 player_dispatch_checked=dispatch,player_provider_modeled=dispatch,controller_client_checked=client,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*startup,'runtime/apps/wireless-remote/library_wire.h','runtime/apps/wireless-remote/library_client.h','runtime/apps/wireless-remote/library_player.h','tools/test_library_wire.py']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
