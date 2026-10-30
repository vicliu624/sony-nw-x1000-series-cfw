"""Public player-client source module, original libc ARM926 and C++ headers."""
from pathlib import Path
import json,time,subprocess
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
 subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(ROOT/'sdk/tests/player.c')],cwd=ROOT,check=True)
 closure=inputs({'resolved_modules':resolve(modules)})
 assert ROOT/'runtime/platform/player/player.h' in closure and ROOT/'runtime/platform/player/rpc_wire.h' in closure
 assert not any(p.name in ('stock_media.c','stock_gui.c','host_hook.c') for p in closure)
 report=dict(passed=True,sdk_version=(ROOT/'sdk/VERSION').read_text().strip(),artifact=str(artifact.relative_to(ROOT)),public_consumer=True,original_libc_arm926=True,cpp_headers=True,client_only_source_closure=True,device_accessed=False,installed=False)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
