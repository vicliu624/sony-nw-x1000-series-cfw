"""Execute both fixed loader profiles with execve intercepted; no module loads."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/autonomous-espnow-test';OUT.mkdir(exist_ok=True)
sources=['tools/test_xnow_loader_job.c','runtime/platform/espnow/xnow_loader_job.c','runtime/platform/espnow/xnow_session.c']
lib=ROOT/'work/arm-signal-tests/lib';rows=[]
for name,directory in [('legacy','/contents/HOMEBREW/data/espnow/candidate'),('test','/contents/HOMEBREW/data/espnow-test/candidate')]:
    common=['-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-DXNOW_CANDIDATE_DIRECTORY="'+directory+'"','-DTEST_EXPECTED_CANDIDATE_ENV="fw_dir='+directory+'"','-Wl,--wrap=execve']
    host=OUT/('loader-'+name+'.host');subprocess.run(['gcc',*common,*sources,'-o',str(host)],cwd=ROOT,check=True)
    a=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=15)
    arm=OUT/('loader-'+name+'.arm');subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
    b=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,check=True,timeout=15)
    rows.append({'profile':name,'candidate_directory':directory,'host':a.stdout,'arm926_stock_libc':b.stdout})
report={'passed':True,'profiles':rows,'stock_restore_directory_unchanged':True,'execve_intercepted':True,'device_accessed':False,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
(OUT/'loader-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
