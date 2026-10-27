"""Stock-libc ARM TLS fixture pair, memory transport only, no server connections."""
from pathlib import Path
import subprocess,sys,hashlib,json,datetime,tempfile,os,re
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/probe_external_tls.py')],cwd=ROOT,check=True)
runtime=ROOT/'work/external-tls-probe';source=runtime/'bearssl-0.6';work=ROOT/'work/external-tls-handshake';work.mkdir(exist_ok=True)
sample=(source/'samples/client_basic.c').read_text();start=sample.index('static const unsigned char TA0_DN');end=sample.index('#define TAs_NUM')
end=sample.index('\n',end)
(work/'fixture_ta.h').write_text(sample[:sample.index('#include')]+sample[start:end]+'\n')
def days(year):return (datetime.date(year,10,24)-datetime.date(1,1,1)).days+366
(work/'fixture_time.h').write_text(f'#define FIXTURE_VALID_DAYS {days(2026)}u\n#define FIXTURE_EXPIRED_DAYS {days(2040)}u\n')
sources=['tools/test_external_tls_handshake.c','runtime/store/stock_tls_compat.c','runtime/store/http_response.c','runtime/store/download_stream.c','runtime/native/sha256.c','tools/stock_test_start.c','tools/store_link_start.S']
command=['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-I'+str(source/'inc'),'-I'+str(source/'samples'),'-I'+str(work),*sources,str(runtime/'arm-build/libbearssl.a'),str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'test.arm')]
subprocess.run(command,cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=45)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
assert not any(call in run.stderr.lower() for call in ('connect(','sendto(','sendmsg(','/dev/urandom')),run.stderr
platform_sources=['runtime/store/tls_platform.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
platform_command=[command[0],'-DHB_TLS_PLATFORM_INPUTS','-DHB_STORE_SONY_LIBC',*platform_sources,*command[1:]];platform_command[-1]=str(work/'platform-inputs.arm')
subprocess.run(platform_command,cwd=ROOT,check=True)
platform_run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'platform-inputs.arm')],capture_output=True,text=True,timeout=45)
assert platform_run.returncode==0,(platform_run.returncode,platform_run.stdout,platform_run.stderr)
assert '/dev/urandom' in platform_run.stderr and not any(call in platform_run.stderr.lower() for call in ('connect(','sendto(','sendmsg('))
socket_sources=['runtime/store/socket_step.c','runtime/store/tls_socket_step.c','runtime/store/deadline.c','runtime/native/syscalls.S']
socket_command=[platform_command[0],'-DHB_TLS_SOCKETPAIR',*socket_sources,*platform_command[1:]];socket_command[-1]=str(work/'socketpair.arm')
subprocess.run(socket_command,cwd=ROOT,check=True)
socket_run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'socketpair.arm')],capture_output=True,text=True,timeout=45)
assert socket_run.returncode==0,(socket_run.returncode,socket_run.stdout,socket_run.stderr)
assert 'socketpair(' in socket_run.stderr.lower() and not any(call in socket_run.stderr.lower() for call in ('connect(','bind(','listen(','accept('))
controller_sources=['runtime/store/https_fetch.c','runtime/store/https_url.c','runtime/store/download_file.c','tools/download_file_faults.c']
controller_command=[socket_command[0],'-DHB_HTTPS_CONTROLLER','-Wl,--wrap=write,--wrap=fsync,--wrap=close',*controller_sources,*socket_command[1:]];controller_command[-1]=str(work/'controller.arm')
subprocess.run(controller_command,cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='controller-cache-',dir=work) as cache:
 controller_run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'controller.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_HTTP_CACHE=cache))
 assert controller_run.returncode==0,(controller_run.returncode,controller_run.stdout,controller_run.stderr)
 assert {p.name for p in Path(cache).iterdir()}=={'.fetch-file-sync','.fetch-dir-sync','.fetch-close-error'}
 assert all(p.read_bytes()==b'abc' for p in Path(cache).iterdir())
 assert not any(call in controller_run.stderr.lower() for call in ('connect(','bind(','listen(','accept('))
connection_sources=['runtime/store/connect_step.c']
connection_command=[controller_command[0],'-DHB_TLS_LOCAL_CONNECT','-Wl,--wrap=connect',*connection_sources,*controller_command[1:]];connection_command[-1]=str(work/'connection-controller.arm')
subprocess.run(connection_command,cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='connection-cache-',dir=work) as cache:
 connection_run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'connection-controller.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_HTTP_CACHE=cache))
 assert connection_run.returncode==0,(connection_run.returncode,connection_run.stdout,connection_run.stderr)
 assert {p.name for p in Path(cache).iterdir()}=={'.fetch-file-sync','.fetch-dir-sync','.fetch-close-error'}
 assert all(p.read_bytes()==b'abc' for p in Path(cache).iterdir())
 connection_families=re.findall(r'\bsocket\(([^,\n]+)',connection_run.stderr.lower())
 assert connection_families and all('_unix' in f or '_local' in f for f in connection_families)
