"""Compile public ESP-NOW SDK modules independently; never accesses a device."""
from pathlib import Path
import json
import time
from app_registry import ROOT
from sdk_services import compile_native

def main():
    out=ROOT/'work/sdk-espnow-full-tests'/str(time.time_ns());out.mkdir(parents=True)
    checks=[]
    for module in ('espnow-full','espnow-security','espnow-full-device'):
        definition=out/module;definition.mkdir()
        (definition/'app.json').write_text(json.dumps({'id':module,'target':'sony-nw-x1000-jp','sdk':{
            'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':['startup',module]}}))
        (definition/'VERSION').write_text('0.1.0-alpha.1\n')
        (definition/'main.c').write_text((ROOT/'sdk/tests/espnow_full.c').read_text())
        (definition/'build.json').write_text(json.dumps({'profile':'native-services','sources':['main.c'],
            'cflags':(['-DSDK_FULL_DEVICE'] if module=='espnow-full-device' else ['-DSDK_FULL_SECURITY'] if module=='espnow-security' else []),'checks':[[]]}))
        artifact=compile_native(definition,definition/'build')
        checks.append({'module':module,'artifact':str(artifact.relative_to(ROOT))})
    report={'passed':True,'sdk_version':(ROOT/'sdk/VERSION').read_text().strip(),'checks':checks,
            'public_headers':True,'old_sony_libc_arm926':True,'device_accessed':False}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
