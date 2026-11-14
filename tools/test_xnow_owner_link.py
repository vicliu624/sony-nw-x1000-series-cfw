"""Root link adapter through actual endpoint/CCMP code and modeled radio words."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

out=ROOT/'work/xnow-owner-link-tests'/str(time.time_ns())
out.mkdir(parents=True)
sources=['tools/fixtures/xnow_owner_link.c']+['runtime/platform/espnow/'+name+'.c' for name in
    ('xnow_owner_link','xnow_link','xnow_link_counter','xnow_endpoint','xnow_endpoint_security',
     'xnow_security','xnow_ccmp','xnow_pn','xnow_full','xnow_peer','xnow_wire')]+['runtime/native/sha256.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT),
       '-I',str(ROOT/'work/external-tls-probe/bearssl-0.6/inc')]
host=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,
    str(ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'),'-o',str(host)],check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=15)
(out/'host.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'XNOW_OWNER_LINK_PASS' in result.stdout,result.stdout+result.stderr
libs=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector',
    '-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,
    'runtime/store/start.c','runtime/store/start.S',
    str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(libs['libc.so.6']),
    str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),
    '--library-path',str(libs['libc.so.6'].parent),str(arm)],capture_output=True,text=True,timeout=15)
(out/'arm.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'XNOW_OWNER_LINK_PASS' in result.stdout,result.stdout+result.stderr
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,
    actual_endpoint_and_ccmp=True,radio_words_modeled=True,device_accessed=False,
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        [*sources,'runtime/platform/espnow/xnow_owner_link.h','runtime/platform/espnow/xnow_owner_runtime.h',
         'runtime/platform/espnow/xnow_link_counter.h','runtime/platform/espnow/xnow_link.h',
         'tools/test_xnow_owner_link.py','tools/test_xnow_full.c']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix())))
