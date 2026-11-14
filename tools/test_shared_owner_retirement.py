"""Run the actual Root stop wrapper with the real full controller and modeled native effects."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT
from player_arm_guest import stock_libraries

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expect-skipped-cleanup',action='store_true',help='Record the old premature-release defect')
options=parser.parse_args()
out=ROOT/'work/shared-owner-retirement'/str(time.time_ns());out.mkdir(parents=True)
owner=ROOT/'runtime/apps/wireless-remote/rf_owner.c'
text=owner.read_text()
def function(name):
    start=text.index('static int '+name+'(')
    first=text.index('{',start);depth=1;end=first+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
fixture=ROOT/'tools/fixtures/shared_owner_retirement.c'
generated=out/'actual-owner-retirement.c'
generated.write_text(fixture.read_text()
    .replace('/* ACTUAL_RESTORE_SHARED_SLEEP */',function('restore_shared_sleep'))
    .replace('/* ACTUAL_REMOTE_CONTROLLER_STEP */',function('remote_controller_step')))
sources=[str(generated),'tools/fixtures/xnow_control_platform.c',
    'runtime/platform/espnow/xnow_full_control.c','runtime/platform/espnow/xnow_session.c',
    'runtime/platform/espnow/xnow_manager.c','runtime/apps/wireless-remote/radio_stop.c',
    'runtime/platform/wireless/radio_release.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-I',str(ROOT)]
if options.expect_skipped_cleanup:flags+=['-DEXPECT_SKIPPED_CLEANUP']
binary=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(binary)],check=True)
result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
(out/'host.log').write_text(result.stdout+result.stderr)
marker='BASELINE_SHARED_RELEASE_SKIPPED_CLEANUP' if options.expect_skipped_cleanup else 'SHARED_OWNER_RETIREMENT_PASS'
assert not result.returncode and marker in result.stdout,result.stdout+result.stderr
libraries=stock_libraries();arm=out/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie',
    '-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,
    'runtime/store/start.c','runtime/store/start.S',str(libraries['libc.so.6']),
    str(libraries['ld-linux.so.3']),'-lgcc','-o',str(arm)],check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(libraries['ld-linux.so.3']),
    '--library-path',str(libraries['libc.so.6'].parent),str(arm)],capture_output=True,text=True,timeout=15)
(out/'arm.log').write_text(result.stdout+result.stderr)
assert not result.returncode and marker in result.stdout,result.stdout+result.stderr
inputs=[owner,fixture,Path(__file__).resolve(),ROOT/'tools/test_xnow_full_control.c',
    ROOT/'runtime/platform/espnow/xnow_full_control.h',ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S']
inputs += [ROOT/path for path in sources[1:]]
report=dict(passed=True,baseline=options.expect_skipped_cleanup,actual_root_stop_wrapper=True,
    actual_full_controller=True,host_sanitizers=True,original_libc_arm926=True,
    native_driver_and_endpoint_drain_modeled=True,device_accessed=False,
    covers=['associated and unassociated native Wi-Fi','manual Off and channel-change stop',
        'delayed endpoint drain','membership before sleep before manager release',
        'cleanup failure retains lease; no false DONE',
        'pre-existing awake radio','already sleeping radio','association during cleanup'],
    source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,baseline=options.expect_skipped_cleanup,
    report=(out/'report.json').relative_to(ROOT).as_posix())))
