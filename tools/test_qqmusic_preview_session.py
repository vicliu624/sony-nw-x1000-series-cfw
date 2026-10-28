"""Preview session safety contract on host sanitizers and stock-libc ARM."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-session';w.mkdir(exist_ok=True)
core=['runtime/apps/qqmusic/qqmusic_preview_session.c','tools/fixtures/qqmusic_preview_session.c']
flags=['-std=c99','-Wall','-Wextra','-Werror'];host=w/'session.sanitized';arm=w/'session.arm';lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host)],check=True,timeout=10)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,check=True,timeout=10)
assert not any(x in result.stderr for x in (b'/dev/sound',b'/contents/',b'socket('))
report={'passed':True,'host_asan_ubsan':True,'stock_arm_libc':True,'sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in core},'checks':['no default ready adapter','no configure before exclusive acquire','byte partial-write/backpressure without drops','unmute only after accepted PCM and verified state','stop receipt generation/producer/reset/close required','pending stop blocks restore and new session','restore callback success with wrong readback refused','stop error/timeout retains owner guard in REVIEW','partial configure errors restore after confirmed stop','clock rollback still drives stop cleanup','internal mute refuses configure','failed outcome cannot turn into later poll success'],'physical_device_accessed':False,'limits':['Owner operations are a stateful model, not a native ownership adapter.','Coordinator is not wired into device UI or package until platform evidence closes.']}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
