"""Per-plan binary/empty downloads through owned tasks, local fixtures only."""
from pathlib import Path
import runpy,subprocess,hashlib,json,tempfile,os,re
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
task=runpy.run_path(str(ROOT/'tools/test_download_task.py'))
work=ROOT/'work/package-download-task-tests';work.mkdir(exist_ok=True)
files=metadata['files'];paths=[p for p in sorted(files) if p!='app.ini']
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in (data or b'\0'))+'};\n'
header=array('PLAN_MF',metadata['manifest'])+array('PLAN_IX',metadata['index'])
for i,path in enumerate(paths):header+=array('PLAN_BODY_'+str(i),files[path])
header+='static const unsigned char *PLAN_BODIES[]={'+','.join('PLAN_BODY_'+str(i) for i in range(len(paths)))+'};\n'
header+='static const unsigned PLAN_SIZES[]={'+','.join(str(len(files[p])) for p in paths)+'};\n'
header+='static const char *PLAN_PATHS[]={'+','.join(json.dumps(p) for p in paths)+'};\n'
(work/'package_task_fixture.h').write_text(header)
runtime=task['runtime'];crypto=task['crypto'];tls=task['tls'];old_work=task['work'];sources=task['sources']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(work),'-I'+str(old_work),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='package-cache-',dir=work) as cache:
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=30,env=dict(os.environ,HB_TASK_CACHE=cache))
 assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-8000:]);assert not list(Path(cache).iterdir())
families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)];assert operations and all('127.0.0.1' in line for line in operations)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'files':[{'path':p,'bytes':len(files[p]),'sha256':hashlib.sha256(files[p]).hexdigest()} for p in paths],'owned_workspace_reused':True,'binary_and_empty_ready_files_read_back':True,'cache_empty_after_explicit_discard':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'fixture_sha256':hashlib.sha256(header.encode()).hexdigest(),'trace':run.stderr,'limits':['Only explicit local DNS/TCP with sample localhost TLS root/key; no remote/device.','Synthetic ARM ELF header bytes are downloaded, never executed.','Each file discarded after inspection, no assembled package directory or install/activation.','app.ini/index provided inline, not bootstrapped from a remote catalog.']}
(ROOT/'sources/native-package-download-task-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip())
