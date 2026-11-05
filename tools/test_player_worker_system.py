"""Production selection/reader workers with Sony LinuxThreads in a PC ARM guest."""
from pathlib import Path
import hashlib,json,subprocess
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
w=ROOT/'work/player-worker-system';w.mkdir(exist_ok=True)
libraries=stock_libraries();pthread=libraries['libpthread.so.0']
core=['runtime/platform/player/'+n+'.c' for n in ('source_intent','audio_check_async','metadata_async','local_identity')]
startup=['runtime/store/start.c','runtime/store/start.S'];fixture='tools/fixtures/player_worker_system.c';init_source='tools/fixtures/player_worker_system_init.c'
flags=['arm-linux-gnueabi-gcc','-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
app=w/'worker.arm';init=w/'init.arm'
subprocess.run([*flags,*core,fixture,*startup,str(pthread),str(libraries['libc.so.6']),str(libraries['ld-linux.so.3']),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run([*flags,init_source,*startup,str(libraries['libc.so.6']),str(libraries['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(w,init,{'test':app},libraries,['PLAYER_ORIGINAL_THREADS_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
headers=['runtime/platform/player/'+name+'.h' for name in ('source_intent','audio_check_async','metadata_async','stock_media','stock_source','stock_gui','local_identity','player','query_snapshot')]
paths=core+startup+headers+[fixture,init_source,Path(__file__).relative_to(ROOT).as_posix()]
report.update(generic_arm_linux_kernel=True,original_linuxthreads=True,original_thread_create_and_detached_drain=report['passed'],production_intent_and_worker=True,native_media_and_gui_modeled=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},limits=['Generic ARM Linux2.6.32/ARM926 kernel, not Sony hardware or its original kernel.','Original libc/loader/LinuxThreads and production reader/intent execute; media objects, validation result and GUI/submission are modeled.','This does not boot SpiderApp, decode audio or qualify APF, sleep/USB or hardware operation.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print((w/'serial.log').read_text(errors='replace')[-1400:]);print(json.dumps(report,indent=2));assert report['passed'],(w/'qemu.log').read_text(errors='replace')[-1000:]
