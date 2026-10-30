"""Public client -> real local IPC -> actual broker/readers; native rows modeled."""
from pathlib import Path
import hashlib,json,os,selectors,subprocess,sys
from app_registry import ROOT
native_queue='--native-queue' in sys.argv
w=ROOT/('work/player-broker-rpc-queue' if native_queue else 'work/player-broker-rpc');w.mkdir(exist_ok=True)
common=['runtime/platform/player/client.c','runtime/platform/player/rpc_wire.c','runtime/platform/player/rpc_posix.c','tools/fixtures/player_host_clock.c']
server_sources=common+['runtime/platform/player/local_identity.c','runtime/platform/player/metadata_async.c','runtime/platform/player/player_broker.c','tools/fixtures/player_broker_rpc_server.c']
client_sources=common+['tools/fixtures/player_broker_rpc_client.c']
if native_queue:
 server_sources += ['runtime/platform/player/'+name+'.c' for name in ('host_queue','queue_browser','queue_exchange','queue_async','group_native','group_reader','queue_capture','queue_page','query_snapshot')]

flags=['-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-pthread','-I'+str(ROOT/'sdk/include')]
if native_queue:flags+=['-DXW_TEST_NATIVE_QUEUE']
server=w/'server';client=w/'client'
for output,sources in ((server,server_sources),(client,client_sources)):subprocess.run(['gcc-12',*flags,*sources,'-o',str(output)],cwd=ROOT,check=True)
endpoint='xw-broker-rpc-'+str(os.getpid());process=subprocess.Popen([str(server),endpoint],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
 selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);assert selector.select(5),'Server readiness timeout';assert process.stdout.readline().strip()=='READY'
 consumer=subprocess.run([str(client),endpoint],capture_output=True,text=True,timeout=15);assert consumer.returncode==0,consumer.stdout+consumer.stderr
 process.terminate();stdout,stderr=process.communicate(timeout=5);assert process.returncode==0,stdout+stderr;assert 'CLEAN:' in stdout
finally:
 if process.poll() is None:process.kill();process.communicate()
headers=['sdk/VERSION','sdk/services.json','sdk/include/x1000/services/player.h','sdk/include/x1000/services/player_remote.h']+['runtime/platform/player/'+name+'.h' for name in ('player','provider','rpc_wire','rpc_posix','player_broker','metadata_async','stock_media','local_identity')]
if native_queue:headers += ['runtime/platform/player/'+name+'.h' for name in ('host_queue','host_hook','queue_browser','queue_exchange','queue_async','group_native','group_reader','queue_capture','queue_page','query_snapshot','stock_queue_owner','session_identity','stock_info')]
report=dict(passed=True,public_sdk_headers=True,separate_processes=True,real_local_ipc=True,actual_broker=True,native_queue_pipeline=native_queue,real_host_workers=True,host_sanitizers=True,native_player_and_rows_modeled=True,device_accessed=False,server_sha256=hashlib.sha256(server.read_bytes()).hexdigest(),client_sha256=hashlib.sha256(client.read_bytes()).hexdigest(),client_stdout=consumer.stdout,server_stdout=stdout,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(server_sources+client_sources+headers+['tools/fixtures/player_broker.c','tools/fixtures/player_native_queue_model.h','tools/test_player_broker_rpc.py']))},limits=['This joins the production SDK/client/RPC/broker/worker code on the host; original player control and database values are modeled.','Original native instructions and original-libc ARM IPC have separate fixtures; no physical endpoint or SonicStage compatibility is qualified.','With --native-queue the production host adapter, session filtering, capture coordinator, exchange and queue workers execute; native session and database boundaries are modeled.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
