"""Guarded stock API power-off helper: sanitizers and stock-libc ARM, RF modeled."""
import hashlib
import json
import os
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/xnow-power-off'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/espnow/xnow_power_off.c','runtime/platform/wireless/radio_modules.c','tools/test_xnow_power_off.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
checked=subprocess.run([str(host)],capture_output=True,text=True,timeout=15)
assert checked.returncode==0 and 'XNOW_POWER_OFF_PASS' in checked.stdout,checked.stdout+checked.stderr
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector',
                '-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',
                *sources,'runtime/store/start.c','runtime/store/start.S',
                str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',
                       str(libs['libc.so.6'].parent),str(arm)],cwd=ROOT,
                      env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=15)
assert result.returncode==0 and 'XNOW_POWER_OFF_PASS' in result.stdout,result.stdout+result.stderr
report=dict(passed=True,device_accessed=False,host_sanitizers=True,original_libc_arm926=True,
            stock_api_modeled=True,production_close_path_integrated=False,
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,
            'runtime/platform/espnow/xnow_power_off.h','runtime/platform/wireless/radio_modules.h','runtime/platform/espnow/xnow_manager.h',
            'runtime/platform/espnow/xnow_session.h','tools/test_xnow_power_off.py']},
            limits=['Exclusive ownership is supplied by a test callback; no production admission policy is implied.',
                    'No actual cnmgr call, RF transition or standby current measurement.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
