"""Actual host broker/cache threads plus original pthread primitive ABI smoke."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-broker';work.mkdir(exist_ok=True)
core=['runtime/platform/player/client.c','runtime/platform/player/local_identity.c','runtime/platform/player/metadata_async.c'];host_sources=core+['runtime/platform/player/player_broker.c','tools/fixtures/player_broker.c'];host=work/'host'
if os.name=='nt':
 host_sources+=['tools/fixtures/windows_pthread.c'];host=work/'host-windows.exe'
 subprocess.run(['clang','-std=c11','-O1','-D_CRT_SECURE_NO_WARNINGS','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*host_sources,'-o',str(host)],cwd=ROOT,check=True)
 run=subprocess.run([str(host)],capture_output=True,text=True,timeout=30);(work/'host-windows.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stdout+run.stderr
 subprocess.run(['clang','--target=armv5te-none-eabi','-std=c99','-Os','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding'),'-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wframe-larger-than=2048','-fstack-usage','-c',str(ROOT/'runtime/platform/player/player_broker.c'),'-o',str(work/'broker-arm-clang.o')],check=True)
 report=dict(passed=True,host='windows-win32-shim',host_sanitizers=False,supported_gnu_build=False,original_pthread_primitives=False,sony_thread_created=False,device_accessed=False,clock_loss_invalidates_metadata_catalog_queue=True,host_stdout=run.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in host_sources+['runtime/platform/player/player_broker.h','tools/fixtures/windows_pthread.h','tools/test_player_broker.py']},limits=['Original backend/media methods and Win32 pthread surface are modeled; this does not qualify Sony runtime or hardware.'])
 (work/'report-windows.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0)
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
subprocess.run(['gcc-12',*flags,'-O1','-fsanitize=address,undefined','-pthread',*host_sources,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=15);(work/'host.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stdout+run.stderr
arm_sources=core+['runtime/platform/player/stock_media.c','runtime/platform/player/stock_query.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/media_text.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/player_metadata_abi.c','runtime/store/start.c','runtime/store/start.S'];lib=ROOT/'work/arm-signal-tests/lib';extra=ROOT/'work/player-sqlite-ro';arm=work/'abi.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*arm_sources,str(extra/'libdl.so.2'),str(extra/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
abi=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(extra)+':'+str(lib),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=15);(work/'arm.log').write_text(abi.stdout+abi.stderr);assert abi.returncode==0,abi.stdout+abi.stderr
report=dict(passed=True,host_sanitizers=True,real_host_worker=True,original_pthread_primitives=True,sony_thread_created=False,device_accessed=False,host_stdout=run.stdout,arm_stdout=abi.stdout,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(host_sources+arm_sources+['runtime/platform/player/player_broker.h','runtime/platform/player/metadata_async.h','tools/test_player_broker.py']))},
 limits=['The host native-media methods are modeled; original Moma ABI/dispatch is covered by test_stock_media.py.', 'The ARM smoke initializes/destroys original pthread primitives only; actual Sony LinuxThreads worker creation and resource/sleep/USB behavior are unqualified.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
