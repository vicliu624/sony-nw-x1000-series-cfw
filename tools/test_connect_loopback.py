"""Actual nonblocking TCP to numeric127.0.0.1 only; no DNS/external server."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile,re
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/loopback-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/connect_step.c','runtime/store/socket_step.c','runtime/store/deadline.c','tools/test_connect_loopback.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DHB_CONNECT_HOST_CLOCK',*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
host=subprocess.run([str(work/'host')],capture_output=True,text=True,timeout=15);assert host.returncode==0,(host.returncode,host.stderr)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/native/syscalls.S','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect)\(',line,re.I)]
assert operations and all('127.0.0.1' in line for line in operations),operations
report={'all_bounded_checks_passed':True,'physical_device_access':False,'host_output':host.stdout.splitlines(),'ARM_output':run.stdout.splitlines(),'trace':run.stderr,'loopback_operations':operations,'native_pending_observed':'native-in-progress' in run.stdout,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Only numeric127.0.0.1 on host kernel/QEMU; no DNS/external network or player Wi-Fi.','No wrapper forces connect result; pending cancel path conditional on native result.','No IPv6 or failure injection beyond closing local listener for refusal.','Not yet integrated with TLS/file controller or store candidate.']}
(ROOT/'sources/native-connect-loopback-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(host.stdout.strip());print(run.stdout.strip())
