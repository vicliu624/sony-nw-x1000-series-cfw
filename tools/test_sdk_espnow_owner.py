"""Public owner SDK consumer with original libc/ARM926, no device access."""
from pathlib import Path
import json,time,subprocess
from app_registry import ROOT
from sdk_services import compile_native
def main():
    out=ROOT/'work/sdk-espnow-owner-tests'/str(time.time_ns());out.mkdir(parents=True)
    definition=out/'espnow-owner-check';definition.mkdir()
    (definition/'app.json').write_text(json.dumps({'id':'espnow-owner-check','target':'sony-nw-x1000-jp','sdk':{'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':['startup','espnow-owner']}}))
    (definition/'VERSION').write_text('0.1.0-alpha.1\n');(definition/'main.c').write_text((ROOT/'sdk/tests/espnow_owner.c').read_text());(definition/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[[]]}))
    artifact=compile_native(definition,definition/'build')
    # C++ public declarations must stay usable without compiling C runtime as C++.
    subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'sdk/include'),'-x','c++','-fsyntax-only',str(ROOT/'sdk/tests/espnow_owner.c')],cwd=ROOT,check=True)
    report={'passed':True,'sdk_version':(ROOT/'sdk/VERSION').read_text().strip(),'artifact':str(artifact.relative_to(ROOT)),'public_service_consumer':True,'old_sony_libc_arm926':True,'cpp_header_syntax':True,'device_accessed':False,'installed':False}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
