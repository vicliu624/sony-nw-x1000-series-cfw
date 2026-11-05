"""Client-only radio transport against actual owner stream, RF modeled; no device."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
from sdk_services import service_files, manifest
client_sources=service_files(['espnow-client'])
assert [p for p in client_sources if p.startswith('runtime/platform/espnow/')]==['runtime/platform/espnow/xnow_client.c'], client_sources
assert manifest()['espnow-client']['exports']['espnow_client.h']=='runtime/platform/espnow/xnow_client.h'
out=ROOT/'work/espnow-client-tests'/str(time.time_ns());out.mkdir(parents=True)
sources=['tools/test_xnow_client.c']+['runtime/platform/espnow/'+n+'.c' for n in ('xnow_client','xnow_owner_stream','xnow_owner_commands','xnow_endpoint','xnow_peer','xnow_wire','xnow_full')]+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
sources+=['runtime/apps/wireless-remote/'+n+'.c' for n in ('link','player_status','status_auth','receiver','status_sender','session_wire','control','control_player','mode_wire','library_wire','library_player')]+['runtime/native/sha256.c','runtime/platform/player/client.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wl,--wrap=read,--wrap=write']
host=out/'client.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,timeout=20);assert run.returncode==0,run.stdout+run.stderr
libs=stock_libraries();arm=out/'client.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
checked=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm)],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20);assert checked.returncode==0,checked.stdout+checked.stderr
headers=['runtime/apps/wireless-remote/'+n+'.h' for n in ('link','player_status','status_auth','receiver','status_sender','session_wire','control','library_wire','library_player')]
report=dict(passed=True,device_accessed=False,host_sanitizers=True,original_libc_arm926=True,actual_client_and_owner_stream=True,application_status_sender_receiver=True,player_provider_modeled=True,radio_modeled=True,hardware_power_off_proven=False,stdout=checked.stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+headers+['tools/test_xnow_client.py','runtime/platform/espnow/xnow_client.h','runtime/platform/player/player.h','runtime/platform/player/provider.h','runtime/native/sha256.h']})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
