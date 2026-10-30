"""Real local IPC with host sanitizers and Sony-libc ARM, modeled player only."""
from pathlib import Path
import hashlib,json,os,selectors,subprocess,time
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-rpc';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/client.c','runtime/platform/player/rpc_wire.c','runtime/platform/player/rpc_posix.c','tools/fixtures/player_rpc.c']
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation'];host=work/'host';arm=work/'rpc.arm';lib=ROOT/'work/arm-signal-tests/lib';extra=ROOT/'work/player-sqlite-ro';rt=ROOT/'work/stock-resolver-probe/librt.so.1'
subprocess.run(['gcc-12',*flags,'-O1','-DXW_RPC_HOST_TEST','-fsanitize=address,undefined','-fno-omit-frame-pointer',*sources,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/deadline.c','runtime/store/start.c','runtime/store/start.S',str(rt),str(extra/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD');cases=[]
for name,command in [('host',[str(host)]),('arm',['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(rt.parent)+':'+str(extra)+':'+str(lib),str(arm)])]:
 run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=10);assert run.returncode==0,run.stdout+run.stderr
 endpoint=f'xw-rpc-{os.getpid()}-{name}';server=subprocess.Popen(command+['--server',endpoint],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  selector=selectors.DefaultSelector();selector.register(server.stdout,selectors.EVENT_READ);assert selector.select(5),'Server did not become ready';ready=server.stdout.readline();assert ready.strip()=='READY',ready
  client=subprocess.run(command+['--client',endpoint],env=env,capture_output=True,text=True,timeout=15);assert client.returncode==0,client.stdout+client.stderr
  stdout,stderr=server.communicate(timeout=5);assert server.returncode==0,stdout+stderr
  (work/(name+'.log')).write_text(run.stdout+run.stderr+client.stdout+client.stderr+stdout+stderr)
  cases.append(dict(profile=name,wire=run.stdout,client=client.stdout,server=stdout))
 finally:
  if server.poll() is None:server.kill();server.communicate()
report=dict(passed=True,host_sanitizers=True,original_libc_arm=True,real_unix_sockets=True,modeled_player=True,device_accessed=False,cases=cases,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/player.h','runtime/platform/player/provider.h','runtime/platform/player/rpc_wire.h','runtime/platform/player/rpc_posix.h','runtime/store/deadline.c','tools/test_player_rpc.py']},
 limits=['The provider is a synthetic fixture, not Sony playback or a live playlist/queue.', 'Original libc IPC/clock ABI and the client/server implementation are exercised; no firmware endpoint has been installed.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
