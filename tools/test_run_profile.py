"""RAM-only run profile constructor: host sanitizers and original-libc ARM."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/run-profile-tests'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/apps/wireless-remote/run_profile.c','tools/test_run_profile.c'];flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'test.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=10);assert result.returncode==0,result.stdout+result.stderr
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm)],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert result.returncode==0 and 'RUN_PROFILE_PASS' in result.stdout,result.stdout+result.stderr
print(json.dumps(dict(passed=True,device_accessed=False,host_sanitizers=True,original_libc_arm926=True,entropy_modeled=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/apps/wireless-remote/run_profile.h','tools/test_run_profile.py']},limits=['Constructor/entropy refusal and in-place operation execute; entropy is deterministic fixture data.','No production Settings binding or hardware entropy/power qualification.']),indent=2))
