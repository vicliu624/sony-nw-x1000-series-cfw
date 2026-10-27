"""Mocked entropy/clock edge cases on host and stock-libc ARM."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/tls-platform-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/tls_platform.c','tools/test_tls_platform.c']
wrap='-Wl,--wrap=open,--wrap=open64,--wrap=read,--wrap=close,--wrap=fstat,--wrap=fstat64,--wrap=__fstat64_time64,--wrap=hb_target_fstat,--wrap=time'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True)
subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'tools/stock_test_start.c','tools/store_link_start.S',wrap,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['48-byte seed across short reads','open failure','non-character file refused','stat failure','EOF','read error','EINTR retry','mid-read stop wipes output','close failure wipes output','pre-set cancellation','time error leaves output unchanged','Unix epoch/year-zero conversion','signed32 maximum conversion'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Open/stat/read/close/time are mocked; no real entropy or clock read in these tests.','No entropy-quality, early boot readiness, RTC or post2038 qualification.','Not connected to production TLS/store candidate.']}
(ROOT/'sources/native-tls-platform-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('TLS seed/clock edge cases passed on host and ARM/QEMU.')
