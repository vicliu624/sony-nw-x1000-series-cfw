"""Actual hidden adapter + page bridge, with explicit backend/view fixtures."""
import hashlib,json,subprocess,time,os
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/remote-page-adapter'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/remote_page_adapter.c','runtime/apps/wireless-remote/native_page_bridge.c','tools/fixtures/remote_page_adapter_policy.c']
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Dpthread_self=wr_test_thread_self']
host=out/'host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=10);assert result.returncode==0,result.stdout+result.stderr
libs=stock_libraries();binary=out/'adapter.arm';init=out/'init.arm';startup=['runtime/store/start.c','runtime/store/start.S']
arm=[*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none,-Ttext-segment=0x01000000,--dynamic-linker=/lib/ld-linux.so.3']
subprocess.run(['arm-linux-gnueabi-gcc',*arm,*sources,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
init_source='tools/fixtures/player_worker_system_init.c'
subprocess.run(['arm-linux-gnueabi-gcc',*arm,init_source,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':binary},libs,['REMOTE_PAGE_ADAPTER_POLICY_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
report.update(host_sanitizers=True,original_libc_adapter_executed=True,backend_and_view_operations_modeled=True,
 device_accessed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+startup+[init_source,'tools/test_remote_page_adapter.py','runtime/platform/player/remote_page_guard.h','runtime/apps/wireless-remote/native_page_bridge.h','runtime/apps/wireless-remote/native_choice_view.h']},
 limits=['Actual adapter/bridge execute; factory backend, owner and native view operations are fixtures.',
         'No original UI/controller/renderer, guarded PID dispatch or live RF is exercised by this test.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
