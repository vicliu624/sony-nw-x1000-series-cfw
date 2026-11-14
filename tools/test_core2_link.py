"""Exercise the actual Core2 link adapter through the public ESP-NOW peer API seam."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT

out=ROOT/'work/core2-link-tests'/str(time.time_ns())
out.mkdir(parents=True)
sources=['runtime/platform/espnow/xnow_link.c','runtime/native/sha256.c']
cxx=['runtime/apps/wireless-remote/core2/src/link_transport.cpp','tools/fixtures/core2_link.cpp']
flags=['-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(ROOT),
       '-I',str(ROOT/'tools/fixtures/core2_link')]
objects=[]
for source in sources:
    obj=out/(Path(source).stem+'.o')
    subprocess.run(['gcc-12','-std=c99',*flags,'-c',source,'-o',str(obj)],check=True)
    objects.append(str(obj))
binary=out/'test.host'
subprocess.run(['g++-12','-std=c++20',*flags,*cxx,*objects,'-o',str(binary)],check=True)
result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
(out/'host.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'CORE2_LINK_TRANSPORT_PASS' in result.stdout,result.stdout+result.stderr
inputs=[*sources,*cxx,'runtime/platform/espnow/xnow_link.h',
        'runtime/apps/wireless-remote/core2/src/link_transport.h',
        'tools/fixtures/core2_link/esp_now.h','tools/fixtures/core2_link/esp_random.h',
        'tools/test_core2_link.py']
report=dict(passed=True,public_native_api_model=True,host_sanitizers=True,device_accessed=False,
    covers=['no encrypted static-key bootstrap','native key install waits for TX idle',
            'both process restarts','matching key derivation','duplicate Ready does not reinstall',
            'no idle heartbeat','bounded NO_MEM resubmit','deadline after native key install',
            'failure closes data admission','stop retains peer until native TX completion'],
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix())))
