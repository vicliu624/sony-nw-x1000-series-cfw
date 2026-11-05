"""Private mode-owner core: host sanitizers and stock-libc ARM, hardware absent."""
import hashlib,json,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/wireless-mode-policy'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/wireless/mode_policy.c','runtime/platform/wireless/native_setting.c','runtime/platform/wireless/native_owner.c','tools/test_wireless_mode_policy.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'test.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined','-pthread',*sources,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=15);assert run.returncode==0,run.stdout+run.stderr
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft',
 '-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none',*sources,
 'runtime/store/start.c','runtime/store/start.S',str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
init=out/'init.arm';init_source='tools/fixtures/player_worker_system_init.c'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft',
 '-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none',init_source,
 'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
guest=run_guest(out,init,{'test':arm},libs,['WIRELESS_MODE_POLICY_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
assert guest['passed'],(out/'serial.log').read_text(errors='replace')[-2000:]
report=dict(passed=True,device_accessed=False,host_sanitizers=True,original_libc_arm926=True,
            generic_arm_guest=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,init_source,'runtime/platform/wireless/native_owner.h','runtime/platform/wireless/native_setting.h','runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h','tools/test_wireless_mode_policy.py']},
            limits=['One serialized authority instance in a generic ARM kernel; no Sony kernel/APF or cross-process broker qualification.',
                    'No native mode GUI or persistence.',
                    'Off/native evidence is supplied by fixtures; no physical radio/voltage/current check.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
