"""External public-SDK ARM client against separate host managed server; no device."""
from pathlib import Path
import hashlib,json,os,subprocess,time,sys
from app_registry import ROOT
from sdk_services import compile_native
from player_arm_guest import stock_libraries
example_mode='--managed-example' in sys.argv
host_mode='--managed-host' in sys.argv or example_mode
out=ROOT/('work/sdk-managed-host' if host_mode else 'work/sdk-managed-channel')/str(time.time_ns());out.mkdir(parents=True)
app=out/'external-managed';app.mkdir();version=(ROOT/'sdk/VERSION').read_text().strip()
(app/'app.json').write_text(json.dumps({'id':app.name,'target':'sony-nw-x1000-jp','sdk':{'version':version,'profile':'native-services','modules':['startup','player-managed-client']}}))
(app/'VERSION').write_text('0.1.0-alpha.1\n');consumer=ROOT/('sdk/examples/player-managed-client/main.c' if example_mode else 'sdk/tests/player_managed_channel.c')
(app/'main.c').write_text(consumer.read_text());(app/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help']]}))
binary=compile_native(app,app/'build')
subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(consumer)],cwd=ROOT,check=True)
names=['client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock']
sources=['runtime/platform/player/'+n+'.c' for n in names]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events')]+['tools/fixtures/player_host_clock.c','tools/fixtures/managed_host_external.c' if host_mode else 'tools/fixtures/service_channel.c']
if host_mode:sources+=['runtime/platform/player/'+n+'.c' for n in ('managed_host','session_offer','service_drain','deferred_prepare')]+['runtime/platform/services/descriptor.c']
server=out/'server';subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',*sources,'-o',str(server)],cwd=ROOT,check=True)
libs=stock_libraries(include_rt=True);paths=':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
command=[str(server),*(['--example-read'] if example_mode else []),'qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',paths,str(binary),*(['--fd','3','--generation','23','snapshot'] if example_mode else ['--host-channel' if host_mode else '--channel','3'])]
run=subprocess.run(command,cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
assert run.returncode==0,run.stdout+run.stderr
if example_mode:assert 'title=Channel song' in run.stdout and 'volume=12 range=0..30' in run.stdout
else:assert 'PUBLIC_MANAGED_ARM_CHANNEL_PASS' in run.stdout
if host_mode:assert 'PUBLIC_MANAGED_HOST_SERVER_PASS' in run.stdout
example_checks=[]
if example_mode:
 cases=[(['watch','2'],'title=Channel song',False),(['tracks','0'],'model:42',False),(['playlists','0'],'model:playlist',False),(['members','model:playlist','0'],'model:42',False),(['queue','0'],'model:42',False),(['pause'],'ACCEPTED:',True)]
 for arguments,expected,control in cases:
  invocation=command[:-1]+arguments
  invocation[1]='--example-watch' if arguments[0]=='watch' else '--example-control' if control else '--example-read'
  checked=subprocess.run(invocation,cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
  assert checked.returncode==0 and expected in checked.stdout and 'PUBLIC_MANAGED_HOST_SERVER_PASS' in checked.stdout,checked.stdout+checked.stderr
  if arguments[0]=='watch':assert 'state=2' in checked.stdout and checked.stdout.count('title=Channel song')==2,checked.stdout
  example_checks.append(dict(arguments=arguments,passed=True,stdout=checked.stdout))
report=dict(passed=True,sdk_version=version,external_public_sdk_arm_client=True,separate_host_server=True,original_client_loader_libc=True,host_server_sanitizers=True,cpp_consumer=True,managed_backend_modeled=True,device_accessed=False,firmware_created=False,stdout=run.stdout,client_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),server_sha256=hashlib.sha256(server.read_bytes()).hexdigest(),source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+[str(consumer.relative_to(ROOT)),'tools/test_sdk_managed_channel.py']})
report['managed_host']=host_mode
report['managed_example']=example_mode
report['managed_example_checks']=example_checks
report['limits']=['Server runs on the host, client under qemu-arm with original loader/libraries; Sony kernel and hardware are not executed.','Playback state, media rows and broker-close effects are modeled; no installed provider or original-manager authorization.']
if host_mode:report['limits'].append('Trusted launch shim receives SCM_RIGHTS and explicitly preserves only the approved child descriptor across exec; it is not a production app-manager policy.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
