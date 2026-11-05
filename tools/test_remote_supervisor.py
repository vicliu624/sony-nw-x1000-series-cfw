"""Full native supervisor/service chain in an isolated ARM guest; RF/media modeled."""
import contextlib,hashlib,io,json,runpy,struct,subprocess,sys,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
out=ROOT/'work/remote-supervisor-integration'/str(time.time_ns());out.mkdir(parents=True)
reusable='--reusable-sessions' in sys.argv
bad_generation='--bad-generation' in sys.argv
bad_grants='--bad-grants' in sys.argv
assert not (bad_generation and bad_grants)
direct_delivery='--direct-delivery' in sys.argv or bad_generation or bad_grants
managed_process='--managed-process' in sys.argv
automatic_factory='--automatic-factory' in sys.argv
owner_view_forward='--owner-view-forward' in sys.argv
assert not owner_view_forward or automatic_factory
real_owner_refusal='--real-owner-startup-refusal' in sys.argv
assert not real_owner_refusal or (owner_view_forward and '--sleep-retirement' not in sys.argv)
real_owner_managed='--real-owner-managed' in sys.argv
assert not real_owner_managed or real_owner_refusal
formal_data_layout='--formal-data-layout' in sys.argv
assert not formal_data_layout or real_owner_managed
sleep_retirement='--sleep-retirement' in sys.argv
assert not sleep_retirement or automatic_factory
settings_factory='--settings-factory' in sys.argv or automatic_factory
settings_backend='--settings-backend' in sys.argv or settings_factory
native_page_chain='--native-page-chain' in sys.argv
assert not native_page_chain or (settings_backend and not settings_factory)
if settings_factory:reusable=True
rf_admission='--rf-admission' in sys.argv
assert not rf_admission or settings_backend
early_stop='--early-stop' in sys.argv
mode_switch='--mode-switch' in sys.argv
assert not mode_switch or (settings_backend and not early_stop)
assert not native_page_chain or not any((mode_switch,early_stop,rf_admission,bad_generation,bad_grants))
assert not early_stop or settings_backend
assert not settings_factory or not any((bad_generation,bad_grants,early_stop,mode_switch,rf_admission))
if settings_backend:managed_process=True
if managed_process:direct_delivery=True
with contextlib.redirect_stdout(io.StringIO()):service=runpy.run_path(str(ROOT/'tools/build_remote_service.py'))
libs=stock_libraries(include_rt=True)
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK',
       '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin',
       '-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none']
startup=['runtime/store/start.c','runtime/store/start.S']
linked=[str(libs[n]) for n in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]
def compile(sources,target,extra=()):subprocess.run(['arm-linux-gnueabi-gcc',*flags,*extra,*sources,*startup,*linked,'-lgcc','-o',str(target)],cwd=ROOT,check=True)
owner=out/'owner.arm';owner_sources=['tools/fixtures/remote_chain_owner.c','runtime/apps/wireless-remote/control.c','runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/status_auth.c','runtime/native/sha256.c','runtime/store/deadline.c']
owner_flags=['-DWR_CHAIN_BROKER_MODEL','-DWR_CHAIN_MANUAL_STOP'] if settings_backend else []
if early_stop:owner_flags+=['-DWR_CHAIN_ALLOW_EMPTY_STOP']
if reusable:owner_flags+=['-DWR_CHAIN_DYNAMIC_SESSION']
if owner_view_forward:
 owner_flags+=['-DWR_CHAIN_OWNER_VIEW']
 owner_sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
real_owner_report=None
if real_owner_refusal:
 saved_owner_args=sys.argv
 try:
  sys.argv=['build_remote_owner.py','--power-off-exit','--mode-view-required']+(['--managed-session'] if real_owner_managed else ['--window-seconds','180'])
  if formal_data_layout:sys.argv+=['--data-leaf','wireless-remote']
  with contextlib.redirect_stdout(io.StringIO()):real_owner=runpy.run_path(str(ROOT/'tools/build_remote_owner.py'))
 finally:sys.argv=saved_owner_args
 owner=real_owner['artifact'];real_owner_report=real_owner['report'];owner_sources=[]
 libs['libcnmgr.so.1']=ROOT/'work/stock-resolver-probe/libcnmgr.so.1'
