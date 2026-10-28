"""Process/pipe/guard lifecycle on host and Sony libc ARM; no sound devices."""
from pathlib import Path
import hashlib,json,subprocess,tempfile,shutil,os
ROOT=Path(__file__).resolve().parents[1]
w=ROOT/'work/qqmusic-preview-supervisor';w.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
shutil.copyfile(ROOT/'work/stock-resolver-probe/librt.so.1',w/'librt.so.1')
shutil.copyfile(ROOT/'work/stock-resolver-probe/libpthread.so.0',w/'libpthread.so.0')
common=['runtime/apps/qqmusic/qqmusic_preview_wire.c']
supervisor=['runtime/apps/qqmusic/qqmusic_preview_owners.c','runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/sha256.c','runtime/apps/qqmusic/qqmusic_preview_supervisor.c','runtime/native/linux_process_posix.c','runtime/native/linux_signals_posix.c','tools/fixtures/qqmusic_preview_supervisor.c']
flags=['-std=c99','-Wall','-Wextra','-Werror']
if os.geteuid()!=0:raise SystemExit('Run under a privileged isolated development environment: owners scans global /proc FD identities.')
results=[]
evidence=set()
for name,files in [('client',['runtime/apps/qqmusic/qqmusic_preview_client.c','runtime/apps/qqmusic/qqmusic_preview_service.c','runtime/apps/qqmusic/qqmusic_preview_device.c','runtime/apps/qqmusic/qqmusic_preview_session.c','runtime/apps/qqmusic/qqmusic_preview_wire.c','runtime/apps/qqmusic/qqmusic_preview_transport.c','runtime/apps/qqmusic/qqmusic_preview_producer.c','runtime/apps/qqmusic/qqmusic_preview_owners.c','runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/linux_process_posix.c','runtime/native/linux_signals_posix.c','runtime/native/sha256.c','tools/fixtures/qqmusic_preview_client.c']),('transport',['runtime/apps/qqmusic/qqmusic_preview_transport.c','runtime/apps/qqmusic/qqmusic_preview_wire.c','runtime/native/linux_process_posix.c','tools/fixtures/qqmusic_preview_transport.c']),('service',['runtime/apps/qqmusic/qqmusic_preview_service.c','runtime/apps/qqmusic/qqmusic_preview_device.c','runtime/apps/qqmusic/qqmusic_preview_session.c','runtime/apps/qqmusic/qqmusic_preview_wire.c','runtime/apps/qqmusic/qqmusic_preview_producer.c','runtime/apps/qqmusic/qqmusic_preview_owners.c','runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/sha256.c','tools/fixtures/qqmusic_preview_service.c']),('producer',['runtime/apps/qqmusic/qqmusic_preview_producer.c','runtime/apps/qqmusic/qqmusic_preview_owners.c','runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/sha256.c','tools/fixtures/qqmusic_preview_producer.c']),('wire',common+['tools/fixtures/qqmusic_preview_wire.c']),('supervisor',common+supervisor),('owners',['runtime/apps/qqmusic/qqmusic_preview_owners.c','runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/sha256.c','tools/fixtures/qqmusic_preview_owners.c'])]:
 host=w/(name+'.sanitized');arm=w/(name+'.arm')
 subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*files,*(['runtime/store/deadline.c'] if name in ('transport','client') else []),'-o',str(host)],cwd=ROOT,check=True)
 with tempfile.TemporaryDirectory(dir=w) as d:subprocess.run([str(host),str(Path(d)/'guard')],check=True,timeout=15)
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*files,'runtime/store/deadline.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(w/'librt.so.1'),str(w/'libpthread.so.0'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
 with tempfile.TemporaryDirectory(dir=w) as d:
  r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(w)+':'+str(lib),str(arm),str(Path(d)/'guard')],capture_output=True,timeout=20)
  assert r.returncode==0,r.stderr.decode(errors='replace')[-3000:]
 results.append(name);evidence.update(files)
report={'passed':True,'host_asan_ubsan':True,'stock_arm_libc':True,'suites':results,'process_cases':7,'service_cases':7,'physical_device_accessed':False,'limits':['Audio cleanup is supplied by a model. Supervisor retirement additionally uses the real global FD scan, including orphan holders. Physical audio output remains unqualified.','No account, network or audio device access.'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(evidence|{'tools/fixtures/qqmusic_preview_device.c','runtime/apps/qqmusic/qqmusic_preview_service.h','runtime/apps/qqmusic/qqmusic_preview_device.h','runtime/native/linux_process.h','runtime/store/stock_fs_bridge.c','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.c'})}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))











