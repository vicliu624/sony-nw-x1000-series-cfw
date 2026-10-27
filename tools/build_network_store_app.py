"""Build network external-store candidate only; never run native mode or flash."""
from pathlib import Path
import argparse,gzip,hashlib,io,json,subprocess,tarfile,sys
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-output');parser.add_argument('--libc-device-io',action='store_true');parser.add_argument('--libc-runtime',action='store_true',help='Use stock libc/librt for device, clock and wait operations.');options=parser.parse_args()
if options.libc_runtime:options.libc_device_io=True
work=(ROOT/options.review_output).resolve() if options.review_output else ROOT/'work/network-store-app-candidate'
assert work.is_relative_to(ROOT/'work') and work!=ROOT/'work'
for prefix in ('integration-','product-review-','network-external-'):
    assert not any(part.startswith(prefix) for part in work.relative_to(ROOT/'work').parts),'Do not build inside a preserved candidate'
work.mkdir(parents=True,exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();candidate=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',candidate/'manifest.json']+[candidate/f['path'] for f in json.loads((candidate/'manifest.json').read_text())['files']]
def snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=snapshot()
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','tools/test_network_store_main.c','-o',str(work/'entry-test')],cwd=ROOT,check=True)
entry_test=subprocess.run([str(work/'entry-test')],capture_output=True,text=True,timeout=10)
assert entry_test.returncode==0,(entry_test.returncode,entry_test.stderr)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run([sys.executable,str(ROOT/'tools/probe_external_tls.py')],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'tools/probe_stock_resolver.py')],cwd=ROOT,check=True)
crypto=ROOT/'work/external-tls-probe/bearssl-0.6';runtime=ROOT/'work/stock-resolver-probe'
modules=['repository', 'remote_store', 'metadata_cache', 'metadata_fetch', 'remote_catalog', 'remote_list', 'download_intent', 'download_record', 'payload_cache_cleanup', 'partial_cleanup', 'download_recovery', 'package_job', 'package_resume', 'package_assemble', 'download_task', 'download_plan', 'resolver', 'connect_step', 'https_url', 'https_fetch', 'tls_socket_step', 'socket_step', 'deadline', 'tls_platform', 'download_file', 'download_stream', 'http_response', 'install_posix', 'transaction', 'stage_posix', 'cleanup_posix', 'pending_plan', 'cleanup_plan', 'bundle_posix', 'inventory', 'package', 'stock_fs_bridge', 'stock_stat64', 'stock_tls_compat', 'canvas', 'job_ui', 'termination', 'network_app', 'platform_native', 'network_main', 'start']
sources=['runtime/store/'+name+'.c' for name in modules]+['runtime/store/start.S','runtime/native/frontend.c','runtime/native/sha256.c','runtime/native/linux_devices.c','runtime/native/syscalls.S']
if options.libc_device_io:
 sources.append('runtime/native/linux_device_io_posix.c')
if options.libc_runtime:sources.remove('runtime/native/syscalls.S')
folder=work/'HOMEBREW/apps/store';folder.mkdir(parents=True,exist_ok=True);out=folder/'app'
flags=['-DHB_BUILD_VERSION="'+version+'"','-DHB_STORE_SONY_LIBC','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
if options.libc_device_io:flags += ['-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE']
if options.libc_runtime:flags += ['-DHB_STORE_LIBC_CLOCK']
# Compile to stable object names. Direct multi-source gcc linking records
# random temporary assembly-object names in ELF .strtab.
objects=[];object_root=work/'objects';object_root.mkdir(exist_ok=True)
compile_flags=[flag for flag in flags if not flag.startswith('-Wl,')]
for index,source in enumerate(sources):
 obj=object_root/(f'{index:02d}-'+Path(source).stem+'.o')
 subprocess.run(['arm-linux-gnueabi-gcc',*compile_flags,'-I'+str(crypto/'inc'),'-I'+str(runtime),'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Wl,-rpath-link,'+str(runtime),*objects,str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),*([str(runtime/'librt.so.1')] if options.libc_runtime else []),str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(out)],cwd=ROOT,check=True)
binary=out.read_bytes();elf=ELFFile(io.BytesIO(binary));needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
assert sorted(needed)==sorted(['libc.so.6','libcares.so.2']+(['librt.so.1'] if options.libc_runtime else []))
if options.libc_runtime:
 symbols=subprocess.check_output(['arm-linux-gnueabi-nm',str(out)],text=True);assert 'x1000_oabi_call' not in symbols and 'x1000_rt_sigreturn' not in symbols
 assert any(s.name=='usleep' for s in elf.get_section_by_name('.dynsym').iter_symbols())
checks=[]
for args,code,expected in [(['--help'],0,'X1000 network app store'),(['--version'],0,version),([],64,'')]:
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(runtime)+':'+str(work),str(out),*args],capture_output=True,text=True,timeout=15)
 assert run.returncode==code and (not expected or expected in run.stdout),(args,run.returncode,run.stdout,run.stderr)
 assert '/dev/fb/' not in run.stderr and '/dev/icx_touch_screen' not in run.stderr
 checks.append({'args':args,'exit':run.returncode,'device_paths_not_accessed':True})
manifest=f'api=1\nid=store\nname=Network Store\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(binary)}\nsha256={hashlib.sha256(binary).hexdigest()}\n'
(folder/'app.ini').write_text(manifest)
assert before==snapshot()
report={'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'version':version,'artifact':str(out.relative_to(ROOT)),'bytes':len(binary),'sha256':hashlib.sha256(binary).hexdigest(),'needed':needed,'read_only_QEMU_entry_checks':checks,'candidate_unchanged':True,'physical_device_access':False,'native_ready':False,'firmware_package_created':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Native mode is built but never executed by this tool.','External network-store prototype requiring user repository configuration, not a release or hardware qualification.','Runtime code linked; only non-native entry checks executed here. No self-update or USB qualification.']}
report['source_hashes'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/build_network_store_app.py','VERSION','runtime/native/linux_devices.h','runtime/native/linux_device_io.h')})
report['runtime_backend']='stock-libc' if options.libc_runtime else 'mixed'
if options.libc_runtime:report['source_hashes']['work/stock-resolver-probe/librt.so.1']=hashlib.sha256((runtime/'librt.so.1').read_bytes()).hexdigest()
report['device_io_backend']='stock-libc' if options.libc_device_io else 'freestanding'
for dependency in [*(ROOT/'runtime/store').glob('*.h'),ROOT/'runtime/native/frontend.h',ROOT/'runtime/native/sha256.h',ROOT/'runtime/native/font.inc',ROOT/'work/external-tls-probe/arm-build/libbearssl.a',runtime/'libcares.so.2',work/'libc-2.3.3.so',work/'ld-2.3.3.so']:
 report['source_hashes'][str(dependency.relative_to(ROOT))]=hashlib.sha256(dependency.read_bytes()).hexdigest()
report['review_only']=bool(options.review_output)
(work/'build.json' if options.review_output else ROOT/'sources/native-network-store-app-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('version','artifact','bytes','sha256','candidate_unchanged','native_ready')},indent=2))

