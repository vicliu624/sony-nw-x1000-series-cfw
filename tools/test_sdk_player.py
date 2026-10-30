"""Offline player-core checks; no stock/device provider is substituted."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/sdk-player-core';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/client.c','tools/fixtures/sdk_player.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation'];host=work/'core.host';arm=work/'core.arm'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host)],check=True,timeout=15)
lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,check=True,timeout=15)
assert not any(s in run.stderr for s in ('/dev/','/contents/','/db/','socket('))
paths=sources+['runtime/platform/player/player.h','runtime/platform/player/provider.h','tools/test_sdk_player.py']
report=dict(passed=True,core_only=True,native_player_backend=False,physical_device_accessed=False,host_sanitizers=True,original_libc_arm=True,stdout=run.stdout,sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths})
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
