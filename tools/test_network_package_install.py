"""Local DNS/TLS downloads to complete package and existing installer; no device."""
from pathlib import Path
import runpy,subprocess,tempfile,os,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
previous=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
work=ROOT/'work/network-package-install-tests';work.mkdir(exist_ok=True)
runtime=previous['runtime'];crypto=previous['crypto'];tls=previous['tls']
sources=previous['sources']+['runtime/store/'+p+'.c' for p in ('package_assemble','bundle_posix','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-DHB_PACKAGE_ASSEMBLE','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(previous['work']),'-I'+str(previous['old_work']),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
traces=[];rows=[]
for scenario in ('complete','corrupt-resource'):
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp);cache=base/'cache';packages=base/'packages';apps=base/'apps'
  for p in (cache,packages,apps):p.mkdir()
  (apps/'unrelated').write_bytes(b'KEEP')
  existing=dict(previous['files'],**{'files.sha256':previous['metadata']['index']})
  if scenario=='corrupt-resource':
   for name,data in existing.items():
    target=apps/'demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=40,env=dict(os.environ,HB_TASK_SCENARIO=scenario,HB_TASK_CACHE=str(cache),HB_TASK_PACKAGES=str(packages),HB_TASK_APPS=str(apps)))
  assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-10000:])
  expected=dict(previous['files'],**{'files.sha256':previous['metadata']['index']})
  for folder in ((packages/'.bundle-demo',apps/'demo') if scenario=='complete' else (packages/'.bundle-demo',)):
   actual={str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
   wanted=expected if scenario=='complete' else {p:expected[p] for p in ('app','app.ini','files.sha256')}
   assert actual==wanted,(folder,actual.keys())
  assert not list(cache.iterdir()) and (apps/'unrelated').read_bytes()==b'KEEP'
  assert {p.name for p in apps.iterdir()} <= {'demo','unrelated','.store-lock'}
  if scenario=='corrupt-resource':
   retained={str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file()}
   assert retained==existing
   assert {p.name for p in apps.iterdir()}=={'demo','unrelated'}
  traces.append(run.stderr)
  rows.append({'scenario':scenario,'passed':True})
trace='\n'.join(traces)
operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
assert operations and all('127.0.0.1' in line for line in operations)
families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'downloaded_files':previous['paths'],'assembled_and_installed_bytes_verified':True,'cache_empty':True,'unrelated_data_preserved':True,'trace':trace,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Positive flow and second-resource hash mismatch only; not exhaustive interruption/install fault qualification.','Metadata inline, sample TLS trust and local DNS only; no remote catalog or Wi-Fi.','Synthetic ARM ELF never executed; host filesystem not Sony FAT.','No UI integration, device execution, firmware generation or hardware safety qualification.']}
(ROOT/'sources/native-network-package-install-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Network package: complete install and second-resource hash rejection passed.')
