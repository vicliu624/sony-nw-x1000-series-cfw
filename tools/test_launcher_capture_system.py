"""Exact supervisor under generic ARM Linux; RAM user volume and mount-list fixture."""
import argparse,json,subprocess,time
from app_registry import ROOT
from review_managed_remote_profile import receipt,artifact,digest
from player_arm_guest import stock_libraries,run_guest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',required=True);args=p.parse_args()
rp,build=receipt(args.review);binary=ROOT/build['artifact'];artifact(binary,build['sha256'],build['bytes'])
seed=rp.parent/'launcher-capture.bin';assert digest(seed)==build['seed_sha256']
out=ROOT/'work/launcher-capture-system'/str(time.time_ns());out.mkdir(parents=True)
mounts=out/'mounts';mounts.write_text('rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n')
libs=stock_libraries();init=out/'init.arm'
sources=['tools/fixtures/launcher_capture_init.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'capture':binary,'seed':seed,'fixture-child':init,'proc/mounts':mounts,'contents/.fixture':seed},libs,['LAUNCHER_CAPTURE_SYSTEM_PASS'])
report.update(source_hashes={s:digest(ROOT/s) for s in sources+['tools/test_launcher_capture_system.py']},limits=['Generic kernel and RAM filesystem, synthetic mount listing; not Sony/VFAT or original GUI qualification.','Tests exact C supervisor, real stock-libc process/file calls, successful child trace and exit, missing exec, symlink and nonce rejection.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
