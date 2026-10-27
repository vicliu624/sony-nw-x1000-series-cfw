"""Initialize pinned stock curl/TLS under QEMU without performing a transfer."""
from pathlib import Path
import gzip,hashlib,io,json,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-transfer-probe';work.mkdir(exist_ok=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
libraries={}
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 def extract(name):
  if name in libraries:return
  assert '/' not in name
  candidates=[p for p in ('./lib/'+name,'./usr/lib/'+name) if p in tar.getnames()]
  assert candidates,name
  source=candidates[0];binary=tar.extractfile(source).read();elf=ELFFile(io.BytesIO(binary))
  needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
  libraries[name]={'archive_path':source,'sha256':hashlib.sha256(binary).hexdigest(),'bytes':len(binary),'needed':needed}
  (work/name).write_bytes(binary)
  for dependency in needed:extract(dependency)
 for name in ('libcurl.so.4','libssl.so.0.9.8','libcrypto.so.0.9.8','libc.so.6','ld-linux.so.3'):extract(name)
sources=['tools/probe_stock_transfer.c','tools/stock_test_start.c','tools/store_link_start.S']
command=['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(work),*sources,*[str(work/n) for n in ('libcurl.so.4','libssl.so.0.9.8','libcrypto.so.0.9.8','libc.so.6','ld-linux.so.3')],'-lgcc','-o',str(work/'probe.arm')]
subprocess.run(command,cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-linux.so.3'),'--library-path',str(work),str(work/'probe.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
assert 'libcurl/7.18.1' in run.stdout and 'OpenSSL 0.9.8i' in run.stdout and 'stock-transfer-init-ok' in run.stdout
assert 'offered version 0x0301' in run.stdout
assert not any(operation in run.stderr.lower() for operation in ('connect(','sendto(','sendmsg(')),run.stderr
report={'physical_device_access':False,'all_bounded_checks_passed':True,'runtime_output':run.stdout.splitlines(),'default_SSLv23_memory_ClientHello_version':'0x0301 (TLS1.0)','libraries':libraries,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'no_connect_or_send_observed':True,'trace':run.stderr,'limits':['Original initialization and default SSLv23 ClientHello emission into memory BIO; no peer/complete handshake or transfer.','No URL is supplied; no network endpoint compatibility or Wi-Fi established.','One method/default configuration, not exhaustive protocol or security analysis.','Does not prove current trust, successful certificate validation or TLS1.2/1.3 compatibility.','No changes to system libraries, certificate verification or device firmware.']}
(ROOT/'sources/native-stock-transfer-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(run.stdout.strip())
print('Stock transfer initialization passed without connect/send calls.')
