"""Full managed owner loop on real IPC/gate with synthetic RF and stock effects."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
power_off='--power-off' in sys.argv
mode_admission='--mode-admission' in sys.argv
assert not mode_admission or power_off
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-full-owner-runtime' if not power_off else ROOT/'work/remote-power-off-runtime'/str(time.time_ns());OUT.mkdir(parents=True,exist_ok=True)
namespace='-DXNOW_OWNER_GATE_NAMESPACE="x1000-xnow-full-owner-runtime-test-v1"'
sources=['tools/fixtures/full_owner_runtime.c','tools/fixtures/xnow_control_platform.c']+['runtime/platform/espnow/'+n+'.c' for n in ['xnow_owner_runtime','xnow_owner_gate','xnow_handoff_owner','xnow_owner_stream','xnow_owner_commands','xnow_owner_commands_control','xnow_full_control','xnow_session','xnow_manager','xnow_endpoint','xnow_peer','xnow_wire','xnow_full']]+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
host=OUT/'runtime.host'
defines=['-DXNOW_TEST_POWER_OFF'] if power_off else []
if power_off:sources+=['runtime/apps/wireless-remote/radio_stop.c','runtime/platform/wireless/radio_release.c','runtime/platform/espnow/xnow_power_off.c','runtime/platform/wireless/radio_modules.c']
extra=[];pthread=[]
if mode_admission:
 defines+=['-DXNOW_TEST_MODE_ADMISSION'];extra+=['-Wno-misleading-indentation','-pthread']
 sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_policy.c']
 from player_arm_guest import stock_libraries
 pthread=[str(stock_libraries()['libpthread.so.0'])]
subprocess.run(['gcc',namespace,*defines,*extra,'-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*sources,'-o',str(host)],cwd=ROOT,check=True)
native=subprocess.run([str(host)],capture_output=True,text=True,timeout=30)
if native.returncode:print(native.stdout,native.stderr);native.check_returncode()
LIB=ROOT/'work/arm-signal-tests/lib';arm=OUT/'runtime.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',namespace,*defines,*extra,'-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE=','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',*pthread,str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
target=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',':'.join(dict.fromkeys([str(LIB)]+[str(Path(p).parent) for p in pthread])),str(arm)],capture_output=True,text=True,timeout=60)
if target.returncode:print(target.stdout,target.stderr);target.check_returncode()
dependencies=[*sources,'tools/fixtures/full_owner_ipc.c','tools/test_xnow_full.c','runtime/platform/espnow/xnow_owner_runtime.h','runtime/platform/espnow/xnow_owner_gate.h','runtime/platform/espnow/xnow_owner_stream.h','runtime/platform/espnow/xnow_owner_commands.h','runtime/platform/espnow/xnow_full_control.h','tools/fixtures/xnow_control_platform.h']
report={'passed':True,'host_asan_ubsan':native.stdout,'arm926_stock_libc':target.stdout,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependencies},'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'real_pipes_and_gate_socket':True,'real_controller_endpoint_backend':True,'stock_driver_actions_mocked':True,'radio_transport_synthetic':True,'over_air_tested':False,'device_accessed':False,'installed':False}
report['power_off_policy']=power_off
report['mode_admission_retirement']=mode_admission
if mode_admission:
 assert 'MODE_REVOKE_RETIREMENT_PASS' in native.stdout and 'MODE_REVOKE_RETIREMENT_PASS' in target.stdout
 for p in ['runtime/apps/wireless-remote/owner_admission.h','runtime/platform/wireless/mode_client.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h']:
  report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
 report['linked_input_hashes']={str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in pthread}
for p in ['tools/test_full_owner_runtime.py']+(['runtime/apps/wireless-remote/radio_stop.h','runtime/platform/wireless/radio_release.h','runtime/platform/wireless/radio_modules.h','runtime/platform/espnow/xnow_power_off.h'] if power_off else []):report['source_hashes'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
