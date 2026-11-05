"""Execute the exact static probe under generic ARM Linux; RAM storage fixtures."""
import argparse,json,subprocess,time
from app_registry import ROOT
from review_managed_remote_profile import receipt,artifact,digest
from player_arm_guest import stock_libraries,run_guest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True);args=parser.parse_args()
rp,build=receipt(args.review);binary=ROOT/build['artifact'];artifact(binary,build['sha256'],build['bytes'])
seed=rp.parent/'entry-boundary.bin';assert digest(seed)==build['seed_sha256']
out=ROOT/'work/launcher-entry-probe-system'/str(time.time_ns());out.mkdir(parents=True)
mounts=out/'fixture-mounts';mounts.write_text('rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\n')
libs=stock_libraries();init=out/'init.arm'
sources=['tools/fixtures/launcher_entry_probe_init.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'entry-probe':binary,'proc/mounts':mounts,'seed':seed,'contents/HOMEBREW/data/diagnostics/entry-boundary.bin':seed},libs,['ENTRY_PROBE_SYSTEM_PASS'])
report.update(artifact_sha256=build['sha256'],exact_probe_executed=True,device_executed=False,
 source_hashes={p:digest(ROOT/p) for p in [*sources,'tools/test_launcher_entry_probe_system.py']},
 limits=['Generic ARM kernel; mount listing and user file are RAM fixtures, not Sony/VFAT hardware.',
 'Real process entry/exit, OABI file operations and bounded marker readback execute; no display/APF application switching qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');(rp.parent/'system-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
