"""RFC7748 vectors and complete code-free handshake; no device operations."""
import json,subprocess,time
from pathlib import Path
from app_registry import ROOT
from pairing_crypto import inputs
from player_arm_guest import stock_libraries
sources,flags=inputs()
sources+=['tools/test_pairing_auto.c','runtime/apps/wireless-remote/pairing_proof.c',
          'runtime/apps/wireless-remote/status_auth.c','runtime/apps/wireless-remote/link.c','runtime/native/sha256.c']
out=ROOT/'work/pairing-auto-tests'/str(time.time_ns());out.mkdir(parents=True)
common=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*flags]
host=out/'test.host';subprocess.run(['gcc',*common,'-fsanitize=address,undefined',*sources,'-o',str(host)],check=True)
r=subprocess.run([str(host)],text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stdout+r.stderr
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],check=True)
r=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm)],text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stdout+r.stderr
print(json.dumps(dict(passed=True,rfc7748=True,host_sanitizers=True,original_libc_arm926=True,code_free_key_agreement=True,mutations_rejected=True,device_accessed=False)))
