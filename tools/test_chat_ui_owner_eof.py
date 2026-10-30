"""Real UI reducer/client pipe EOF checks; no player or RF operation."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/chat-ui-owner-eof';OUT.mkdir(exist_ok=True)
(OUT/'chat_worker_identity.h').write_text('#define CHAT_WORKER_BYTES 1u\nstatic const unsigned char chat_worker_sha[32]={0};\n')
sources=['tools/fixtures/chat_ui_owner_eof.c','runtime/apps/espnow-chat/chat_client.c']
binary=OUT/'ui-eof.host'
subprocess.run(['gcc','-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(OUT),'-I'+str(ROOT/'sdk/include'),'-fsanitize=address,undefined','-g',*sources,'-o',str(binary)],cwd=ROOT,check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
assert run.returncode==0,run.stderr
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
arm=OUT/'ui-eof.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffunction-sections','-fdata-sections','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),'-I'+str(ROOT/'sdk/include'),*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
arm_run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,timeout=15)
assert arm_run.returncode==0,arm_run.stderr
report={'passed':run.returncode==0,'stdout':run.stdout,'stderr':run.stderr,'real_pipes_and_production_ui_parser':True,'device_accessed':False,'rf_mocked_not_executed':True,'launcher_forced_kill_qualified':False,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,'runtime/apps/espnow-chat/chat_app.c','runtime/apps/espnow-chat/chat_ipc.h']}}
report.update(arm926_stock_libc=arm_run.stdout,arm_sha256=hashlib.sha256(arm.read_bytes()).hexdigest())
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(run.returncode)
