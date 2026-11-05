"""Public SDK IPC and production workers in a generic ARM kernel/original libc."""
from pathlib import Path
import hashlib,json,subprocess
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
w=ROOT/'work/player-broker-system';w.mkdir(exist_ok=True);libraries=stock_libraries(include_rt=True)
startup=['runtime/store/start.c','runtime/store/start.S']
common=['runtime/platform/player/'+n+'.c' for n in ('client','rpc_wire','rpc_posix')]+['runtime/store/deadline.c']
server_sources=common+['runtime/platform/player/'+n+'.c' for n in ('local_identity','metadata_async','player_broker','source_service','source_intent','audio_check_async')]+['tools/fixtures/player_broker_rpc_server.c']
client_sources=common+['tools/fixtures/player_broker_rpc_client.c'];init_source='tools/fixtures/player_broker_system_init.c'
flags=['arm-linux-gnueabi-gcc','-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_LIBC_CLOCK','-DXW_TEST_SOURCE','-DXW_TEST_PUBLIC_EXAMPLE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(ROOT/'sdk/include')]
links=[str(libraries[n]) for n in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]
server=w/'server.arm';client=w/'client.arm';init=w/'init.arm'
example=w/'example.arm';example_sources=common+['sdk/examples/player-client/main.c']
for output,sources in ((server,server_sources),(client,client_sources),(init,[init_source]),(example,example_sources)):
 subprocess.run([*flags,*sources,*startup,*links,'-lgcc','-o',str(output)],cwd=ROOT,check=True)
markers=['PLAYER_SYSTEM_SERVER_READY','PLAYER_SYSTEM_PUBLIC_EXAMPLE_PASS','Selection pipeline: negotiated capability','End-to-end public SDK client:','CLEAN: endpoint closed','PLAYER_SYSTEM_CLIENT_STATUS=0 SERVER_STATUS=0','PLAYER_SYSTEM_IPC_PASS']
report=run_guest(w,init,{'server':server,'client':client,'example':example},libraries,markers)
inputs=sorted(set(server_sources+client_sources+example_sources+startup+[init_source,'tools/fixtures/player_broker.c',Path(__file__).relative_to(ROOT).as_posix()]+[p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/player').glob('*.h')]+['runtime/store/deadline.h','sdk/include/x1000/services/player.h','sdk/include/x1000/services/player_remote.h']))
report.update(public_sdk_headers=True,separate_guest_processes=True,original_socket_ipc=True,original_linuxthreads=True,production_broker_source_and_workers=True,native_player_media_gui_modeled=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},limits=['Original Sony libc/loader/librt/LinuxThreads execute under generic ARM Linux2.6.32, not Sony hardware/kernel.','Public client, IPC, broker, selection adapter/intent and readers execute; native GUI/media/audio completion and catalog rows are modeled.','No SpiderApp startup, physical endpoint, audio decoding, APF, sleep or USB qualification.'])
report['public_example_controls_and_watch_original_libc_ipc']=report['passed']
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print((w/'serial.log').read_text(errors='replace')[-2000:]);print(json.dumps(report,indent=2));assert report['passed'],(w/'qemu.log').read_text(errors='replace')[-1000:]
