"""Cross-build pinned BearSSL compatibility fixture; no connection or adoption."""
from pathlib import Path
import hashlib,json,subprocess,tarfile,gzip,io,re
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/external-tls-probe';work.mkdir(exist_ok=True)
archive=ROOT/'work/bearssl-0.6.tar.gz'
archive_hash='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==archive_hash
with tarfile.open(archive) as tar:
 assert all(m.name=='bearssl-0.6' or m.name.startswith('bearssl-0.6/') for m in tar.getmembers())
 tar.extractall(work,filter='data')
source=work/'bearssl-0.6';build=work/'arm-build'
flags='-Os -march=armv5te -marm -mfloat-abi=soft -ffreestanding -fno-builtin -DBR_USE_URANDOM=0'
made=subprocess.run(['make','-C',str(source),'-j4','lib','CC=arm-linux-gnueabi-gcc','AR=arm-linux-gnueabi-ar','CFLAGS='+flags,'BUILD='+str(build)],capture_output=True,text=True)
assert made.returncode==0,made.stderr[-4000:]
library=build/'libbearssl.a';assert library.exists()
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
sources=['tools/probe_external_tls.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
linked=subprocess.run(['arm-linux-gnueabi-gcc',*flags.split(),'-I'+str(source/'inc'),'-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(library),str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'probe.arm')],cwd=ROOT,capture_output=True,text=True)
if linked.returncode:
 missing=sorted(set(re.findall(r"undefined reference to [`‘]([^'’]+)",linked.stderr)))
 report={'physical_device_access':False,'all_bounded_checks_passed':False,'source_url':'https://www.bearssl.org/bearssl-0.6.tar.gz','archive_sha256':archive_hash,'ARM_static_library_built':True,'stock_libc_link_passed':False,'missing_symbols':missing,'link_diagnostics':linked.stderr,'compiler_flags':flags,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['No executable/ClientHello test completed.','Not selected or included in store/device candidates.','Fixed fixture entropy and no trust anchors are test-only, never production configuration.','No checks disabled or system libc replaced to force a link.']}
 (ROOT/'sources/native-external-tls-probe.json').write_text(json.dumps(report,indent=2)+'\n')
 print('External TLS ARM library built; stock libc link missing:',', '.join(missing));raise SystemExit(2)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'probe.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
assert not any(call in run.stderr.lower() for call in ('connect(','sendto(','sendmsg(','/dev/urandom')),run.stderr
report={'all_bounded_checks_passed':True,'physical_device_access':False,'source_url':'https://www.bearssl.org/bearssl-0.6.tar.gz','archive_sha256':archive_hash,'license':'MIT (retained in ignored source tree)','compiler_flags':flags,'runtime_output':run.stdout.splitlines(),'probe_bytes':(work/'probe.arm').stat().st_size,'probe_sha256':hashlib.sha256((work/'probe.arm').read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'limits':['Compatibility evaluation only, not selected or shipped TLS implementation.','Fixed fixture entropy and zero trust anchors: never use this configuration for real traffic.','ClientHello only, no peer, handshake, certificate/hostname validation or HTTP download.','QEMU ARM926 with Sony libc, not hardware performance or entropy/clock qualification.','No system TLS/certificate changes; no vulnerability research.']}
report['stock_libc_link_passed']=True
(ROOT/'sources/native-external-tls-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(run.stdout.strip());print('External TLS fixture bytes:',report['probe_bytes'])
