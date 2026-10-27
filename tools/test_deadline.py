"""Pinned original OABI monotonic clock: host edge cases and QEMU syscall."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/deadline-tests';work.mkdir(exist_ok=True)
kernel=(ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz').read_bytes();assert hashlib.sha256(kernel).hexdigest()=='286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
with tarfile.open(fileobj=io.BytesIO(kernel)) as tar:
 unistd=tar.extractfile('./include/asm-arm/unistd.h').read();clock=tar.extractfile('./include/linux/time.h').read()
 assert b'__NR_clock_gettime' in unistd and b'__NR_SYSCALL_BASE+263' in unistd and b'#define CLOCK_MONOTONIC\t  1' in clock
sources=['runtime/store/deadline.c','tools/test_deadline.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DHB_DEADLINE_MOCK',*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/native/syscalls.S','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'kernel_archive_sha256':hashlib.sha256(kernel).hexdigest(),'header_hashes':{'asm-arm/unistd.h':hashlib.sha256(unistd).hexdigest(),'linux/time.h':hashlib.sha256(clock).hexdigest()},'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/native/syscalls.S']},'checks':['deadline does not reset across calls','exact expiry','poll wait cap','clock regression','ENOSYS and malformed timespec leave output unchanged','actual OABI clock call in QEMU'],'trace':run.stderr,'limits':['QEMU uses host monotonic clock, not physical Sony clock qualification.','This primitive check does not itself qualify full transfer scheduling; integration is checked separately.']}
(ROOT/'sources/native-deadline-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Deadline edge cases and original OABI monotonic clock QEMU checks passed.')

