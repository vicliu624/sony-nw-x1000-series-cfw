"""App lifecycle with controlled platform/backend, host and original libc ARM."""
from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/network-app-tests';work.mkdir(exist_ok=True)
crypto=ROOT/'work/external-tls-probe/bearssl-0.6'
sources=['runtime/store/network_app.c','runtime/store/canvas.c','runtime/native/frontend.c','tools/test_network_app.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(crypto/'inc'),'-I'+str(ROOT/'work/stock-resolver-probe')]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
runtime=metadata['work'];bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'cases_each_platform':['normal','partial platform open failure closes','close failure','platform stop before repository access','repository error page','missing repository setup page','present failure','active transport cancellation before close','termination setup failure'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['runtime/store/network_app.h','runtime/store/repository.h','runtime/store/remote_store.h','runtime/store/canvas.h','runtime/store/termination.h','runtime/native/font.inc']},'limits':['Platform, repository, remote-store and signal functions substituted; actual allocation/canvas/control flow.','Does not qualify hardware, network or physical USB lifecycle.','Retained temporary trees are not auto-deleted on app exit.']}
(ROOT/'sources/native-network-app-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Network app lifecycle: nine cases on host and ARM/QEMU passed.')
