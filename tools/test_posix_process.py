"""Build/test the optional POSIX process backend with pinned stock ARM libc."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/posix-process-review';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
files=['runtime/native/linux_process_posix.c','runtime/native/linux_process.h','tools/fixtures/posix_process.c','runtime/store/start.c','runtime/store/start.S']
artifact=work/'test.arm'
command=['arm-linux-gnueabi-gcc','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',files[0],files[2],files[3],files[4],str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)]
subprocess.run(command,cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact)],cwd=ROOT,check=True,timeout=15)
tracked=[ROOT/f for f in files]+[Path(__file__),lib/'libc.so.6',lib/'ld-linux.so.3']
report={'passed':True,'scope':'actual stock-libc ARM process calls under QEMU; not device qualification or full launcher integration','checks':['chdir ENOENT','execve ENOENT','fork and exit23','waitpid status and ECHILD','inherited SIG_IGN reset to SIG_DFL and child SIGTERM'],'artifact':str(artifact.relative_to(ROOT)),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'firmware_created':False,'hardware_tested':False}
(ROOT/'sources/native-posix-process-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

