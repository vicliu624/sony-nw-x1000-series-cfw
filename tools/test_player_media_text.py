"""Text conversion under host sanitizers and original-libc ARM."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-media-text';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/media_text.c','tools/fixtures/player_media_text.c'];flags=['-std=c99','-Wall','-Wextra','-Werror'];host=work/'host';arm=work/'text.arm';lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['gcc-12',*flags,'-O1','-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True);host_run=subprocess.run([str(host)],capture_output=True,text=True,timeout=10,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10,check=True)
(work/'host.log').write_text(host_run.stdout+host_run.stderr);(work/'arm.log').write_text(run.stdout+run.stderr)
report=dict(passed=True,host_sanitizers=True,original_libc_arm=True,device_accessed=False,stdout=run.stdout,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/media_text.h','tools/test_player_media_text.py']})
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
