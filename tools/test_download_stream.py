"""Bounded download-body streaming checks, no HTTP/socket/filesystem sink."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/download-stream-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/download_stream.c','runtime/native/sha256.c','tools/test_download_stream.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['Known abc SHA256 with split input/short writes','Extra data after verification invalidates state','Oversize rejected before sink writes','Truncation','Hash mismatch','Sink error/overreported size','Pre-set and mid-write cancellation','Failure remains terminal','128MiB per-file cap'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Memory sink, no HTTP parsing, TLS, file/disk capacity or commit operation.','Expected metadata provenance and timeout belong to future downloader.','Failed partial output must be discarded by owning file transaction.','Not added to store candidate or physical device.']}
(ROOT/'sources/native-download-stream-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Download streaming checks passed on host and ARM/QEMU.')