else:compile(owner_sources,owner,owner_flags)
generation=1 if automatic_factory else 41 if settings_backend else 23
template_generation=40 if automatic_factory else generation-1 if reusable else generation
config=out/'config.bin';config.write_bytes(b'XWRUN001'+struct.pack('<QQ',template_generation,1234567)+bytes([2,1,2,3,4,5])+b'\0\0'+bytes(range(1,33))+bytes(range(16)))
review=dict(generation=template_generation,device_directory='/contents/HOMEBREW/data/wireless-remote/runtime' if formal_data_layout else '/contents/HOMEBREW/data/player-sdk-live-1/remote',files={})
if owner_view_forward:review['owner_mode_view_supported']=True
for name,path in [('service',service['artifact']),('owner',owner),('config',config)]:review['files'][name]=dict(local=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
review_path=out/'review.private.json';review_path.write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
saved=sys.argv
try:
 sys.argv=['build_remote_supervisor.py','--review',str(review_path)]+(['--reusable-sessions'] if reusable else [])+(['--forward-owner-mode-view'] if owner_view_forward else [])
 with contextlib.redirect_stdout(io.StringIO()):supervisor=runpy.run_path(str(ROOT/'tools/build_remote_supervisor.py'))
finally:sys.argv=saved
names=('client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock','managed_host','session_offer','service_drain','deferred_prepare','startup_delivery')
server_sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['runtime/store/deadline.c','tools/fixtures/managed_host_external.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
server_flags=['-DXW_FIXTURE_STARTUP_PROBE']
if managed_process:
 server_sources+=['runtime/apps/wireless-remote/supervisor_process.c']
 server_flags+=['-DXW_FIXTURE_MANAGED_PROCESS','-DWR_SUPERVISOR_PATH="/supervisor"']
if settings_backend:
 names=('client','managed','managed_rpc','managed_channel','managed_control','rpc_wire','player_broker','metadata_async','local_identity','service_drain','drain_completion','deferred_prepare','managed_host','session_offer','host_managed_service')
 server_sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]
 server_sources+=['runtime/apps/wireless-remote/settings_backend.c','runtime/apps/wireless-remote/native_page_bridge.c','runtime/apps/wireless-remote/supervisor_process.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/fixtures/settings_backend_chain.c']
if native_page_chain:
 server_sources=[p for p in server_sources if p!='tools/fixtures/settings_backend_chain.c']
 server_sources+=['tools/fixtures/native_page_backend_chain.c']
 server_sources+=['runtime/apps/wireless-remote/native_page.c']
 server_flags+=['-DWR_NATIVE_PAGE_CHAIN']
if settings_factory:
 server_sources=[p for p in server_sources if p!='tools/fixtures/settings_backend_chain.c']
 server_sources+=['runtime/apps/wireless-remote/settings_factory.c','runtime/platform/player/wireless_host.c','runtime/platform/wireless/native_publisher.c','runtime/platform/wireless/mode_channel.c','tools/fixtures/settings_factory_chain.c']
 server_sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c']
 server_flags+=['-DXW_PLAYER_NATIVE_RF']
if automatic_factory:
 (out/'remote_factory_profile.h').write_text('#define WR_REMOTE_SUPERVISOR_BYTES '+str(supervisor['artifact'].stat().st_size)+'u\n'+('#define WR_REMOTE_OWNER_VIEW\n' if owner_view_forward else ''))
 server_flags+=['-DWR_SETTINGS_AUTO_TEST','-I'+str(out)]
if sleep_retirement:
 server_sources+=['runtime/platform/player/sleep_retirement.c','runtime/platform/player/sleep_host.c']
 server_flags+=['-DWR_SETTINGS_SLEEP_RETIREMENT']
if real_owner_refusal:server_flags+=['-DWR_REAL_OWNER_REFUSAL']
if early_stop:server_flags+=['-DWR_SETTINGS_EARLY_STOP']
if mode_switch:server_flags+=['-DWR_SETTINGS_MODE_SWITCH']
if rf_admission:server_flags+=['-DXW_PLAYER_NATIVE_RF','-DWR_SETTINGS_ADMISSION_TEST']
if reusable and settings_backend and not mode_switch and not early_stop:server_flags+=['-DWR_SETTINGS_RESTART']
server=out/'server.arm';compile(server_sources,server,server_flags)
init_flags=['-DXW_DIRECT_REMOTE'] if direct_delivery else []
if formal_data_layout:init_flags+=['-DXW_FORMAL_REMOTE_LAYOUT']
if bad_generation:init_flags+=['-DXW_DIRECT_BAD_GENERATION']
if bad_grants:init_flags+=['-DXW_DIRECT_BAD_GRANTS']
init=out/'init.arm';compile(['tools/fixtures/remote_chain_init.c'],init,init_flags)
markers=['REMOTE_DIRECT_REJECTION_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0'] if bad_generation or bad_grants else ['REMOTE_CHAIN_OWNER_STARTED','REMOTE_SUPERVISOR_CHILDREN service=0 owner=0','REMOTE_SERVICE_RETIRED startup_failure=0','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0']
markers.append('REMOTE_CONFIG_UNCHANGED')
if real_owner_refusal:
 markers=['REMOTE_RF_MODE_VIEW_AUTHORIZED','REMOTE_SUPERVISOR_CHILDREN service=1 owner=69','REMOTE_SUPERVISOR_START_REFUSAL_RETIRED','REMOTE_SERVICE_RETIRED startup_failure=1','FACTORY_START_REFUSAL_RETRY_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS','REMOTE_CHAIN_CHILD_STATUS=0','REMOTE_CONFIG_UNCHANGED']
report=run_guest(out,init,{'test':server,'supervisor':supervisor['artifact'],'stage/service.arm':service['artifact'],'stage/owner.arm':owner,'stage/config.bin':config},libs,
                 markers,timeout=25)
if native_page_chain:assert 'NATIVE_PAGE_BACKEND_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
elif settings_backend and not real_owner_refusal:assert 'SETTINGS_BACKEND_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
if reusable and native_page_chain:assert 'NATIVE_PAGE_GENERATION_STALE_PASS' in (out/'serial.log').read_text(errors='replace')
elif reusable and settings_backend and not mode_switch and not early_stop and not real_owner_refusal:assert 'SETTINGS_BACKEND_RESTART_PASS' in (out/'serial.log').read_text(errors='replace')
if settings_factory and not real_owner_refusal:assert 'SETTINGS_FACTORY_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
if settings_factory and not real_owner_refusal:assert (out/'serial.log').read_text(errors='replace').count('FACTORY_OWNER_VIEW_PASS') >= (2 if sleep_retirement else 1)
if sleep_retirement:
 assert 'SLEEP_RETIREMENT_CHAIN_PASS' in (out/'serial.log').read_text(errors='replace')
 assert 'SLEEP_REMOTE_RESTART_PASS' in (out/'serial.log').read_text(errors='replace')
if owner_view_forward and not real_owner_refusal:assert (out/'serial.log').read_text(errors='replace').count('REMOTE_CHAIN_MODE_VIEW_PASS') >= (4 if sleep_retirement else 3)
if real_owner_refusal:
 serial=(out/'serial.log').read_text(errors='replace');assert 'REMOTE_RF_OWNER_STARTING' not in serial
 assert serial.count('REMOTE_SUPERVISOR_START_REFUSAL_RETIRED')>=2 and 'startup_failure=1' in serial
if rf_admission:assert 'SETTINGS_BACKEND_ADMISSION_PASS' in (out/'serial.log').read_text(errors='replace')
if bad_generation or bad_grants:
 assert 'REMOTE_SUPERVISOR_CHILDREN' not in (out/'serial.log').read_text(errors='replace')
 assert 'REMOTE_CHAIN_OWNER_STARTED' not in (out/'serial.log').read_text(errors='replace')
inputs=owner_sources+server_sources+['tools/fixtures/remote_chain_init.c','tools/test_remote_supervisor.py']
if managed_process:inputs+=['runtime/apps/wireless-remote/supervisor_process.h']
if automatic_factory:inputs+=['runtime/platform/player/remote_auto.c','runtime/platform/player/remote_ready.h']
if sleep_retirement:inputs+=['runtime/platform/player/sleep_retirement.h','runtime/platform/player/sleep_host.h']
if settings_factory:inputs+=['runtime/apps/wireless-remote/settings_factory.h','runtime/apps/wireless-remote/owner_admission.h','runtime/platform/player/wireless_host.h','runtime/platform/wireless/native_publisher.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_client.h','runtime/platform/services/session.h']
if settings_backend:inputs+=['runtime/apps/wireless-remote/settings_backend.h','runtime/platform/wireless/mode.h','runtime/platform/wireless/mode_policy.h','runtime/platform/player/host_managed_service.h','tools/fixtures/player_host_managed_service.c','tools/fixtures/player_broker.c']
if settings_backend:inputs+=['runtime/apps/wireless-remote/native_page.h','runtime/apps/wireless-remote/native_page_bridge.h']
if native_page_chain:inputs=[p for p in inputs if p!='tools/fixtures/settings_backend_chain.c']
report.update(built=True,native_page_chain=native_page_chain,artifact=supervisor['artifact'].relative_to(ROOT).as_posix(),bytes=supervisor['artifact'].stat().st_size,
              native_page_generation_refusal_checked=native_page_chain and reusable,
              sha256=hashlib.sha256(supervisor['artifact'].read_bytes()).hexdigest(),original_libc_arm_entry_checks=True,
              actual_supervisor=True,actual_service=not (bad_generation or bad_grants),actual_player_host=True,radio_owner_modeled=not real_owner_refusal,player_backend_modeled=True,
              actual_real_owner=real_owner_refusal,real_owner_startup_refusal_checked=real_owner_refusal,
              real_owner_managed=real_owner_managed,
              formal_data_layout=formal_data_layout,
              direct_delivery=direct_delivery,reusable_sessions=reusable,runtime_generation=generation,template_generation=template_generation,
              managed_process_launcher=managed_process,
              actual_settings_backend=settings_backend,actual_settings_factory=settings_factory,foreign_generation_isolation_checked=settings_factory and not real_owner_refusal,cooperative_native_exit_checked=settings_factory and not real_owner_refusal,automatic_factory=automatic_factory,inactive_player_admission=rf_admission,
              factory_owner_view_checked=settings_factory,
              owner_view_forwarded=owner_view_forward,
              early_stop=early_stop,
              actual_sleep_retirement=sleep_retirement,native_sleep_ack_modeled=sleep_retirement,
              sleep_remote_restart_checked=sleep_retirement,native_recovery_evidence_modeled=sleep_retirement,
              system_mode_change=mode_switch,
              actual_mode_policy=settings_backend,mode_policy_evidence_modeled=settings_backend,
              rejects_bad_generation=bad_generation,rejects_bad_grants=bad_grants,
              device_accessed=False,source_hashes={**(real_owner_report['source_hashes'] if real_owner_report else {}),**service['report']['source_hashes'],**supervisor['report']['source_hashes'],**{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs}})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
assert report['passed'],(out/'serial.log').read_text(errors='replace')[-6000:]
print(json.dumps(report,indent=2))
