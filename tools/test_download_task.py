"""Owned URL/DNS/TCP/TLS/cache task against explicit local fixtures only."""
from pathlib import Path
import subprocess,sys,hashlib,json,tempfile,os,re,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/probe_external_tls.py')],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'tools/probe_stock_resolver.py')],cwd=ROOT,check=True)
tls=ROOT/'work/external-tls-probe';crypto=tls/'bearssl-0.6';runtime=ROOT/'work/stock-resolver-probe';work=ROOT/'work/download-task-tests';work.mkdir(exist_ok=True)
sample=(crypto/'samples/client_basic.c').read_text();start=sample.index('static const unsigned char TA0_DN');end=sample.index('\n',sample.index('#define TAs_NUM'))
(work/'fixture_ta.h').write_text(sample[:sample.index('#include')]+sample[start:end]+'\n')
modules=['download_task','download_plan','inventory','package','cleanup_plan','resolver','connect_step','https_url','https_fetch','tls_socket_step','socket_step','deadline','tls_platform','download_file','download_stream','http_response','stock_fs_bridge','stock_stat64','stock_tls_compat']
sources=[('runtime/apps/store/' if name in ('network_app','network_main') else 'runtime/store/')+name+'.c' for name in modules]+['runtime/native/sha256.c','runtime/native/syscalls.S','tools/test_download_task.c','tools/download_file_faults.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(work),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='task-cache-',dir=work) as cache:
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_TASK_CACHE=cache))
 assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-10000:])
 assert not list(Path(cache).iterdir())
families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
assert operations and all('127.0.0.1' in line or '127.0.0.2' in line for line in operations),operations
elf=ELFFile(io.BytesIO((work/'test.arm').read_bytes()));workspace=next(s['st_size'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name=='task')
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'scenarios':9,'cases':['full DNS/TCP/TLS/HTTP/READY','NXDOMAIN','silent DNS deadline','wrong trust root','cancel pending DNS','HTTP hash mismatch','fsync error plus explicit cache recheck','pre-cancel before task I/O','first address refusal then second address success'],'workspace_reused_after_discard':True,'workspace_bytes_excluding_stack_library_heap':workspace,'owned_crypto_buffers_zero_checked':True,'cache_empty_after_explicit_discard':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'loopback_operations':operations,'limits':['Only local DNS/TCP endpoints127.0.0.1 and refused127.0.0.2; no system/default/external DNS or network.','Sample trust roots/key, host entropy/clock, original c-ares/libc under QEMU; no device/Wi-Fi qualification.','No redirects, package publication, UI integration or runtime memory budget qualification.','Fault wrappers only in test; context reuse requires explicit discard and no owned resources.']}
report['input_report_hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('sources/native-external-tls-probe.json','sources/native-stock-resolver-probe.json')}
(ROOT/'sources/native-download-task-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip());print('Task workspace bytes:',workspace)
