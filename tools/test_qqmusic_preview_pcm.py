"""PCM normalization against a whole-signal rational reference, ARM and host."""
from pathlib import Path
import hashlib,json,resource,subprocess
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-pcm';w.mkdir(exist_ok=True)
sources=['runtime/apps/qqmusic/qqmusic_preview_pcm.c','tools/fixtures/qqmusic_preview_pcm.c'];flags=['-std=c99','-Wall','-Wextra','-Werror'];lib=ROOT/'work/arm-signal-tests/lib'
host=w/'pcm.sanitized';arm=w/'pcm.arm'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host)],check=True,timeout=10)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,check=True,timeout=15);assert b'/dev/sound' not in result.stderr
report={'passed':True,'host_asan_ubsan':True,'stock_arm_libc':True,'signal_cases_per_backend':36,'checks':['32000/44100/48000 mono/stereo to44100 stereo','chunk-boundary invariant rational interpolation','whole-second exact output sample count','one/13-frame EOF and tail handling','44100 stereo byte identity via numeric reference','unsupported format rejection','stop during output aborts finish'],'physical_device_accessed':False,'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'limits':['Preview-quality linear interpolation, not an archival resampler.','No live PCM negotiation or acoustic output tested.']}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
