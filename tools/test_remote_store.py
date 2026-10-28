"""Local DNS/TLS downloads to complete package and existing installer; no device."""
from pathlib import Path
import runpy,subprocess,tempfile,os,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
previous=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
work=ROOT/'work/remote-store-tests';work.mkdir(exist_ok=True)
runtime=previous['runtime'];crypto=previous['crypto'];tls=previous['tls']
sources=[p for p in previous['sources'] if p!='tools/test_download_task.c']+['tools/test_remote_store.c','runtime/store/remote_store.c','runtime/store/metadata_cache.c','runtime/store/metadata_fetch.c','runtime/store/remote_catalog.c','runtime/store/remote_list.c','runtime/store/package_resume.c','runtime/store/download_intent.c','runtime/store/download_record.c','runtime/store/payload_cache_cleanup.c','runtime/store/partial_cleanup.c','runtime/store/download_recovery.c','runtime/store/package_job.c','runtime/store/job_ui.c','runtime/store/canvas.c','runtime/native/frontend.c']+['runtime/store/'+p+'.c' for p in ('package_assemble','bundle_posix','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-DHB_PACKAGE_ASSEMBLE','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(previous['work']),'-I'+str(previous['old_work']),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
traces=[];rows=[]
for scenario in ('complete','corrupt-resource','cancel-second','present-fail','metadata-hash','list-back','metadata-cancel','details-back','details-cancel'):
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  base=Path(temp);cache=base/'cache';packages=base/'packages';apps=base/'apps'
  for p in (cache,packages,apps):p.mkdir()
  (apps/'unrelated').write_bytes(b'KEEP')
  existing=dict(previous['files'],**{'files.sha256':previous['metadata']['index']})
  if scenario!='complete':
   for name,data in existing.items():
    target=apps/'demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=40,env=dict(os.environ,**({'HB_UI_PREVIEW':str(work/'ready.ppm')} if scenario=='complete' else {}),HB_TASK_SCENARIO=scenario,HB_TASK_CACHE=str(cache),HB_TASK_PACKAGES=str(packages),HB_TASK_APPS=str(apps)))
  assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-10000:])
  expected=dict(previous['files'],**{'files.sha256':previous['metadata']['index']})
  assert not list(packages.iterdir())
  for folder in ((apps/'demo',) if scenario=='complete' else ()):
   actual={str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
   wanted=expected if scenario=='complete' else {p:expected[p] for p in ('app','app.ini','files.sha256')}
   assert actual==wanted,(folder,actual.keys())
  assert not list(cache.iterdir()) and (apps/'unrelated').read_bytes()==b'KEEP'
  assert {p.name for p in apps.iterdir()} <= {'demo','unrelated','.store-lock'}
  if scenario!='complete':
   retained={str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file()}
   assert retained==existing
   assert {p.name for p in apps.iterdir()}=={'demo','unrelated'}
  traces.append(run.stderr)
  rows.append({'scenario':scenario,'passed':True})
trace='\n'.join(traces)
operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
assert operations and all('127.0.0.1' in line for line in operations)
families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
symbols=subprocess.check_output(['arm-linux-gnueabi-readelf','-sW',str(work/'test.arm')],text=True)
workspace_bytes=int(next(line.split()[2] for line in symbols.splitlines() if line.split() and line.split()[-1]=='store'),0)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'workspace_bytes_excluding_stack_library_heap':workspace_bytes,'downloaded_files':previous['paths'],'assembled_and_installed_bytes_verified':True,'cache_empty':True,'unrelated_data_preserved':True,'trace':trace,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Fetched metadata hash rejection plus scripted touch/controller/network; not exhaustive I/O faults; not exhaustive interruption/install fault qualification.','Catalog, manifest and inventory fetched over local TLS; catalog root size/hash pinned by fixture; no production repository configuration or Wi-Fi.','Synthetic ARM ELF never executed; host filesystem not Sony FAT.','Scripted UI only, not default app candidate integration; no physical execution or hardware qualification.']}
(ROOT/'sources/native-remote-store-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Production C remote-store controller: network/list/metadata/install/error/cancel paths passed.')

# Preview conversion uses the host standard library only.
import struct,zlib
ppm=(work/'ready.ppm').read_bytes();header=b'P6\n240 432\n255\n';assert ppm.startswith(header)
rgb=ppm[len(header):];assert len(rgb)==240*432*3
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
(work/'ready.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
