"""Actual read-only probe through startup rendezvous to model host; no device."""
import contextlib,hashlib,io,json,os,runpy,subprocess,time,sys
volume_mode="--volume" in sys.argv
observe_mode="--observe" in sys.argv
assert not (volume_mode and observe_mode)
from app_registry import ROOT
from player_arm_guest import stock_libraries
with contextlib.redirect_stdout(io.StringIO()):built=runpy.run_path(str(ROOT/'tools/build_player_live_probe.py'))
probe=built['artifact'];out=ROOT/'work/player-probe-startup'/str(time.time_ns());out.mkdir(parents=True)
names=('client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock','managed_host','session_offer','service_drain','deferred_prepare','startup_delivery')
sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['tools/fixtures/player_host_clock.c','tools/fixtures/managed_host_external.c']
server=out/'server'
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DXW_FIXTURE_STARTUP_PROBE','-fsanitize=address,undefined',*sources,'-o',str(server)],cwd=ROOT,check=True)
libs=stock_libraries(include_rt=True);paths=':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
directory='/tmp/x1000-player-probe-'+str(time.time_ns());nonce=os.urandom(16).hex()
run=subprocess.run([str(server),'--startup-volume-probe' if volume_mode else '--startup-observe-probe' if observe_mode else '--startup-probe','qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',paths,str(probe),directory,nonce,'23',*(['--volume-roundtrip'] if volume_mode else ['--observe'] if observe_mode else [])],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
assert run.returncode==0 and ('LIVE_PLAYER_VOLUME_PASS' if volume_mode else 'LIVE_PLAYER_READ_ONLY_PASS') in run.stdout and 'PUBLIC_MANAGED_HOST_SERVER_PASS' in run.stdout,run.stdout+run.stderr
if observe_mode:assert 'NOTIFICATION kind=1' in run.stdout and 'OBSERVE_COMPLETE notifications=1' in run.stdout,run.stdout
assert not os.path.exists(directory)
report=dict(passed=True,device_accessed=False,original_libc_arm_client=True,host_server_sanitizers=True,startup_handshake=True,read_grant_only=not volume_mode,control_calls=2 if volume_mode else 0,volume_roundtrip=volume_mode,observe_notifications=observe_mode,session_close_receipt=True,temporary_ipc_removed=True,stdout=run.stdout,probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/wireless-remote/probe.c','tools/test_player_probe_startup.py']},limits=['Server and Sony playback/media are models on the development computer.','This does not execute the real Sony GUI, its owner hook or the optional bootstrap exec path.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
