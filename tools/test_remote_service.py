"""Actual ARM service + actual player host; media and radio owner are models."""
import hashlib,json,os,subprocess,sys,time
from app_registry import ROOT
from build_remote_service import build, reviewed_service
from player_arm_guest import stock_libraries
all_modes='--all-play-modes' in sys.argv
mode_control='--play-mode-control' in sys.argv
mode_profile='--play-mode' in sys.argv or all_modes or mode_control
library_profile='--library' in sys.argv
out=ROOT/'work/remote-service-integration'/str(time.time_ns());out.mkdir(parents=True)
if '--service-review' in sys.argv:
 _,artifact,build_report=reviewed_service(sys.argv[sys.argv.index('--service-review')+1])
else:
 artifact,build_report=build(out/'service-build')
names=('client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock','managed_host','session_offer','service_drain','deferred_prepare')
sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['tools/fixtures/player_host_clock.c','tools/fixtures/managed_host_external.c']
server=out/'server'
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined',*(['-DXW_FIXTURE_PLAY_MODE'] if mode_profile else []),*(['-DXW_FIXTURE_MODE_CONTROL'] if mode_control else []),*(['-DXW_FIXTURE_ALL_PLAY_MODES'] if all_modes else []),*(['-DXW_FIXTURE_LIBRARY'] if library_profile else []),*sources,'-o',str(server)],cwd=ROOT,check=True)
libs=stock_libraries(include_rt=True)
command=[str(server),'--example-control',sys.executable,str(ROOT/'tools/fixtures/remote_service_owner.py'),
         'qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',
         ':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(artifact)]
run=subprocess.run(command,cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD',XW_FIXTURE_PLAY_MODE='1' if mode_profile else '0',XW_FIXTURE_MODE_CONTROL='1' if mode_control else '0',XW_FIXTURE_ALL_PLAY_MODES='1' if all_modes else '0',XW_FIXTURE_LIBRARY='1' if library_profile else '0'),capture_output=True,text=True,timeout=20)
assert run.returncode==0,run.stdout+run.stderr
assert all(marker in run.stdout for marker in ('REMOTE_SERVICE_READY','REMOTE_SERVICE_RETIRED startup_failure=0','REMOTE_SERVICE_OWNER_MODEL_PASS','PUBLIC_MANAGED_HOST_SERVER_PASS')),run.stdout
if mode_profile:assert 'REMOTE_SERVICE_MODE_MODEL_PASS' in run.stdout,run.stdout
if mode_control:assert all(s in run.stdout for s in ('REMOTE_SERVICE_FIVE_MODE_WRITES_PASS','PUBLIC_MANAGED_FIVE_MODE_WRITES_PASS')),run.stdout
if all_modes:assert 'REMOTE_SERVICE_ALL_FIVE_MODES_PASS' in run.stdout,run.stdout
if library_profile:assert 'MANAGED_LIBRARY_BUSY_THEN_READY_PASS' in run.stdout,run.stdout
report=dict(built=True,passed=True,artifact=artifact.relative_to(ROOT).as_posix(),bytes=build_report['bytes'],
            sha256=build_report['sha256'],original_libc_arm_entry_checks=True,
            actual_service_process=True,actual_player_host=True,host_sanitizers=True,player_backend_modeled=True,
            play_mode_query_exercised=mode_profile,
            all_five_modes_exercised=all_modes,
            all_five_mode_writes_exercised=mode_control,
            library_browse_busy_completion_exercised=library_profile,
            radio_owner_modeled=True,device_accessed=False,stdout=run.stdout,
            source_hashes={**build_report['source_hashes'],**{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_remote_service.py','tools/fixtures/remote_service_owner.py']}})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
