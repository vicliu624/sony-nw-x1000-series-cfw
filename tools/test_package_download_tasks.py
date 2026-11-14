"""Per-plan binary/empty downloads through owned tasks, local fixtures only."""
from pathlib import Path
import test_download_plan as plan
import subprocess,hashlib,json,tempfile,os,re
from test_download_task import CRYPTO, RESOLVER, TASK_SOURCES, TLS, prepare_task_fixture
ROOT=Path(__file__).resolve().parents[1]


def prepare_package_fixture(work):
    lib = prepare_task_fixture(work)
    metadata = {'index': plan.index, 'keys': plan.keys}
    files=plan.files;paths=[p for p in sorted(files) if p!='app.ini']
    def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in (data or b'\0'))+'};\n'
    fixture_header=array('PLAN_MF',plan.manifest)+array('PLAN_IX',plan.index)
    for i,path in enumerate(paths):fixture_header+=array('PLAN_BODY_'+str(i),files[path])
    fixture_header+='static const unsigned char *PLAN_BODIES[]={'+','.join('PLAN_BODY_'+str(i) for i in range(len(paths)))+'};\n'
    fixture_header+='static const unsigned PLAN_SIZES[]={'+','.join(str(len(files[p])) for p in paths)+'};\n'
    fixture_header+='static const char *PLAN_PATHS[]={'+','.join(json.dumps(p) for p in paths)+'};\n'
    (work/'package_task_fixture.h').write_text(fixture_header)
    return dict(runtime=RESOLVER, crypto=CRYPTO, tls=TLS, lib=lib, sources=TASK_SOURCES,
                metadata=metadata, files=files, paths=paths, work=work, header=fixture_header)


def main():
    work = ROOT / 'work/package-download-task-tests'
    work.mkdir(exist_ok=True)
    inputs = prepare_package_fixture(work)
    runtime, crypto, tls, lib = (inputs[name] for name in ('runtime', 'crypto', 'tls', 'lib'))
    files, paths, header, sources = (inputs[name] for name in ('files', 'paths', 'header', 'sources'))
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(work),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='package-cache-',dir=work) as cache:
     run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{runtime}',str(work/'test.arm')],capture_output=True,text=True,timeout=30,env=dict(os.environ,HB_TASK_CACHE=cache))
     assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-8000:]);assert not list(Path(cache).iterdir())
    families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
    operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)];assert operations and all('127.0.0.1' in line for line in operations)
    report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'files':[{'path':p,'bytes':len(files[p]),'sha256':hashlib.sha256(files[p]).hexdigest()} for p in paths],'owned_workspace_reused':True,'binary_and_empty_ready_files_read_back':True,'cache_empty_after_explicit_discard':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'fixture_sha256':hashlib.sha256(header.encode()).hexdigest(),'trace':run.stderr,'limits':['Only explicit local DNS/TCP with sample localhost TLS root/key; no remote/device.','Synthetic ARM ELF header bytes are downloaded, never executed.','Each file discarded after inspection, no assembled package directory or install/activation.','app.ini/index provided inline, not bootstrapped from a remote catalog.']}
    (ROOT/'sources/native-package-download-task-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip())


if __name__ == '__main__':
    main()
