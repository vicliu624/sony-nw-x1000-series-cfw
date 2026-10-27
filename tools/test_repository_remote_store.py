"""Local DNS/TLS downloads to complete package and existing installer; no device."""
from pathlib import Path
import runpy,subprocess,tempfile,os,json,hashlib,re,ssl,socket,struct
ROOT=Path(__file__).resolve().parents[1]
previous=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
work=ROOT/'work/repository-remote-store-tests';work.mkdir(exist_ok=True)
runtime=previous['runtime'];crypto=previous['crypto'];tls=previous['tls']
sources=[p for p in previous['sources'] if p not in ('tools/test_download_task.c','tools/download_file_faults.c')]+['tools/repository_record_faults.c']+['tools/test_repository_remote_store.c','runtime/store/repository.c','runtime/store/remote_store.c','runtime/store/metadata_cache.c','runtime/store/metadata_fetch.c','runtime/store/remote_catalog.c','runtime/store/remote_list.c','runtime/store/package_resume.c','runtime/store/download_intent.c','runtime/store/download_record.c','runtime/store/payload_cache_cleanup.c','runtime/store/partial_cleanup.c','runtime/store/download_recovery.c','runtime/store/package_job.c','runtime/store/job_ui.c','runtime/store/canvas.c','runtime/native/frontend.c']+['runtime/store/'+p+'.c' for p in ('package_assemble','bundle_posix','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-DHB_PACKAGE_ASSEMBLE','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(previous['work']),'-I'+str(previous['old_work']),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
traces=[];rows=[]
positive_cases={'complete','resume-complete','recover-restart','actual-crash-restart','actual-record-crash-restart','meta-complete','meta-retry','meta-corrupt','actual-meta-crash-restart','info-complete','info-retry','index-complete','index-retry'}
scenarios=('complete','corrupt-resource','cancel-second','present-fail','metadata-hash','list-back','metadata-cancel','resume-complete','recover-restart','recover-back','actual-crash-restart','actual-crash-back','actual-record-crash-restart','actual-record-crash-back','meta-complete','meta-retry','meta-back','meta-corrupt','meta-link','meta-retry-present-fail','actual-meta-crash-restart','actual-meta-crash-back','info-complete','info-retry','index-complete','index-retry')
def snapshot(folder):return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file() and not p.is_symlink()}
for scenario in scenarios:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp);cache=base/'cache';packages=base/'packages';apps=base/'apps'
  for folder in (cache,packages,apps):folder.mkdir()
  repository_dir=base/'repository';repository_dir.mkdir();ca_der=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-rsa.pem').read_text());(repository_dir/'ca.der').write_bytes(ca_der);(apps/'unrelated').write_bytes(b'KEEP')
  env=dict(os.environ,HB_TEST_REPOSITORY=str(repository_dir),HB_TEST_CA_HASH=hashlib.sha256(ca_der).hexdigest(),HB_TASK_CACHE=str(cache),HB_TASK_PACKAGES=str(packages),HB_TASK_APPS=str(apps))
  command=['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')]
  if scenario.startswith('actual-meta-'):
   with socket.socket() as listener:listener.bind(('127.0.0.1',0));env['HB_META_TEST_PORT']=str(listener.getsockname()[1])
  expected=dict(previous['files'],**{'files.sha256':previous['metadata']['index']})
  if scenario=='resume-complete':
   for name,data in expected.items():target=packages/'.bundle-demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  if scenario in ('recover-restart','recover-back'):
   seed=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(env,HB_TASK_SCENARIO='seed-record'));assert seed.returncode==0,seed.stderr
   for name,data in expected.items():target=packages/'.bundle-demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data[:5])
   (cache/('.fetch-'+previous['metadata']['keys'][0])).write_bytes(b'OLD PARTIAL')
  if scenario not in positive_cases:
   for name,data in expected.items():target=apps/'demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  cache_before=snapshot(cache);packages_before=snapshot(packages);effective=scenario
  if scenario.startswith('actual-'):
   kind='crash-metadata' if scenario.startswith('actual-meta-') else 'crash-record' if scenario.startswith('actual-record-') else 'crash-payload'
   crashed=subprocess.run(command,capture_output=True,text=True,timeout=40,env=dict(env,HB_TASK_SCENARIO=kind));assert crashed.returncode==77,(scenario,crashed.returncode,crashed.stderr[-7000:]);traces.append(crashed.stderr)
   if kind=='crash-metadata':assert not list(packages.iterdir()) and len(list(cache.iterdir()))==1 and next(cache.iterdir()).read_bytes()==b'H'
   elif kind=='crash-record':
    assert not (packages/'.download-demo.intent').exists() and not (packages/'.bundle-demo').exists();staged=list(packages.glob('.save-demo-*'));assert len(staged)==1 and staged[0].read_bytes()==b'H'
   else:assert (packages/'.download-demo.intent').exists() and (packages/'.bundle-demo/app').read_bytes()==previous['files']['app'] and (cache/('.fetch-'+previous['metadata']['keys'][1])).exists()
   cache_before=snapshot(cache);packages_before=snapshot(packages);(repository_dir/'repository.conf').unlink()
   effective=('meta-retry' if scenario.endswith('-restart') else 'meta-back') if kind=='crash-metadata' else ('recover-restart' if scenario.endswith('-restart') else 'recover-back')
  if scenario in positive_cases:env['HB_UI_PREVIEW']=str(work/'ready.ppm')
  run=subprocess.run(command,capture_output=True,text=True,timeout=40,env=dict(env,HB_TASK_SCENARIO=effective));assert run.returncode==0,(scenario,run.returncode,run.stdout,run.stderr[-10000:])
  assert (apps/'unrelated').read_bytes()==b'KEEP'
  if effective=='recover-back':assert snapshot(packages)==packages_before and snapshot(cache)==cache_before
  else:assert not list(packages.iterdir())
  if effective in ('meta-back','meta-link'):
   fields=dict(line.split('=',1) for line in (repository_dir/'repository.conf').read_text().splitlines()[1:]);key=hashlib.sha256(b'HBMETA1'+fields['catalog_url'].encode()+bytes.fromhex(fields['catalog_sha256'])+struct.pack('<I',int(fields['catalog_bytes']))).hexdigest()[:32];target=cache/('.fetch-'+key)
   assert {p.name for p in cache.iterdir()}=={target.name}
   if effective=='meta-back':assert target.read_bytes()==b'H'
   else:assert target.is_symlink() and (apps/'unrelated').read_bytes()==b'KEEP'
  elif effective!='recover-back':assert not list(cache.iterdir())
  if scenario in positive_cases:assert snapshot(apps/'demo')==expected
  else:assert snapshot(apps/'demo')==expected and {p.name for p in apps.iterdir()}=={'demo','unrelated'}
  assert {p.name for p in apps.iterdir()}<={'demo','unrelated','.store-lock'}
  traces.append(run.stderr);rows.append({'scenario':scenario,'passed':True})
