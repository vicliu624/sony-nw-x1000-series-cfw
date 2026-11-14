"""Actual RF summary writer and parent trace reader, with bounded private-pipe capture."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

out=ROOT/'work/remote-retirement-summary'/str(time.time_ns());out.mkdir(parents=True)
fixture=ROOT/'tools/fixtures/remote_retirement_summary.c'
owner=ROOT/'runtime/apps/wireless-remote/rf_owner.c'
parent=ROOT/'runtime/platform/player/remote_auto.c'
def function(path,signature):
    text=path.read_text();start=text.index(signature);first=text.index('{',start);depth=1;end=first+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
generated=out/'actual-summary.c'
generated.write_text(fixture.read_text().replace('/* ACTUAL_OWNER_REPORT */',
    function(owner,'static void owner_report_retirement(')).replace('/* ACTUAL_PARENT_READER */',
    function(parent,'void xw_player_pairing_trace_exit(')))
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT)]
host=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',str(generated),'-o',str(host)],check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=10)
(out/'host.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'REMOTE_RETIREMENT_SUMMARY_PASS' in result.stdout,result.stdout+result.stderr
libraries=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie',
    '-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',str(generated),
    'runtime/store/start.c','runtime/store/start.S',str(libraries['libc.so.6']),
    str(libraries['ld-linux.so.3']),'-lgcc','-o',str(arm)],check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libraries['ld-linux.so.3']),
    '--library-path',str(libraries['libc.so.6'].parent),str(arm)],capture_output=True,text=True,timeout=10)
(out/'arm.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'REMOTE_RETIREMENT_SUMMARY_PASS' in result.stdout,result.stdout+result.stderr
inputs=[owner,parent,fixture,Path(__file__).resolve(),ROOT/'runtime/apps/wireless-remote/supervisor_process.h',
    ROOT/'runtime/platform/espnow/xnow_owner_runtime.h',ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S']
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,actual_writer_and_reader=True,
    device_accessed=False,new_device_file_io=False,legacy_and_truncated_summary_not_invented=True,
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix())))
