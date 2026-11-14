"""Check public SDK native-service clients and independent module links."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from app_registry import ROOT
from sdk import create
from sdk_services import compile_native, manifest, resolve

def fixture():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0'))+chunk(b'IEND',b'')
    return 'static const unsigned char rgb_fixture[]={'+','.join(map(str,png))+'};\n'

def check_public_consumer(out):
    ident=out.name
    app_root=out/'client-source'
    definition=create(ident,'minimal','SDK Service Check',app_root)
    (definition/'main.c').write_text((ROOT/'sdk/tests/services.c').read_text())
    (definition/'rgb-fixture.h').write_text(fixture())
    info=json.loads((definition/'app.json').read_text())
    info['sdk']={'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services',
                 'modules':['startup','display','signals-libc','files','hash','process','network','pcm','fm','unicode-font','images','system-info','volume','packages']}
    (definition/'app.json').write_text(json.dumps(info,indent=2)+'\n')
    (definition/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help'],['--version'],['--selftest']]},indent=2)+'\n')
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    build=out/'compiled'
    command=[sys.executable,'tools/sdk.py','--apps-root',str(app_root),'build',ident,'--output',str(build)]
    run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
    if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    from verify_app_package import verify
    report=verify(build/'package');report.update({'native_service_profile':True,'hardware_accessed':False,'network_account_accessed':False,
        'source_definition':definition.relative_to(ROOT).as_posix(),'formal_app_tree_written':False})
    (out/'service-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


def check_modules(out, names, results):
    for name in names:
        modules=['startup'] if name=='startup' else ['startup',name]
        source='#include <stdio.h>\nint main(void){puts("SDK module link OK");return 0;}\n'
        if name=='list-ui':
            source='#include <x1000/services/presentation.h>\nint main(void){struct hb_presentation p;return hb_presentation_load(&p,"/sdk-fixture-missing")?1:0;}\n'
        started=time.monotonic()
        with tempfile.TemporaryDirectory(prefix='module-', dir=out) as folder:
            app=Path(folder)/('check-'+name);app.mkdir()
            metadata={'id':app.name,'target':'sony-nw-x1000-jp','sdk':{'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':modules}}
            (app/'app.json').write_text(json.dumps(metadata));(app/'VERSION').write_text('0.1.0-alpha.1\n')
            (app/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],'checks':[['--help']]}))
            (app/'main.c').write_text(source)
            artifact=compile_native(app,app/'build',receipt_path=app/'compiler.jsonl')
            checked=json.loads((app/'build.sdk-report.json').read_text())
            results.append(dict(module=name,resolved_modules=checked['sdk']['resolved_modules'],
                                checks=checked['checks'],binary_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                seconds=round(time.monotonic()-started,3)))


def main():
    available = manifest()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', choices=available, action='append',
                        help='Link only the named module and its dependencies. Repeat for multiple modules.')
    parser.add_argument('--plan', action='store_true', help='List selected checks without building anything.')
    args = parser.parse_args()
    names = list(dict.fromkeys(args.module)) if args.module else list(available)
    public_consumer = args.module is None
    if args.plan:
        modules = {name: resolve(['startup', name] if name != 'startup' else [name], available)
                   for name in names}
        print(json.dumps(dict(public_consumer=public_consumer, module_builds=modules), indent=2))
        return
    out = ROOT / 'work/sdk-service-tests' / ('service-check-' + str(time.time_ns()))
    out.mkdir(parents=True)
    results=[]
    report=dict(passed=False,public_consumer_checked=False,modules=names,module_checks=results,
                hardware_accessed=False)
    try:
        if public_consumer:
            check_public_consumer(out)
            report['public_consumer_checked']=True
        check_modules(out, names, results)
        report['passed']=True
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        report['individual_service_modules_built']=len(results)
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(report, output=out.relative_to(ROOT).as_posix())))


if __name__=='__main__':main()