trace='\n'.join(traces)
operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
assert operations and all('127.0.0.1' in line for line in operations)
families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
symbols=subprocess.check_output(['arm-linux-gnueabi-readelf','-sW',str(work/'test.arm')],text=True)
workspace_bytes=int(next(line.split()[2] for line in symbols.splitlines() if line.split() and line.split()[-1]=='store'),0)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'workspace_bytes_excluding_stack_library_heap':workspace_bytes,'downloaded_files':previous['paths'],'assembled_and_installed_bytes_verified':True,'cache_empty_after_completed_cleanup':True,'back_preserves_pending_files':True,'real_download_process_exit_recovery_tested':True,'record_publication_exit_recovery_tested':True,'metadata_cache_reuse_recovery_tested':True,'unrelated_data_preserved':True,'trace':trace,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/download_file_faults.c']},'limits':['Fetched metadata hash rejection plus scripted touch/controller/network; not exhaustive I/O faults; not exhaustive interruption/install fault qualification.','repository.conf/ca.der loaded at runtime for real local TLS, sample public root and fixture-generated repository pin; no production endpoint or Wi-Fi qualification.','Synthetic ARM ELF never executed; host filesystem not Sony FAT.','Scripted platform; no successful native display/touch execution or hardware qualification.']}
(ROOT/'sources/native-repository-remote-store-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Runtime repository config + decoded CA -> real TLS remote-store paths passed.')

# Preview conversion uses the host standard library only.
import struct,zlib
ppm=(work/'ready.ppm').read_bytes();header=b'P6\n240 432\n255\n';assert ppm.startswith(header)
rgb=ppm[len(header):];assert len(rgb)==240*432*3
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
(work/'ready.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
