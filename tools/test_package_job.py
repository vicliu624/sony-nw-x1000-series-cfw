"""Package job state machine with deterministic transport, actual file operations."""
from pathlib import Path
import runpy,subprocess,tempfile,os,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
transport=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
assembly=runpy.run_path(str(ROOT/'tools/test_package_assemble.py'))
work=ROOT/'work/package-job-tests';work.mkdir(exist_ok=True)
sources=[p for p in assembly['sources'] if p!='tools/test_package_assemble.c']+['runtime/store/package_resume.c','runtime/store/download_intent.c','runtime/store/download_record.c','runtime/store/payload_cache_cleanup.c','runtime/store/partial_cleanup.c','runtime/store/download_recovery.c','runtime/store/package_job.c','runtime/store/job_ui.c','runtime/store/canvas.c','runtime/native/frontend.c','tools/test_package_job.c']
crypto=transport['crypto'];runtime=transport['runtime']
includes=['-I'+str(crypto/'inc'),'-I'+str(runtime),'-I'+str(assembly['work'])]
common=['-DHB_JOB_UI','-std=c99','-Wall','-Wextra','-Werror',*includes]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*assembly['bridge'],str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('ready','install','cancel','hash','ui-install','ui-cancel','ui-present-fail','ui-platform','resume-ready','resume-install','resume-bad','recover-restart','ui-recovery-restart','ui-recovery-back','recover-unknown','unclaimed-cache','unrecognized','ui-unrecognized','space','marker-restart','ui-marker-restart','ui-marker-back','ui-marker-bad'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);cache=base/'cache';packages=base/'packages';apps=base/'apps'
   for p in (cache,packages,apps):p.mkdir()
   (apps/'keep').write_bytes(b'KEEP')
   resume_files=dict(assembly['files'],**{'files.sha256':assembly['metadata']['index']})
   if mode.startswith('resume-'):
    for name,data in resume_files.items():
     target=packages/'.bundle-demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if mode=='resume-bad':(packages/'.bundle-demo/app').write_bytes(b'X'*len(resume_files['app']))
   recovery_modes=('recover-restart','ui-recovery-restart','ui-recovery-back','recover-unknown')
   env=dict(os.environ,HB_JOB_CACHE=str(cache),HB_JOB_PACKAGES=str(packages),HB_JOB_APPS=str(apps))
   if mode in recovery_modes:
    seeded=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(env,HB_JOB_CASE='seed-record'));assert seeded.returncode==0,seeded.stderr
    for name,data in resume_files.items():
     target=packages/'.bundle-demo'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data[:5])
    (cache/('.fetch-'+assembly['metadata']['keys'][0])).write_bytes(b'X'*10)
    if mode=='recover-unknown':(packages/'.bundle-demo/unknown').write_bytes(b'KEEP')
   if mode in ('marker-restart','ui-marker-restart','ui-marker-back','ui-marker-bad'):
    seeded=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(env,HB_JOB_CASE='seed-record'));assert seeded.returncode==0,seeded.stderr
    final=packages/'.download-demo.intent';data=final.read_bytes();temporary=packages/('.save-demo-'+hashlib.sha256(data).hexdigest());final.unlink();temporary.write_bytes(b'X' if mode=='ui-marker-bad' else data[:1])
   if mode=='unclaimed-cache':(cache/('.fetch-'+assembly['metadata']['keys'][0])).write_bytes(b'KEEP')
   if mode in ('unrecognized','ui-unrecognized'):(packages/'.download-demo.intent').write_bytes(b'KEEP')
   def snapshot(folder):return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
   cache_before=snapshot(cache);packages_before=snapshot(packages)
   run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,**({'HB_RECOVERY_PREVIEW':str(work/'recovery.ppm')} if mode=='ui-recovery-back' else {}),HB_JOB_CASE=mode,HB_JOB_CACHE=str(cache),HB_JOB_PACKAGES=str(packages),HB_JOB_APPS=str(apps)))
   assert run.returncode==0,(platform,mode,run.returncode,run.stderr)
   preserved=mode in ('ui-recovery-back','recover-unknown','unclaimed-cache','unrecognized','ui-unrecognized','ui-marker-back','ui-marker-bad')
   assert (apps/'keep').read_bytes()==b'KEEP'
   if preserved:assert snapshot(cache)==cache_before and snapshot(packages)==packages_before
   else:assert not list(cache.iterdir())
   if mode=='resume-bad':assert (packages/'.bundle-demo/app').read_bytes()==b'X'*len(resume_files['app'])
   elif not preserved:assert not list(packages.iterdir())
   if mode in ('install','ui-install','resume-install','ui-recovery-restart','ui-marker-restart'):
    expected=dict(assembly['files'],**{'files.sha256':assembly['metadata']['index']})
    actual={str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file()}
    assert actual==expected
   else:assert {p.name for p in apps.iterdir()}=={'keep'}
   rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+assembly['bridge']},'limits':['Mock transport, real cache/assembly/installer; not full network controller integration.','Scripted touch/painter UI; no remote catalog, physical filesystem or hardware qualification.','Copy/check/install synchronous; controller does not guarantee UI responsiveness.','Caller owns trust/options/stop lifetime and quiescent external directories.']}
(ROOT/'sources/native-package-job-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Package job:',len(rows),'host/ARM cases passed.')

# Capture the actual canvas with a standard-library-only PNG conversion.
import struct,zlib
ppm=(work/'recovery.ppm').read_bytes();header=b'P6\n240 432\n255\n';assert ppm.startswith(header);rgb=ppm[len(header):];assert len(rgb)==240*432*3
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
(work/'recovery.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
