"""Guest-only idle DSP adapter contracts using the original Sony libc on ARM926."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/stock-dsp-idle-tests'/str(time.time_ns());out.mkdir(parents=True)
libs=stock_libraries();source='tools/fixtures/stock_dsp_idle_test.c';binary=out/'test.arm'
inputs=[source,'tools/fixtures/stock_dsp_idle_model.h','runtime/store/start.c','runtime/store/start.S',__file__]
subprocess.run(['arm-linux-gnueabi-gcc','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
 '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-no-pie','-fno-pie',
 '-nostdlib','-Wl,--hash-style=sysv,--build-id=none',source,'runtime/store/start.c','runtime/store/start.S',
 str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
r=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(binary)],
 env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=15)
(out/'run.log').write_text(r.stdout+r.stderr);assert not r.returncode,r.stdout+r.stderr
assert 'STOCK_DSP_IDLE_MODEL_PASS' in r.stdout
report=dict(passed=True,original_libc_arm926=True,physical_device_access=False,
 transfer_bounds_checked=True,empty_nonblocking_read='EAGAIN, packet unchanged',
 empty_blocking_read='waits until killed by signal',dsp_messages_generated=False,dsp_instruction_execution=False,
 source_hashes={(ROOT/p).resolve().relative_to(ROOT).as_posix():hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
