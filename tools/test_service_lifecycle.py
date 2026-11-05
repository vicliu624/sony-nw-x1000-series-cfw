"""Private session/request core: host sanitizers and ARM compilation, no device."""
from pathlib import Path
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/service-lifecycle'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/services/session.c','runtime/platform/services/request.c','runtime/platform/services/events.c','runtime/platform/player/managed.c','runtime/platform/player/client.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
checks=[]
sources+=['runtime/platform/player/managed_rpc.c','runtime/platform/player/rpc_wire.c','runtime/platform/player/managed_channel.c']
sources+=['runtime/platform/player/managed_control.c']
sources+=['runtime/platform/player/managed_codec.c']
sources+=['runtime/platform/player/managed_remote.c']
sources+=['runtime/platform/player/managed_client.c']
sources+=['runtime/platform/player/managed_clock.c']
sources+=['runtime/platform/services/descriptor.c']
sources+=['runtime/platform/player/session_offer.c']
sources+=['runtime/platform/player/service_drain.c']
sources+=['runtime/platform/player/drain_completion.c']
sources+=['runtime/platform/player/deferred_prepare.c']
sources+=['runtime/platform/player/managed_host.c']
libraries=stock_libraries(include_rt=True);libc=libraries['libc.so.6'];loader=libraries['ld-linux.so.3']
arm_flags=[*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
for name in ('session','request','player','events','dispatch','channel','control','descriptor','offer','quiesce','drain','host'):
 fixture='tools/fixtures/service_'+name+'.c';binary=out/name
 subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'tools/fixtures/player_host_clock.c',fixture,'-o',str(binary)],cwd=ROOT,check=True)
 run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10);assert run.returncode==0,run.stdout+run.stderr
 arm=out/(name+'.arm')
 subprocess.run(['arm-linux-gnueabi-gcc',*arm_flags,'-DHB_STORE_LIBC_CLOCK',*sources,fixture,'runtime/store/deadline.c','runtime/store/start.c','runtime/store/start.S',str(libraries['librt.so.1']),str(libraries['libpthread.so.0']),str(libc),str(loader),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
 arm_run=subprocess.run(['qemu-arm','-cpu','arm926',str(loader),'--library-path',str(libc.parent)+':'+str(libraries['librt.so.1'].parent),str(arm)],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=15)
 assert arm_run.returncode==0,arm_run.stdout+arm_run.stderr
 checks.append(dict(fixture=fixture,stdout=run.stdout,original_libc_arm_stdout=arm_run.stdout,arm_sha256=hashlib.sha256(arm.read_bytes()).hexdigest()))
for source in sources:
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-c',source,'-o',str(out/(Path(source).stem+'.arm.o'))],cwd=ROOT,check=True)
inputs=sources+['runtime/platform/services/session.h','runtime/platform/services/request.h','runtime/platform/player/managed.h','runtime/platform/player/provider.h','runtime/platform/player/player.h','tools/fixtures/service_session.c','tools/fixtures/service_request.c','tools/fixtures/service_player.c',Path(__file__).relative_to(ROOT).as_posix()]
report=dict(passed=True,private_core_only=True,host_sanitizers=True,original_libc_arm926_executed=True,sony_kernel_executed=False,device_accessed=False,public_sdk_exported=False,checks=checks,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
report['linked_library_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries.values()}
for p in ['runtime/store/deadline.c','runtime/store/deadline.h','tools/fixtures/player_host_clock.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
for p in ['runtime/store/start.c','runtime/store/start.S','tools/player_arm_guest.py']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
for p in ['runtime/platform/services/types.h','runtime/platform/player/managed_wire.h']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
cpp=out/'client-header.cpp';cpp.write_text('#include "managed_client.h"\nint (*entry)(xw_managed_client *,xw_session_snapshot *)=&xw_managed_client_status;\n')
subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-Iruntime/platform/player','-c',str(cpp),'-o',str(out/'client-header.o')],cwd=ROOT,check=True)
symbols=subprocess.check_output(['nm','-u',str(out/'client-header.o')],text=True);assert 'xw_managed_client_status' in symbols and '_Z' not in symbols
expanded=subprocess.check_output(['g++','-std=c++11','-Iruntime/platform/player','-E',str(cpp)],cwd=ROOT,text=True)
assert 'struct xw_session_manager' not in expanded and 'struct xw_request_ledger' not in expanded and 'struct xw_managed_player' not in expanded
report.update(client_header_cpp_linkage=True,client_header_excludes_server_objects=True)
for p in ['runtime/platform/services/events.h','tools/fixtures/service_events.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
for p in ['runtime/platform/player/managed_rpc.h','runtime/platform/player/rpc_wire.h','tools/fixtures/service_dispatch.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
report['source_hashes']['tools/fixtures/service_channel.c']=hashlib.sha256((ROOT/'tools/fixtures/service_channel.c').read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/managed_channel.h']=hashlib.sha256((ROOT/'runtime/platform/player/managed_channel.h').read_bytes()).hexdigest()
for p in ['runtime/platform/player/managed_control.h','tools/fixtures/service_control.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/managed_codec.h']=hashlib.sha256((ROOT/'runtime/platform/player/managed_codec.h').read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/snapshot.h']=hashlib.sha256((ROOT/'runtime/platform/player/snapshot.h').read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/managed_remote.h']=hashlib.sha256((ROOT/'runtime/platform/player/managed_remote.h').read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/managed_client.h']=hashlib.sha256((ROOT/'runtime/platform/player/managed_client.h').read_bytes()).hexdigest()
for p in ['runtime/platform/services/descriptor.h','tools/fixtures/service_descriptor.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
for p in ['runtime/platform/player/session_offer.h','tools/fixtures/service_offer.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
report['source_hashes']['tools/fixtures/service_quiesce.c']=hashlib.sha256((ROOT/'tools/fixtures/service_quiesce.c').read_bytes()).hexdigest()
for p in ['runtime/platform/player/service_drain.h','runtime/platform/player/player_broker.h','tools/fixtures/service_drain.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/drain_completion.h']=hashlib.sha256((ROOT/'runtime/platform/player/drain_completion.h').read_bytes()).hexdigest()
report['source_hashes']['runtime/platform/player/deferred_prepare.h']=hashlib.sha256((ROOT/'runtime/platform/player/deferred_prepare.h').read_bytes()).hexdigest()
for p in ['runtime/platform/player/managed_host.h','tools/fixtures/service_host.c']:report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
