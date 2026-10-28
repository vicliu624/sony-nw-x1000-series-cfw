"""Create an explicit source-only SDK archive. Never packages Sony inputs or apps."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from app_registry import ROOT
from sdk_build import COMMON,NATIVE

TOOLS=['sdk.py','sdk_build.py','sdk_bootstrap.py','sdk_services.py','native_app_build.py','package_sdk.py','test_sdk.py','test_sdk_bundle.py',
       'app_registry.py','app_presentation.py','build_app.py','verify_app_package.py','market_metadata.py']
HEADERS=['runtime/native/linux_devices.h','runtime/native/linux_device_io.h','runtime/native/frontend.h','runtime/native/ui_font.h',
         'runtime/store/termination.h','runtime/store/deadline.h','runtime/store/stock_fs_bridge.h',
         'runtime/store/stock_stat64.h','runtime/store/target_abi.h',
         'runtime/apps/qqmusic/qqmusic_volume.h','runtime/apps/qqmusic/qqmusic_storage.h']
def source_files():
    paths=[ROOT/p for p in sorted(set(COMMON+NATIVE+HEADERS+['runtime/platform/sdk/internal.h','runtime/platform/sdk/host.c',
        'runtime/native/app_catalog.c','runtime/native/app_catalog.h','runtime/native/linux_files.c','runtime/native/linux_files.h',
        'runtime/native/sha256.c','runtime/native/sha256.h']))]
    paths += [ROOT/'tools'/n for n in TOOLS]
    paths += [ROOT/'VERSION',ROOT/'scripts/upg.py',ROOT/'sources/downloads.json',ROOT/'third_party/qqmusic-stb/Noto-OFL.txt']
    paths += [p for d in ('sdk','docs/sdk','runtime/apps/sdk-counter','runtime/apps/sdk-canvas') for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    from sdk_services import inputs,manifest
    # Export every service implementation and transitive header, not only the
    # small callback-profile subset. External clients never need private checkout paths.
    for name in manifest():
        paths += inputs({'resolved_modules':[name]})
    return sorted(set(paths))

def package(output):
    version=(ROOT/'sdk/VERSION').read_text().strip()
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'dist') or output.exists():raise ValueError('Select a new ZIP under project dist/')
    data={}
    for path in source_files():
        if path.is_symlink() or not path.is_file():raise ValueError('Missing/linked source: '+str(path))
        name=path.relative_to(ROOT).as_posix()
        if any(p in ('work','dist','.tmp','.git','firmware','node_modules') for p in Path(name).parts) or path.suffix in ('.so','.exe','.UPG','.elf','.pyc'):
            raise ValueError('Forbidden SDK input: '+name)
        data[name]=path.read_bytes()
    # The source catalog is restricted to the one input used by SDK setup.
    data['sources/downloads.json']=(json.dumps(json.loads(data['sources/downloads.json'])[0:1],indent=2)+'\n').encode()
    data['README.md']=('''# X1000 SDK source bundle

Start with sdk/README.md and docs/sdk/README.md. Supported development host:
Ubuntu24.04 / WSL2, Python3.12, GNU ARM cross compiler and SDL2.

This archive contains source, templates, tests and public input provenance.
It contains no Sony executable, libc/loader, firmware image, ROM, music,
identity or personal state. SDK setup acquires/extracts pinned original inputs
locally and never executes an updater. Run python tools/sdk.py --help.
Existing app metadata is separate from the official release allowlist.
All device behavior remains experimental; see docs/sdk/VALIDATION.md.
''').encode()
    data['.gitignore']=b'/work/\n/dist/\n/firmware/\n/.venv/\n__pycache__/\n*.pyc\n'
    manifest={'sdk_version':version,'target':'sony-nw-x1000-jp','source_only':True,
              'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(data.items())}}
    data['SDK_MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,content in sorted(data.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,content)
    output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
    print(json.dumps({'sdk_version':version,'archive':str(output.relative_to(ROOT)),'files':len(data),'source_only':True},indent=2))
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args()
    version=(ROOT/'sdk/VERSION').read_text().strip()
    package(a.output or ROOT/'dist/sdk'/version/('x1000-sdk-'+version+'-source.zip'))
