"""Local AF_UNIX listener only; no IP sockets, DNS or remote network."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile,tempfile,os,re
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/conn-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/connect_step.c','runtime/store/deadline.c','tools/test_connect_step.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DHB_CONNECT_HOST_CLOCK',*sources,'-Wl,--wrap=connect','-o',str(work/'host')],cwd=ROOT,check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=connect',*sources,'runtime/native/syscalls.S','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
rows=[];trace=''
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')])]:
 with tempfile.TemporaryDirectory(prefix='c-',dir=work) as temp:
  path=str(Path(temp)/'s');assert len(path.encode())<107
  run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_LOCAL_SOCKET=path));assert run.returncode==0,(platform,run.returncode,run.stderr)
  assert not Path(path).exists();rows.append({'platform':platform,'passed':True})
  if platform=='ARM/QEMU':trace=run.stderr
families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower());assert families and all('_unix' in f or '_local' in f for f in families),trace
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'checks':['forced in-progress return after real local connect exercises poll/SO_ERROR','transfer owned fd once and exchange bytes','pre-set cancel and zero deadline create no retained fd','EAGAIN is not misclassified as successful/in-progress','pending cancel closes fd','refused local connection closes fd'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':trace,'socket_families':families,'limits':['Local abstract AF_UNIX namespace only; IPv4/IPv6, DNS and Wi-Fi not tested.','In-progress state forced by wrapper after real successful connect; not TCP pending behavior.','No injected socket/fcntl/poll/getsockopt/close failures or live device.','Not bound to TLS downloader or store candidate.']}
(ROOT/'sources/native-connect-step-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Connection owner/pending/cancel tests passed on host and stock-libc ARM (local Unix only).')
