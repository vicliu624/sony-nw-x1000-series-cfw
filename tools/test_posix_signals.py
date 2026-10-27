"""Actual repeated libc signal handling and interrupted read under ARM QEMU."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/posix-signal-review';work.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
files=['runtime/native/linux_signals_posix.c','tools/fixtures/posix_signals.c','runtime/store/start.c','runtime/store/start.S'];artifact=work/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*files,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact)],cwd=ROOT,capture_output=True,text=True,timeout=10);assert run.returncode==0,(run.returncode,run.stderr)
assert run.stderr.lower().count('sigreturn(')>=5
tracked=[ROOT/f for f in files]+[Path(__file__),ROOT/'runtime/native/linux_signals.h',lib/'libc.so.6',lib/'ld-linux.so.3']
report={'passed':True,'artifact':str(artifact.relative_to(ROOT)),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'checks':['three SIGTERM handlers persist','SIGINT handler','blocking pipe read interrupted with EINTR','child reaped'],'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False}
(ROOT/'sources/native-posix-signal-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock-libc signals: repeated delivery, return and non-restarting read passed.')
