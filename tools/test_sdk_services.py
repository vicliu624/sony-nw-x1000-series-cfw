"""Compile and execute an external custom-main client against public SDK services."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zlib
from app_registry import ROOT
from sdk import create

def fixture():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0'))+chunk(b'IEND',b'')
    return 'static const unsigned char rgb_fixture[]={'+','.join(map(str,png))+'};\n'

def main():
    ident='service-check-'+str(time.time_ns())[-10:]
    definition=create(ident,'minimal','SDK Service Check')
    (definition/'main.c').write_text((ROOT/'sdk/tests/services.c').read_text())
    (definition/'rgb-fixture.h').write_text(fixture())
    info=json.loads((definition/'app.json').read_text())
    info['sdk']={'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services',
                 'modules':['startup','display','signals-libc','files','hash','process','network','pcm','fm','unicode-font','images','system-info','volume','packages']}
    (definition/'app.json').write_text(json.dumps(info,indent=2)+'\n')
    (definition/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help'],['--version'],['--selftest']]},indent=2)+'\n')
    # Generated service recipes still use the common SDK compiler entry, with a custom main.
    (definition/'build.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))\nfrom sdk_build import build\nif __name__=="__main__":build(Path(__file__).resolve().parent)\n')
    out=ROOT/'work/sdk-service-tests'/ident
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    command=[sys.executable,'tools/sdk.py','build',ident,'--output',str(out)]
    run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
    if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    from verify_app_package import verify
    report=verify(out/'package');report.update({'native_service_profile':True,'hardware_accessed':False,'network_account_accessed':False})
    # Keep the generated source and report only in work, not in the public app tree.
    target=out/'client-source';shutil.copytree(definition,target)
    for path in sorted(definition.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if path.is_file():path.unlink()
        elif path.is_dir():path.rmdir()
    definition.rmdir()
    (out/'service-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    # A full aggregate link can hide missing module edges. Check every service
    # independently, including header-only presentation's actual file dependency.
    from sdk_services import manifest,compile_native
    matrix=out/'module-matrix';matrix.mkdir()
    for name in manifest():
        app=matrix/('check-'+name);app.mkdir()
        modules=['startup'] if name=='startup' else ['startup',name]
        metadata={'id':app.name,'target':'sony-nw-x1000-jp','sdk':{'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':modules}}
        (app/'app.json').write_text(json.dumps(metadata));(app/'VERSION').write_text('0.1.0-alpha.1\n')
        (app/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help']]}))
        source='#include <stdio.h>\nint main(void){puts("SDK module link OK");return 0;}\n'
        if name=='list-ui':
            source='#include <x1000/services/presentation.h>\nint main(void){struct hb_presentation p;return hb_presentation_load(&p,"/sdk-fixture-missing")?1:0;}\n'
        (app/'main.c').write_text(source)
        compile_native(app,app/'build')
    print(json.dumps({'individual_service_modules_built':len(manifest()),'hardware_accessed':False}))
if __name__=='__main__':main()
