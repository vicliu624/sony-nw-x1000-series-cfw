"""Connect real Root owner IPC/crypto and the Core2 native peer adapter offline."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT

out=ROOT/'work/core2-owner-bus'/str(time.time_ns());out.mkdir(parents=True)
sources=['tools/fixtures/core2_owner_bus.c','tools/fixtures/xnow_control_platform.c']
sources+=['runtime/platform/espnow/'+name+'.c' for name in
    ('xnow_owner_runtime','xnow_owner_gate','xnow_handoff_owner','xnow_owner_stream',
     'xnow_owner_commands','xnow_owner_commands_control','xnow_full_control','xnow_session',
     'xnow_manager','xnow_endpoint','xnow_peer','xnow_wire','xnow_full','xnow_owner_link',
     'xnow_link','xnow_link_counter','xnow_endpoint_security','xnow_security','xnow_ccmp','xnow_pn')]
sources+=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/native/sha256.c']
cxx=['tools/fixtures/core2_owner_bus.cpp','runtime/apps/wireless-remote/core2/src/link_transport.cpp']
flags=['-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined',
       '-I',str(ROOT),'-I',str(ROOT/'tools/fixtures/core2_link'),
       '-I',str(ROOT/'work/external-tls-probe/bearssl-0.6/inc'),
       '-DXNOW_OWNER_GATE_NAMESPACE="x1000-core2-owner-bus-test-v1"']
objects=[]
for source in sources:
    obj=out/(Path(source).stem+'.o')
    subprocess.run(['gcc-12','-std=c99',*flags,'-c',source,'-o',str(obj)],check=True)
    objects.append(str(obj))
binary=out/'test.host'
subprocess.run(['g++-12','-std=c++20',*flags,*cxx,*objects,
    str(ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'),'-o',str(binary)],check=True)
result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=20)
(out/'host.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'CORE2_OWNER_BUS_PASS' in result.stdout,result.stdout+result.stderr
inputs=[*sources,*cxx,'tools/fixtures/full_owner_ipc.c','tools/test_xnow_full.c',
        'tools/fixtures/core2_link.cpp','tools/fixtures/core2_link/esp_now.h',
        'tools/fixtures/core2_link/esp_random.h','tools/fixtures/core2_owner_bus.h',
        'runtime/apps/wireless-remote/core2/src/link_transport.h','tools/test_core2_owner_bus.py']
inputs+=['runtime/platform/espnow/'+name+'.h' for name in
         ('xnow_owner_runtime','xnow_owner_transport','xnow_owner_link','xnow_link',
          'xnow_link_counter','xnow_security','xnow_endpoint','xnow_ccmp')]
report=dict(passed=True,real_owner_pipes_and_ccmp=True,real_core2_link_adapter=True,
    host_sanitizers=True,radio_and_native_peer_api_modeled=True,device_accessed=False,
    covers=['both endpoint restarts','app SEND held until encrypted peer confirmation',
            'PN1 accepted only under fresh link key','actual encrypted bidirectional data',
            'quiet session has no heartbeat','Off waits for producer and actual TX completion'],
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix())))
