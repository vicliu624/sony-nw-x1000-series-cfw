"""Run autonomous test engine with actual native full stack; no device access."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/autonomous-espnow-test';OUT.mkdir(exist_ok=True)
sources=['tools/fixtures/autonomous_probe.c','runtime/apps/espnow-test/runner.c','tools/fixtures/xnow_control_platform.c']+['runtime/platform/espnow/'+n+'.c' for n in ('xnow_full_control','xnow_session','xnow_manager','xnow_endpoint','xnow_peer','xnow_full','xnow_wire')]
sources+=['runtime/native/sha256.c']
flags=['-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections']
host=OUT/'probe.host';subprocess.run(['gcc',*flags,'-fsanitize=address,undefined','-g',*sources,'-o',str(host)],cwd=ROOT,check=True)
a=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=20)
lib=ROOT/'work/arm-signal-tests/lib';arm=OUT/'probe.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
b=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,check=True,timeout=20)
report={'passed':True,'host_asan_ubsan':a.stdout,'arm926_stock_libc':b.stdout,'actual_full_controller_endpoint_backend':True,'stock_driver_ap_effects_modeled':True,'device_accessed':False,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'tools/fixtures/full_owner_ipc.c','tools/test_xnow_full.c','runtime/apps/espnow-test/runner.h','tools/test_autonomous_probe.py']}}
(OUT/'tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
