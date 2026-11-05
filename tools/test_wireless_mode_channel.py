"""Actual cross-process mode-capability IPC; hardware/native evidence modeled."""
import hashlib,json,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/wireless-mode-channel'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/wireless/mode_policy.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/native_permission.c','runtime/platform/wireless/native_rf_worker.c','runtime/platform/wireless/native_offer.c','runtime/platform/wireless/native_delivery.c','runtime/platform/wireless/native_retirement.c','runtime/platform/wireless/native_boot.c','runtime/platform/wireless/native_bootstrap.c','runtime/platform/wireless/native_publisher.c','runtime/platform/wireless/radio_modules.c','runtime/platform/player/wireless_host.c','runtime/platform/player/wireless_auto.c','runtime/store/deadline.c','tools/test_wireless_mode_channel.c']
sources+=['runtime/apps/wireless-remote/owner_admission.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'test.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined','-pthread','-Wl,--wrap=poll',*sources,'-o',str(host)],cwd=ROOT,check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=20);assert result.returncode==0,result.stdout+result.stderr
libs=stock_libraries();libs['librt.so.1']=ROOT/'work/stock-resolver-probe/librt.so.1'
startup=['runtime/store/start.c','runtime/store/start.S'];arm=out/'test.arm';init=out/'init.arm'
armflags=[*flags,'-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none,--wrap=poll']
bridges=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c'];init_source='tools/fixtures/player_worker_system_init.c'
links=[str(libs[n]) for n in ('libpthread.so.0','librt.so.1','libc.so.6','ld-linux.so.3')]
subprocess.run(['arm-linux-gnueabi-gcc',*armflags,*sources,*bridges,*startup,*links,'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*armflags,init_source,*startup,*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
guest=run_guest(out,init,{'test':arm},libs,['WIRELESS_MODE_CHANNEL_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
assert guest['passed'],(out/'serial.log').read_text(errors='replace')[-2500:]
report=dict(passed=True,device_accessed=False,host_sanitizers=True,actual_cross_process_ipc=True,
            owner_admission_cases=6,
            owner_admission_periodic_cases=4,periodic_clock_modeled=True,
            original_libc_arm_guest=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*bridges,*startup,init_source,'runtime/apps/wireless-remote/owner_admission.h',
            'runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_client.h','runtime/platform/wireless/native_permission.h','runtime/platform/wireless/native_rf_worker.h','runtime/platform/wireless/native_offer.h','runtime/platform/wireless/native_delivery.h','runtime/platform/wireless/native_retirement.h','runtime/platform/wireless/native_boot.h','runtime/platform/wireless/native_publisher.h','runtime/platform/wireless/radio_modules.h','runtime/platform/player/wireless_host.h','runtime/store/deadline.h','runtime/platform/wireless/mode.h','tools/test_wireless_mode_channel.py']},
            limits=['Channels/grants/consumer identities are supplied by a trusted fixture parent; no installed daemon/launcher registration.',
                    'Driver retirement/off evidence is modeled by a separate fixture pipe, never by the mode client RPC.',
                    'No native UI, original Wi-Fi interception, hardware or persistence qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
