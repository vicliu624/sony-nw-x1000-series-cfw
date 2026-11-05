"""Public player-client source module, original libc ARM926 and C++ headers."""
from pathlib import Path
import hashlib,json,time,subprocess
from app_registry import ROOT
from sdk_services import compile_native,inputs,resolve

def main():
 out=ROOT/'work/sdk-player-tests'/str(time.time_ns());out.mkdir(parents=True)
 definition=out/'player-check';definition.mkdir()
 modules=['startup','player-client']
 (definition/'app.json').write_text(json.dumps({'id':'player-check','target':'sony-nw-x1000-jp','sdk':{'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':modules}}))
 (definition/'VERSION').write_text('0.1.0-alpha.1\n')
 (definition/'main.c').write_text((ROOT/'sdk/tests/player.c').read_text())
 (definition/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[[]]}))
 artifact=compile_native(definition,definition/'build')
 example=out/'player-example';example.mkdir()
 info=json.loads((definition/'app.json').read_text());info['id']=example.name
 (example/'app.json').write_text(json.dumps(info))
 (example/'VERSION').write_text('0.1.0-alpha.1\n')
 sample=ROOT/'sdk/examples/player-client/main.c'
 (example/'main.c').write_text(sample.read_text())
 (example/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help']]}))
 example_artifact=compile_native(example,example/'build')
 managed=out/'player-managed-check';managed.mkdir()
 info['id']=managed.name;info['sdk']['modules']=['startup','player-managed-client']
 (managed/'app.json').write_text(json.dumps(info));(managed/'VERSION').write_text('0.1.0-alpha.1\n')
 managed_source=ROOT/'sdk/tests/player_managed.c'
 (managed/'main.c').write_text(managed_source.read_text())
 (managed/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[[]]}))
 managed_artifact=compile_native(managed,managed/'build')
 managed_example=out/'managed-example';managed_example.mkdir()
 info['id']=managed_example.name
 (managed_example/'app.json').write_text(json.dumps(info));(managed_example/'VERSION').write_text('0.1.0-alpha.1\n')
 managed_example_source=ROOT/'sdk/examples/player-managed-client/main.c'
 (managed_example/'main.c').write_text(managed_example_source.read_text())
 (managed_example/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help']]}))
 managed_example_artifact=compile_native(managed_example,managed_example/'build')
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(managed_example_source)],cwd=ROOT,check=True)
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(managed_source)],cwd=ROOT,check=True)
 from sdk_services import service_files
 managed_files=service_files(['player-managed-client'])
 assert not any(Path(p).name in ('managed.c','managed_channel.c','managed_rpc.c','managed_control.c','session.c','request.c','events.c','host_hook.c','stock_media.c') for p in managed_files)
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(sample)],cwd=ROOT,check=True)
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(ROOT/'sdk/tests/player.c')],cwd=ROOT,check=True)
 closure=inputs({'resolved_modules':resolve(modules)})
 assert ROOT/'runtime/platform/player/player.h' in closure and ROOT/'runtime/platform/player/rpc_wire.h' in closure
 assert not any(p.name in ('stock_media.c','stock_gui.c','host_hook.c') for p in closure)
 report=dict(passed=True,sdk_version=(ROOT/'sdk/VERSION').read_text().strip(),artifact=str(artifact.relative_to(ROOT)),public_consumer=True,original_libc_arm926=True,cpp_headers=True,client_only_source_closure=True,modeled_controls_notifications_browse=True,selection_admission_does_not_infer_playback=True,consumer_sha256=hashlib.sha256((ROOT/'sdk/tests/player.c').read_bytes()).hexdigest(),device_accessed=False,installed=False,limits=['The public client contract executes against a modeled provider; no stock service or device is contacted.'])
 report.update(example_artifact=str(example_artifact.relative_to(ROOT)),example_help_original_libc_arm926=True,example_cpp_syntax=True,example_sha256=hashlib.sha256(sample.read_bytes()).hexdigest(),example_live_endpoint_tested=False)
 report.update(managed_artifact=str(managed_artifact.relative_to(ROOT)),managed_public_consumer=True,managed_client_only_link=True,managed_cpp_headers=True,managed_consumer_sha256=hashlib.sha256(managed_source.read_bytes()).hexdigest())
 report.update(managed_example_artifact=str(managed_example_artifact.relative_to(ROOT)),managed_example_help_original_libc_arm926=True,managed_example_cpp_syntax=True,managed_example_live_endpoint_tested=False)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
