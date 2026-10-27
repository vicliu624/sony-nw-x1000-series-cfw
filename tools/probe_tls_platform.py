"""Real original-libc I/O in QEMU against host OS entropy/time, not a player."""
from pathlib import Path
import hashlib,json,gzip,io,tarfile,subprocess,time
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/tls-platform-probe';work.mkdir(exist_ok=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
sources=['runtime/store/tls_platform.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/probe_tls_platform.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'probe.arm')],cwd=ROOT,check=True)
assert 0<time.time()<2147483647
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'probe.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
assert '/dev/urandom' in run.stderr and not any(call in run.stderr.lower() for call in ('connect(','sendto(','sendmsg('))
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'limits':['Real Sony libc calls translated by QEMU to host Linux urandom/time.','No device entropy/RTC or early-boot readiness qualification.','Seed contents and digests are neither printed nor stored.','Not yet bound to a production TLS connection or store candidate.']}
(ROOT/'sources/native-tls-platform-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(run.stdout.strip())
