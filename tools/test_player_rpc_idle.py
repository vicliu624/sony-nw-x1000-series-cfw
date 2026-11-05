"""Controlled owner-loop idle cadence, host sanitizers and original-lib ARM."""
from pathlib import Path
import hashlib,json,os,selectors,subprocess
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
w=ROOT/'work/player-rpc-idle';w.mkdir(exist_ok=True)
core=['runtime/platform/player/'+n+'.c' for n in ('client','rpc_wire','rpc_posix')]
fixture='tools/fixtures/player_rpc_idle.c';sources=core+[fixture,'tools/fixtures/player_host_clock.c']
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(ROOT/'sdk/include')]
app=w/'host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(app)],cwd=ROOT,check=True)
endpoint='player-idle-'+str(os.getpid());process=subprocess.Popen([str(app),'--server',endpoint],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
 selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);assert selector.select(5);assert process.stdout.readline().strip()=='READY'
 client=subprocess.run([str(app),'--client',endpoint],capture_output=True,text=True,timeout=10)
 (w/'client.log').write_text(client.stdout+client.stderr);assert client.returncode==0,client.stdout+client.stderr
 process.terminate();stdout,stderr=process.communicate(timeout=5);(w/'server.log').write_text(stdout+stderr);assert process.returncode==0,stdout+stderr
finally:
 if process.poll() is None:process.terminate();process.communicate(timeout=5)
libraries=stock_libraries(include_rt=True);arm=w/'idle.arm';init=w/'init.arm';startup=['runtime/store/start.c','runtime/store/start.S'];init_source='tools/fixtures/player_broker_system_init.c'
arm_flags=['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_LIBC_CLOCK','-DXW_TEST_IDLE_RPC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
links=[str(libraries[n]) for n in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]
arm_sources=core+[fixture,'runtime/store/deadline.c']
subprocess.run([*arm_flags,*arm_sources,*startup,*links,'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run([*arm_flags,init_source,*startup,*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
guest=run_guest(w,init,{'server':arm,'client':arm},libraries,['RPC_IDLE_PASS','CLEAN: idle server executed exactly two commands','PLAYER_SYSTEM_CLIENT_STATUS=0 SERVER_STATUS=0','PLAYER_SYSTEM_IPC_PASS'])
assert guest['passed'],(w/'serial.log').read_text(errors='replace')[-2000:]
inputs=sorted(set(sources+arm_sources+startup+[init_source,Path(__file__).relative_to(ROOT).as_posix()]+['runtime/platform/player/'+name+'.h' for name in ('player','provider','rpc_wire','rpc_posix')]+['runtime/store/deadline.h','sdk/include/x1000/services/player.h','sdk/include/x1000/services/player_remote.h']))
report=dict(guest,device_accessed=False,owner_cadence_ms=200,client_deadline_ms=300,host_sanitizers=True,original_libc_arm_kernel=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},limits=['Controlled owner cadence and modeled player; this is not physical UI latency or a sleep/USB qualification.','Original libraries run in a generic ARM kernel, not Sony firmware boot.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
