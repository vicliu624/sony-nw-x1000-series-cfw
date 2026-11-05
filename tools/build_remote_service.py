"""Build the explicit-capability remote service; never deploys or starts RF."""
import hashlib,json,os,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries
out=ROOT/'work/remote-service-build'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/apps/wireless-remote/'+n+'.c' for n in
         ('service','worker','radio_retirement','status_sender','session_wire','player_status','link','status_auth','control','control_player','mode_wire','library_wire','library_player')]
sources+=['runtime/platform/player/'+n+'.c' for n in
          ('client','managed_remote','managed_client','managed_codec','managed_clock','rpc_wire')]
sources+=['runtime/platform/espnow/xnow_client.c','runtime/platform/espnow/xnow_handoff.c',
          'runtime/native/sha256.c','runtime/store/deadline.c','runtime/store/stock_fs_bridge.c',
          'runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
libs=stock_libraries(include_rt=True);artifact=out/'wireless-remote-service.arm'
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
       '-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
       '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector',
       '-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(libs['librt.so.1']),
                str(libs['libpthread.so.0']),str(libs['libc.so.6']),
                str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',
      ':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(artifact)]
env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
for args,expected in [(['--help'],0),([],64),(['--run','3','3','5','6','7'],64)]:
 run=subprocess.run(base+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
 assert run.returncode==expected,run.stdout+run.stderr
inputs=sources+['tools/build_remote_service.py']
inputs+=['runtime/platform/espnow/xnow_handoff.h','runtime/platform/espnow/xnow_client.h',
         'runtime/platform/espnow/xnow_mailbox.h','runtime/platform/player/player.h',
         'runtime/platform/player/provider.h','runtime/platform/player/managed_client.h',
         'runtime/platform/player/managed_remote.h','runtime/platform/player/managed_codec.h',
         'runtime/platform/services/types.h','runtime/store/target_abi.h',
         'runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h','runtime/native/sha256.h']
inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/apps/wireless-remote').glob('*.h')]
report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,
            sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),original_libc_arm_entry_checks=True,
            device_accessed=False,radio_started=False,live_capability_run_verified=False,
            linked_library_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in libs.values()},
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
