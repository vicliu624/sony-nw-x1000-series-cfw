"""HTTP framing/body integration on synthetic messages, no sockets or files."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/http-response-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/http_response.c','runtime/store/download_stream.c','runtime/native/sha256.c','tools/test_http_response.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'message_scenarios':17,'fragmentation':'Each message across every fixed fragment size from 1 through length+1','platforms':['host','ARM/QEMU original libc'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Restricted 200 GET response profile, no chunk extensions, redirects, compression or interim responses.','Memory sink only; no HTTP request, TLS/socket/timeout/disk commit.','Protocol implementation not claimed generally RFC-conformant or security-qualified.']}
(ROOT/'sources/native-http-response-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('HTTP response framing/body checks passed on host and ARM/QEMU.')
