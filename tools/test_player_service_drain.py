"""Real broker workers + service drain, host and original LinuxThreads ARM guest."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
host_wrapper='--host-wrapper' in sys.argv
bound_native_repeat='--bound-native-repeat' in sys.argv
assert not bound_native_repeat or host_wrapper
native_pending_view='--native-pending-view' in sys.argv
assert not native_pending_view or bound_native_repeat
clock_failure='--clock-failure' in sys.argv
exit_fault='--exit-fault' in sys.argv
native_exit_empty='--native-exit-empty' in sys.argv
inherited_delivery='--inherited-delivery' in sys.argv
exit_dependency='--exit-dependency' in sys.argv
user_stop_fault='--user-stop-fault' in sys.argv
settings_requests='--settings-requests' in sys.argv
user_toggle='--user-toggle' in sys.argv or user_stop_fault
assert not user_toggle or (host_wrapper and not any((exit_dependency,inherited_delivery,native_exit_empty,clock_failure,exit_fault)))
assert not settings_requests or (host_wrapper and not any((user_toggle,exit_dependency,inherited_delivery,native_exit_empty,clock_failure,exit_fault)))
assert not exit_dependency or (host_wrapper and not native_exit_empty and not clock_failure and not exit_fault)
assert not inherited_delivery or (host_wrapper and not native_exit_empty and not clock_failure and not exit_fault)
assert not clock_failure or host_wrapper
assert not exit_fault or (host_wrapper and not clock_failure)
assert not native_exit_empty or (host_wrapper and not clock_failure and not exit_fault)
out=ROOT/('work/player-host-managed-test' if host_wrapper else 'work/player-service-drain')/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/'+n+'.c' for n in ('client','managed','managed_rpc','managed_channel','managed_control','rpc_wire','player_broker','metadata_async','local_identity','service_drain')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events')]
sources+=['runtime/platform/player/drain_completion.c']
sources+=['runtime/platform/player/deferred_prepare.c']
sources+=['runtime/platform/player/managed_host.c','runtime/platform/player/session_offer.c','runtime/platform/services/descriptor.c']
if host_wrapper:sources+=['runtime/platform/player/host_managed_service.c']
if bound_native_repeat:sources+=['tools/fixtures/player_prepare_rf_bridge.c']
if inherited_delivery:sources+=['runtime/platform/player/host_inherited.c']
fixture='tools/fixtures/player_host_managed_service.c' if host_wrapper else 'tools/fixtures/player_service_drain_threads.c';init_source='tools/fixtures/player_worker_system_init.c'
flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if bound_native_repeat:flags+=['-DXW_HOST_BOUND_NATIVE_REPEAT']
if native_pending_view:flags+=['-DXW_HOST_NATIVE_PENDING_VIEW']
if clock_failure:flags+=['-DXW_HOST_CLOCK_FAILURE']
if exit_fault:flags+=['-DXW_HOST_EXIT_FAULT']
if native_exit_empty:flags+=['-DXW_HOST_NATIVE_EXIT_EMPTY']
if inherited_delivery:flags+=['-DXW_HOST_INHERITED_DELIVERY']
if exit_dependency:flags+=['-DXW_HOST_EXIT_DEPENDENCY']
if user_toggle:flags+=['-DXW_HOST_USER_TOGGLE']
if user_stop_fault:flags+=['-DXW_HOST_USER_STOP_FAULT']
if settings_requests:flags+=['-DXW_HOST_SETTINGS_REQUESTS']
host=out/'host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined','-pthread',*sources,fixture,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=15);assert run.returncode==0,run.stdout+run.stderr
libs=stock_libraries();startup=['runtime/store/start.c','runtime/store/start.S']
arm_flags=[*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
app=out/'test.arm';init=out/'init.arm'
for output,code in ((app,[*sources,fixture]),(init,[init_source])):
 subprocess.run(['arm-linux-gnueabi-gcc',*arm_flags,*code,*startup,str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(output)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':app},libs,['PLAYER_HOST_MANAGED_SERVICE_PASS' if host_wrapper else 'PLAYER_SERVICE_DRAIN_THREADS_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
paths=sources+startup+[fixture,init_source,'tools/fixtures/player_broker.c',Path(__file__).relative_to(ROOT).as_posix()]+[p.relative_to(ROOT).as_posix() for folder in ('runtime/platform/player','runtime/platform/services') for p in (ROOT/folder).glob('*.h')]
if bound_native_repeat:paths+=['runtime/platform/player/host_prepare_bridge.c']
report.update(host_sanitizers=True,real_blocked_workers=True,production_broker_and_service_drain=True,original_linuxthreads=True,moma_and_original_player_modeled=True,host_stdout=run.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(paths))},limits=['Generic ARM kernel, not Sony kernel/hardware.','Two actual reader threads hold modeled native handles until released by the fixture.','No original pending-table hook, library finalization or USB/sleep handshake executes.'])
report['managed_host_wrapper']=host_wrapper
report['exit_dependency_fixture']=exit_dependency
report['user_toggle_fixture']=user_toggle
report['user_stop_fault_fixture']=user_stop_fault
report['settings_requests_fixture']=settings_requests
report['inherited_delivery']=inherited_delivery
report['clock_failure_fixture']=clock_failure
report['exit_fault_fixture']=exit_fault
report['native_exit_empty_fixture']=native_exit_empty
if exit_fault:report['limits'].append('Exit fault retains SDK objects and suppresses native continuation; process exit is not evidence of graceful service drain.')
if host_wrapper:
 report['real_blocked_workers']=False;report['real_worker_threads']=True
 report['limits'][1]='Actual reader threads use modeled native handles and fixture delays; no explicit condition gate in this profile.'
 report['limits']+=['Real host dispatch/offer/prepare API and broker execute; original queue/source attachment and media/backend are models. No listener, original-manager policy or native hook is installed.']
if native_exit_empty:
 report['real_worker_threads']=False;report['production_broker_and_service_drain']=False
 report['limits']=['No-resource native-exit admission/factory decision executes under the actual host wrapper; no SDK broker or worker starts.','Original native exit event and backend are modeled; no installed dispatcher or physical qualification.']
if settings_requests:
 report['real_worker_threads']=False;report['production_broker_and_service_drain']=False
 report['foreign_owner_probe_thread']=True
 report['limits']=['Actual private Settings queue/bind/result/cancel code executes; request backend and original player are modeled.',
                   'One foreign-owner probe thread is created/joined; no metadata/catalog worker, broker drain or RF owner starts.',
                   'Request delivery result is not radio status; no original GUI, power transition or device access.']
if bound_native_repeat:
 report['native_pending_view']=native_pending_view
 report['bound_native_repeat_fixture']=True
 report['real_worker_threads']=False;report['real_blocked_workers']=False;report['production_broker_and_service_drain']=False
 report['limits']=['Actual managed-service and RF-enabled prepare bridge execute on host sanitizers and ARM/Sony libc.',
  'Initialized provider, Root/image validation and verified-OFF radio response are fixtures; no actual radio owner, GUI or physical ordering executes.',
  'Repeated empty exit uses the same epoch and keeps admission closed; subsequent RF refusal suppresses native fallback.']
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print((out/'serial.log').read_text(errors='replace')[-900:]);print(json.dumps(report,indent=2));assert report['passed'],(out/'qemu.log').read_text(errors='replace')[-1000:]
