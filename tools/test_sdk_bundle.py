"""Prove source SDK usability in a clean extracted project, without old work inputs."""
import argparse
import hashlib
import json
import os
import posixpath
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from urllib.parse import unquote, urlsplit
from app_registry import ROOT

def check_documentation(archive):
    names = set(archive.namelist())
    missing = []
    count = 0
    for name in sorted(names):
        if not name.endswith('.md'):
            continue
        count += 1
        text = archive.read(name).decode('utf-8-sig')
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            link = urlsplit(raw.strip('<>'))
            if link.scheme or link.netloc or not link.path:
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(link.path)))
            if target not in names and not any(path.startswith(target.rstrip('/') + '/') for path in names):
                missing.append(name + ': ' + raw)
    if missing:
        raise ValueError('Broken source-SDK documentation links:\n' + '\n'.join(missing))
    return count

def verify_bundle(a, work):
    with zipfile.ZipFile(a.archive) as archive:
        documentation_count = check_documentation(archive)
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
    report = dict(passed=True, sdk_version=manifest['sdk_version'],
                  source_archive_sha256=hashlib.sha256(a.archive.read_bytes()).hexdigest(),
                  documentation_links_checked=documentation_count, hardware_accessed=False,
                  firmware_created=False)
    if a.archive_only:
        report.update(scope='archive-only', full_sdk_matrix_run=False)
        return 'archive-test-report.json', report
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    def run(*args,timeout=120):
        started=time.monotonic();print('SDK bundle check: '+str(args[0]),flush=True)
        result=subprocess.run([sys.executable,*map(str,args)],cwd=work,env=env,capture_output=True,text=True,timeout=timeout)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        print('SDK bundle check passed in %.1fs: %s'%(time.monotonic()-started,args[0]),flush=True)
        return result.stdout
    # The installer can be independently supplied, but no extracted libc/build is copied.
    setup=['tools/sdk.py','setup']
    if a.stock_exe:setup+=['--stock-exe',a.stock_exe.resolve()]
    run(*setup,'--services');run('tools/sdk.py','doctor')
    if a.player_only:
        run('tools/test_sdk_player_service.py')
        report.update(scope='player-client-only', clean_inputs=True, original_installer_only=True,
                      public_player_consumer=True, full_sdk_matrix_run=False)
        return 'player-bundle-test-report.json', report
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
    # This checks every selected module independently, including codecs/packages.
    # Keep per-app command limits unchanged; allow the expanded matrix to finish.
    run('tools/test_sdk_services.py',timeout=600)
    run('tools/test_sdk_text.py')
    run('tools/test_sdk_storage_stop.py')
    run('tools/test_sdk_espnow.py');run('tools/test_sdk_espnow_full.py');run('tools/test_sdk_espnow_owner.py');run('tools/test_sdk_player_service.py')
    report.update(clean_inputs=True, templates_created_host_rendered_arm_packaged=checks,
                  external_native_service_client=True, full_sdk_matrix_run=True)
    return 'bundle-test-report.json', report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--stock-exe', type=Path)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--player-only', action='store_true',
                       help='Verify only the public player client after fresh SDK setup')
    scope.add_argument('--archive-only', action='store_true',
                       help='Verify ZIP contents, manifest and links without preparing the toolchain')
    args = parser.parse_args()
    if sys.flags.optimize:
        raise RuntimeError('Do not disable assertions')
    output = ROOT / 'work/sdk-bundle-tests' / str(time.time_ns())
    output.mkdir(parents=True)
    try:
        # Keep short-lived builds on the host's temporary filesystem. On WSL
        # this avoids compiling the SDK fixture tree through a Windows mount.
        with tempfile.TemporaryDirectory(prefix='x1000-sdk-') as directory:
            report_name, report = verify_bundle(args, Path(directory))
    except Exception:
        (output / 'failure.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    (output / report_name).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__=='__main__':main()
