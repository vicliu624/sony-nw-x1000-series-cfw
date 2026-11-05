"""Exercise deferred ack ordering on host sanitizers and freestanding ARM/OABI."""
import hashlib,json,subprocess,time
from app_registry import ROOT
out=ROOT/'work/player-sleep-retirement'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/sleep_retirement.c','tools/fixtures/sleep_retirement.c']
common=['-std=c99','-Os','-Wall','-Wextra','-Werror',*sources]
host=out/'host'
subprocess.run(['gcc',*common,'-fsanitize=address,undefined','-fno-omit-frame-pointer','-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],check=True,cwd=ROOT)
arm=out/'retirement.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-DARM_FIXTURE','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-e,_start','-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm',str(arm)],check=True,cwd=ROOT)
report=dict(passed=True,host_sanitizers=True,freestanding_arm=True,cases=5,device_accessed=False,native_hook_installed=False,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/sleep_retirement.h','tools/test_sleep_retirement.py']},
 limits=['Sequencing code executes with modeled owner, validity, radio retirement, SDK stop and original acknowledgement callbacks.',
         'No native callback/callsite binding, wake/rearm, actual RF or hardware qualification.'])
(ROOT/'work/player-sleep-retirement-latest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
