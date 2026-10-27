"""Checked-memory/time conversion fixtures on host and ARM; no real clock test."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/tls-compat-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/stock_tls_compat.c','tools/test_stock_tls_compat.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin',*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')])]:
 for args,code in [([],0),(['copy-overflow'],99),(['set-overflow'],99),(['move-overflow'],99),(['poll-overflow'],99)]:
  run=subprocess.run(command+args,capture_output=True,text=True,timeout=10)
  assert run.returncode==code,(platform,args,run.returncode,run.stderr)
  rows.append({'platform':platform,'args':args,'exit':code})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Memory/time/abort functions mocked to exercise conversion and failure paths.','ARM target has 32-bit long, host may not; target fixtures cover 32-bit maximum and -1.','No real RTC/errno syscall qualification or post-2038 clock support.','No changes to system libc or store candidate.']}
(ROOT/'sources/native-stock-tls-compat-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('TLS compatibility helpers:',len(rows),'host/ARM fixture runs passed.')
