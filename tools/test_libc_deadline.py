"""Stock librt monotonic-clock ABI; ordinary ARM/QEMU deadline operations."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/libc-deadline-review';work.mkdir(exist_ok=True);runtime=ROOT/'work/stock-resolver-probe';resolver=json.loads((ROOT/'sources/native-stock-resolver-probe.json').read_text())
for name in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3'):assert hashlib.sha256((runtime/name).read_bytes()).hexdigest()==resolver['libraries'][name]['sha256']
files=['runtime/store/deadline.c','tools/test_deadline.c','tools/stock_test_start.c','tools/store_link_start.S'];artifact=work/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-DHB_STORE_LIBC_CLOCK','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,-rpath-link,'+str(runtime),*files,str(runtime/'librt.so.1'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
symbols=subprocess.check_output(['arm-linux-gnueabi-nm',str(artifact)],text=True);assert 'x1000_oabi_call' not in symbols
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(artifact)],cwd=ROOT,capture_output=True,text=True,timeout=10);assert run.returncode==0,(run.returncode,run.stderr)
assert 'clock_gettime(CLOCK_MONOTONIC' in run.stderr
tracked=[ROOT/f for f in files]+[Path(__file__),ROOT/'runtime/store/deadline.h',ROOT/'sources/native-stock-resolver-probe.json',*[runtime/n for n in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]]
report={'passed':True,'artifact':str(artifact.relative_to(ROOT)),'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'clock':'original librt clock_gettime, fixed old32 timespec, CLOCK_MONOTONIC','custom_syscall_assembly_linked':False,'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False}
(ROOT/'sources/native-libc-deadline-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock librt clock: monotonic deadline/cap/zero-timeout checks passed, no custom syscall assembly.')
