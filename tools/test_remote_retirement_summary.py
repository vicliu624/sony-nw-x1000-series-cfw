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
reader=ROOT/'runtime/apps/wireless-remote/retirement_log.c'
def function(path,signature):
    text=path.read_text();start=text.index(signature);first=text.index('{',start);depth=1;end=first+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
generated=out/'actual-summary.c'
packet_start=function(owner,'static int owner_enable_packet_backend(')
generated.write_text(fixture.read_text().replace('/* ACTUAL_OWNER_REPORT */',
    function(owner,'static void owner_report_retirement(')).replace('/* ACTUAL_PARENT_READER */',
    function(parent,'void xw_player_pairing_trace_exit(')).replace('/* ACTUAL_FRM1_START */',
    packet_start.replace('owner_enable_packet_backend','owner_enable_frames',1)).replace('/* ACTUAL_BULK_START */',
    packet_start.replace('owner_enable_packet_backend','owner_enable_bulk',1)))
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT)]
host=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',str(generated),str(reader),'-o',str(host)],check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=10)
(out/'host.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'REMOTE_RETIREMENT_SUMMARY_PASS' in result.stdout,result.stdout+result.stderr
libraries=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie',
    '-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',str(generated),str(reader),
    'runtime/store/start.c','runtime/store/start.S',str(libraries['libc.so.6']),
    str(libraries['ld-linux.so.3']),'-lgcc','-o',str(arm)],check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libraries['ld-linux.so.3']),
    '--library-path',str(libraries['libc.so.6'].parent),str(arm)],capture_output=True,text=True,timeout=10)
(out/'arm.log').write_text(result.stdout+result.stderr)
assert not result.returncode and 'REMOTE_RETIREMENT_SUMMARY_PASS' in result.stdout,result.stdout+result.stderr
inputs=[owner,parent,reader,reader.with_suffix('.h'),reader.with_name('startup_result.h'),
    fixture,Path(__file__).resolve(),ROOT/'runtime/apps/wireless-remote/supervisor_process.h',
    ROOT/'runtime/platform/espnow/xnow_owner_runtime.h',ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S']
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,actual_writer_and_reader=True,
    device_accessed=False,new_device_file_io=False,legacy_and_truncated_summary_not_invented=True,
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix())))