tcp_command=[connection_command[0],'-DHB_TLS_LOOPBACK_CONNECT',*[arg for arg in connection_command[1:] if arg!='-Wl,--wrap=connect']];tcp_command[-1]=str(work/'loopback-controller.arm')
subprocess.run(tcp_command,cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='loopback-cache-',dir=work) as cache:
 tcp_run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'loopback-controller.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_HTTP_CACHE=cache))
 assert tcp_run.returncode==0,(tcp_run.returncode,tcp_run.stdout,tcp_run.stderr)
 assert {p.name for p in Path(cache).iterdir()}=={'.fetch-file-sync','.fetch-dir-sync','.fetch-close-error'}
 assert all(p.read_bytes()==b'abc' for p in Path(cache).iterdir())
 tcp_families=re.findall(r'\bsocket\(([^,\n]+)',tcp_run.stderr.lower());assert tcp_families and all(f.strip() in ('pf_inet','af_inet') for f in tcp_families)
 tcp_operations=[line for line in tcp_run.stderr.splitlines() if re.search(r'\b(?:bind|connect)\(',line,re.I)]
 assert tcp_operations and all('127.0.0.1' in line for line in tcp_operations),tcp_operations
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'cases':['TLS1.2 trusted localhost GET/Content-Length response','wrong hostname rejected with X509_BAD_SERVER_NAME','zero trust anchors rejected with X509_NOT_TRUSTED','2040 fixture time rejected with X509_EXPIRED','authenticated HTTP hash mismatch rejected','authenticated HTTP length mismatch rejected','authenticated HTTP truncation rejected','TLS1.2 chunked HTTP body verified'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'fixture_archive_sha256':'6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14','trace':run.stderr,'limits':['Both endpoints BearSSL 0.6, in-memory transport with 137-byte fragments.','Public sample keys/certificates, fixed entropy and fixture times: never production configuration.','Baseline uses fixture clock/entropy; no Wi-Fi, sockets, remote server or interoperability qualification.','Not shipped in store/system or used to connect a device.']}
report['host_OS_entropy_clock_variant']={'passed':True,'runtime_output':platform_run.stdout.splitlines(),'trace':platform_run.stderr,'limits':['Original libc translates to host urandom/time, not player entropy or RTC.','Sample certificates/keys remain test fixtures; expiry negative case still uses explicit fixture date.','No network sockets, remote HTTP endpoint or device TLS qualification.']}
report['platform_source_hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in platform_sources}
report['local_socketpair_variant']={'passed':True,'runtime_output':socket_run.stdout.splitlines(),'trace':socket_run.stderr,'raw_EOF_distinguished_from_TLS_close':True,'orderly_close_notify_both_engines_closed':True,'shared_deadline_end_unchanged_on_progress':True,'stalled_peer_deadline_expired':True,'pre_set_cancel_checked':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in socket_sources},'limits':['Local AF_UNIX only; no remote TCP/DNS/Wi-Fi or device.','Deadline checks cover record steps, not all CPU/file work; no remote or device qualification.']}
report['https_file_controller_variant']={'passed':True,'runtime_output':controller_run.stdout.splitlines(),'trace':controller_run.stderr,'scenarios':17,'negative_controller_cases':['pre-set cancellation','expired deadline before I/O','stalled handshake deadline','raw EOF after request','cancel after body before READY','invalid deadline state'],'request_injection_and_hostname_mismatch_rejected':True,'verified_cache_read_back':True,'normal_owned_cache_files_discarded':True,'review_cache_retained_and_checked':2,'explicit_recheck_ready_without_reopening_failed_transfer':1,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in controller_sources},'limits':['Local Unix socket and sample TLS trust only, not remote downloader.','Connected socket/TLS configuration/deadline/cache supplied by caller.','No redirects, DNS, connection setup or package publication.']}
report['local_connection_controller_variant']={'passed':True,'runtime_output':connection_run.stdout.splitlines(),'trace':connection_run.stderr,'scenarios':17,'socket_families':connection_families,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in connection_sources},'limits':['AF_UNIX abstract listener only; no IP/DNS/Wi-Fi or remote endpoint.','Wrapper forces EINPROGRESS after real successful local connect, not real TCP in-progress timing.','Same fixture deadline starts before local connection; not yet a production task owning connection and TLS config.']}
report['loopback_tcp_controller_variant']={'passed':True,'runtime_output':tcp_run.stdout.splitlines(),'trace':tcp_run.stderr,'scenarios':17,'socket_families':tcp_families,'loopback_operations':tcp_operations,'connect_result_not_wrapped':True,'limits':['Only host127.0.0.1, sample localhost certificate and ephemeral local listener.','No DNS, remote publisher, device network or Wi-Fi.','Connection/TLS/cache scheduling still driven by test caller, not store UI.']}
(ROOT/'sources/native-external-tls-handshake.json').write_text(json.dumps(report,indent=2)+'\n')
print(run.stdout.strip())
