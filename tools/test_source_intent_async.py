"""Real background validation -> explicit GUI-owner source submission composition."""
import hashlib,json,os,subprocess,sys,time
from app_registry import ROOT
managed='--managed' in sys.argv
w=ROOT/('work/source-managed-async' if managed else 'work/source-intent-async');w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/'+n+'.c' for n in ('source_intent','audio_check_async','metadata_async','local_identity')]+['tools/fixtures/source_intent_async.c']
if managed:sources=sources[:-1]+['runtime/platform/player/'+n+'.c' for n in ('source_service','managed','client')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events')]+['tools/fixtures/source_managed_async.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if windows:sources+=['tools/fixtures/windows_pthread.c']
else:flags+=['-pthread','-fsanitize=address,undefined']
out=w/('test-windows.exe' if windows else 'test')
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True)
subprocess.run([str(out)],check=True,timeout=30)
report=dict(passed=True,device_accessed=False,real_threads=True,host='windows-win32-shim' if windows else 'linux-pthread',sanitizers=not windows,checks=['blocked old validation cannot submit after replacement','new validation closes its native client before submission','uncertain submission is not replayed','cancelled in-flight read cannot submit','video refusal propagated','source loss prevents late submission and requires new generation','worker cannot call GUI submission','stop/drain/destroy balances all clients'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/source_intent.h','runtime/platform/player/audio_check_async.h','runtime/platform/player/metadata_async.h','tools/test_source_intent_async.py']},limits=['Native media validation, GUI view and submission are modeled; worker and intent implementations execute.','No Sony thread ABI, full stop/install/play transaction or hardware qualification. This test does not install the host endpoint.'])
if managed:
 report['managed_source_service']=True
 report['checks']=['revoked client cannot submit blocked validation','new session explicitly replaces target','old request ID never advances intent','uncertain result not resubmitted','backend close waits for actual validation thread and balances native clients']
 report['source_hashes']['tools/fixtures/source_intent_async.c']=hashlib.sha256((ROOT/'tools/fixtures/source_intent_async.c').read_bytes()).hexdigest()
 if not windows:
  from player_arm_guest import stock_libraries,run_guest
  guest=w/str(time.time_ns());guest.mkdir();libs=stock_libraries()
  startup=['runtime/store/start.c','runtime/store/start.S'];init_source='tools/fixtures/player_worker_system_init.c'
  arm_flags=['-std=c11','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
  binary=guest/'test.arm';init=guest/'init.arm'
  for target,code in ((binary,sources),(init,[init_source])):
   subprocess.run(['arm-linux-gnueabi-gcc',*arm_flags,*code,*startup,str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(target)],cwd=ROOT,check=True)
  result=run_guest(guest,init,{'test':binary},libs,['MANAGED_SOURCE_ASYNC_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
  assert result['passed'],(guest/'serial.log').read_text(errors='replace')[-2000:]
  report['original_linuxthreads_arm_guest']=result
  report['source_hashes'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in startup+[init_source]})
  report['limits']=['Production managed/source/intent/worker code and actual threads execute; native media validation, GUI and source submission are models.','ARM guest uses original Sony LinuxThreads/libc with mutex-backed fixture counters, generic kernel; not full native stop/install/play or physical qualification.']
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
