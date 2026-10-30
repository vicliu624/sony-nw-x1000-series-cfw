"""Production owner-service startup recovery with modeled dependencies."""
import hashlib,json,os,subprocess
from pathlib import Path
from app_registry import ROOT
w=ROOT/'work/player-host-service';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/host_service.c','tools/fixtures/player_host_service.c'];host=w/'host';arm=w/'service.arm'
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
subprocess.run(['gcc-12',*flags,'-O1','-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
h=subprocess.run([str(host)],capture_output=True,text=True,timeout=10);assert h.returncode==0,h.stdout+h.stderr
lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
a=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert a.returncode==0,a.stdout+a.stderr
for command in ([str(host),'--rollback'],['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm),'--rollback']):
 result=subprocess.run(command,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10)
 assert result.returncode==0,result.stdout+result.stderr
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,production_dispatch=True,dependencies_modeled=True,device_accessed=False,stdout=a.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_player_host_service.py']},limits=['Broker, local listener and monotonic clock are modeled; actual IPC and original provider are covered separately.','No full Sony app startup, source lifecycle, power, USB or hardware operation is qualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
