"""Pinned c-ares DNS against a local numeric127.0.0.1 UDP fixture only."""
from pathlib import Path
import subprocess,sys,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/probe_stock_resolver.py')],cwd=ROOT,check=True)
runtime=ROOT/'work/stock-resolver-probe';work=ROOT/'work/stock-resolver-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/resolver.c','runtime/store/https_url.c','runtime/store/deadline.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/native/syscalls.S','tools/test_stock_resolver.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,-rpath-link,'+str(runtime),'-I'+str(runtime),*sources,str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=30)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-8000:])
families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
assert operations and all('127.0.0.1' in line for line in operations),operations
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'scenarios':8,'cases':['one IPv4 reply','NXDOMAIN','silent server deadline','cancel outstanding query','zero deadline before query','nine-address result rejected','invalid hostname before query','two IPv4 replies'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'loopback_operations':operations,'limits':['Only explicit host127.0.0.1 DNS fixture, no system/default/external DNS or player.','IPv4 only, max8 outputs; no IPv6, CNAME/TCP fallback or broad protocol qualification.','No memory/descriptor fault injection; original library manages its sockets.','Not connected to production download task or store candidate.']}
(ROOT/'sources/native-stock-resolver-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip())
