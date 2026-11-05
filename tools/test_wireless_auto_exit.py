"""Real wireless-auto/policy core with explicit lifecycle and RF observation fixtures."""
import hashlib,json,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/wireless-auto-exit'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/wireless_auto.c','runtime/platform/wireless/mode_policy.c','tools/fixtures/wireless_auto_exit.c']
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined','-pthread',*sources,'-o',str(host)],cwd=ROOT,check=True)
r=subprocess.run([str(host)],capture_output=True,text=True,timeout=10)
(out/'host.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
libs=stock_libraries();binary=out/'init.arm';startup=['runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,*startup,str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
report=run_guest(out,binary,{},libs,['WIRELESS_AUTO_EXIT_GUARD_PASS'])
report.update(host_sanitizers=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*startup,'tools/test_wireless_auto_exit.py']},limits=['Original-exiting result and boot OFF observation are fixtures; actual auto and mode-policy initialization execute.','No original GUI, RF hardware or actual first-owner binding/order executes.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
