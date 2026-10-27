"""Stock c-ares options ABI/idle lifecycle only, no resolver request or socket."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-resolver-probe';work.mkdir(exist_ok=True)
header=ROOT/'work/cares-1_5_2-ares.h';header_hash='ed0804876d9dc6846acd30165ccc5a866cd7e6987aa5907adb53130dc3868f04'
assert hashlib.sha256(header.read_bytes()).hexdigest()==header_hash;(work/'ares.h').write_bytes(header.read_bytes())
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
libraries={}
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 names=set(tar.getnames())
 def extract(name):
  if name in libraries:return
  assert '/' not in name
  path=next(p for p in ('./lib/'+name,'./usr/lib/'+name) if p in names)
  data=tar.extractfile(path).read();elf=ELFFile(io.BytesIO(data));needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
  libraries[name]={'archive_path':path,'sha256':hashlib.sha256(data).hexdigest(),'needed':needed};(work/name).write_bytes(data)
  if name=='libcares.so.2':libraries[name]['async_exports']=sorted(s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF' and s.name in ('ares_getsock','ares_process_fd','ares_cancel','ares_gethostbyname','ares_init_options','ares_save_options','ares_destroy'))
  for dependency in needed:extract(dependency)
 for name in ('libcares.so.2','libc.so.6','ld-linux.so.3'):extract(name)
sources=['tools/probe_stock_resolver.c','runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,-rpath-link,'+str(work),'-I'+str(work),*sources,str(work/'libcares.so.2'),str(work/'libc.so.6'),str(work/'ld-linux.so.3'),'-lgcc','-o',str(work/'probe.arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-linux.so.3'),'--library-path',str(work),str(work/'probe.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
assert not any(call in run.stderr.lower() for call in ('socket(','connect(','sendto(','sendmsg(')),run.stderr
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'libraries':libraries,'header_url':'https://raw.githubusercontent.com/c-ares/c-ares/cares-1_5_2/ares.h','header_sha256':header_hash,'option_output_guard_bytes_unchanged':32,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'limits':['Explicit loopback server options roundtrip and idle lifecycle only, no query or DNS behavior.','64-byte options/servers offset28 checked for ARM; only exercised fields qualified.','Sony library may differ from upstream tag beyond tested ABI.','Not connected to store/TLS or physical Wi-Fi.']}
(ROOT/'sources/native-stock-resolver-probe.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip())
