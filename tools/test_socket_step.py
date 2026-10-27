"""Local Unix socketpair only: no DNS, IP interface or remote connection."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/socket-step-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/socket_step.c','tools/test_socket_step.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
trace=run.stderr.lower()
assert 'socketpair(' in trace and not any(call in trace for call in ('connect(','bind(','listen(','accept('))
report={'all_bounded_checks_passed':True,'physical_device_access':False,'transport':'AF_UNIX socketpair within local process','platforms':['host','ARM/QEMU original libc'],'checks':['empty poll timeout','write/read bytes','pre-set cancellation writes no bytes','invalid fd/length/timeout','peer shutdown EOF','peer closed write fails without SIGPIPE termination'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'limits':['No TCP/DNS/Wi-Fi/TLS integration or external server.','Per-step wait only, aggregate deadline and retry scheduling not implemented.','Partial readiness/EINTR error injection and saturation tests remain.','Not linked into store candidate or run on device.']}
(ROOT/'sources/native-socket-step-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Socket steps passed on host and original-libc ARM with local socketpair.')
