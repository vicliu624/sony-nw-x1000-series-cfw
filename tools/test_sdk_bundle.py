"""Prove source SDK usability in a clean extracted project, without old work inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
from app_registry import ROOT

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('--stock-exe',type=Path);a=p.parse_args()
    if sys.flags.optimize:raise RuntimeError('Do not disable assertions')
    work=ROOT/'work/sdk-bundle-tests'/str(time.time_ns());work.mkdir(parents=True)
    with zipfile.ZipFile(a.archive) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names))
        for name in names:
            path=Path(name)
            assert not path.is_absolute() and '..' not in path.parts and not name.startswith(('/', '\\'))
            assert not any(s in path.parts for s in ('work','dist','firmware','.tmp','.git','node_modules','__pycache__'))
            assert path.suffix not in ('.exe','.so','.UPG','.elf','.pyc')
        archive.extractall(work)
    manifest=json.loads((work/'SDK_MANIFEST.json').read_text())
    actual={p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()}
    assert actual==set(manifest['files'])|{'SDK_MANIFEST.json'}
    for name,info in manifest['files'].items():
        data=(work/name).read_bytes();assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256']
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    def run(*args):
        result=subprocess.run([sys.executable,*map(str,args)],cwd=work,env=env,capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        return result.stdout
    # The installer can be independently supplied, but no extracted libc/build is copied.
    setup=['tools/sdk.py','setup']
    if a.stock_exe:setup+=['--stock-exe',a.stock_exe.resolve()]
    run(*setup);run('tools/sdk.py','doctor')
    checks=[]
    for template in ('minimal','touch-ui','canvas-game'):
        ident='new-'+template
        run('tools/sdk.py','new',ident,'--template',template)
        assert (work/'runtime/apps'/ident/'build.json').exists()
        run('tools/sdk.py','render',ident,'--data','--output','work/'+ident+'-preview')
        run('tools/build_app.py',ident,'--build-output','work/'+ident+'-native','--output','work/'+ident+'-package')
        run('tools/verify_app_package.py','work/'+ident+'-package')
        run('tools/sdk.py','package',ident,'--from-package','work/'+ident+'-package','--output','dist/'+ident+'.zip')
        with zipfile.ZipFile(work/'dist'/(ident+'.zip')) as z:
            assert 'HOMEBREW/apps/'+ident+'/app' in z.namelist()
            assert 'HOMEBREW/data/'+ident+'/' in z.namelist()
            assert not any(n.endswith(('.so','.exe','.UPG')) for n in z.namelist())
        checks.append(template)
    report={'passed':True,'sdk_version':manifest['sdk_version'],'source_archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),
            'clean_inputs':True,'templates_created_host_rendered_arm_packaged':checks,'hardware_accessed':False,'firmware_created':False}
    (work/'bundle-test-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
