"""Version-pinned SDK compiler. PC-only; host previews never ship to the player."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from app_registry import ROOT
from market_metadata import parse_version

LIBRARIES = {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}
COMMON = ['runtime/platform/sdk/'+n for n in ('core.c','canvas.c','storage.c','entry.c')]
NATIVE = ['runtime/platform/sdk/native.c','runtime/native/linux_devices.c',
          'runtime/native/linux_device_io_posix.c','runtime/native/frontend.c',
          'runtime/native/syscalls.S','runtime/store/deadline.c',
          'runtime/store/termination.c','runtime/store/start.c','runtime/store/start.S',
          'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c',
          'runtime/apps/qqmusic/qqmusic_storage.c','runtime/apps/qqmusic/qqmusic_volume.c']

def fresh_work(path):
    path=Path(path)
    if path.is_symlink(): raise ValueError('Linked output')
    resolved=path.resolve()
    if not resolved.is_relative_to(ROOT/'work') or resolved==ROOT/'work':
        raise ValueError('Output must be a new directory below project work/')
    if resolved.exists(): raise ValueError('Output already exists; select a new --output')
    resolved.mkdir(parents=True)
    return resolved

def compile_app(definition, output, host=False):
    definition=Path(definition).resolve()
    recipe=json.loads((definition/'build.json').read_text())
    if recipe.get('profile')=='native-services':
        if host:raise ValueError('Custom-main services retain their own renderer; use their existing fixture runner')
        from sdk_services import compile_native
        return compile_native(definition,output)
    sdk_version=(ROOT/'sdk/VERSION').read_text().strip()
    if recipe.get('sdk')!=sdk_version: raise ValueError('SDK version mismatch; review and pin sdk/VERSION')
    modules=recipe.get('modules')
    if not isinstance(modules,list) or any(not isinstance(m,str) for m in modules) or len(modules)!=len(set(modules)) or not {'app','canvas'}<=set(modules) or set(modules)-{'app','canvas','storage'}:
        raise ValueError('SDK v1 requires app/canvas; storage is optional; unknown/duplicate modules are rejected')
    version=(definition/'VERSION').read_text().strip();parse_version(version)
    identity=json.loads((definition/'app.json').read_text())['id']
    if identity!=definition.name:raise ValueError('Application ID mismatch')
    source=[]
    for name in recipe['sources']:
        path=(definition/name).resolve()
        if not path.is_relative_to(definition) or not path.is_file() or path.suffix!='.c' or (definition/name).is_symlink():
            raise ValueError('SDK sources must be application-local C files')
        source.append(path)
    output=fresh_work(output)
    storage_sources={'runtime/platform/sdk/storage.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c',
                     'runtime/apps/qqmusic/qqmusic_storage.c','runtime/apps/qqmusic/qqmusic_volume.c'}
    selected=COMMON+(['runtime/platform/sdk/host.c'] if host else NATIVE)
    if 'storage' not in modules:selected=[p for p in selected if p not in storage_sources]
    sources=source+[ROOT/p for p in selected]
    flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
           '-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin',
           '-DHB_BUILD_VERSION="'+version+'"','-DXW_SDK_VERSION="'+sdk_version+'"',
           '-DXW_APP_ID="'+identity+'"',
           '-I'+str(ROOT/'sdk/include')]
    compiler='gcc' if host else 'arm-linux-gnueabi-gcc'
    libraries=[]
    if host:
        flags+=['-DXW_HOST',*subprocess.check_output(['sdl2-config','--cflags'],text=True).split()]
        libraries=subprocess.check_output(['sdl2-config','--libs'],text=True).split()
    else:
        lib=ROOT/'work/arm-signal-tests/lib'
        for name,digest in LIBRARIES.items():
            if not (lib/name).is_file() or hashlib.sha256((lib/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Missing/mismatched '+name+'; run python tools/sdk.py setup')
        flags+=['-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding',
                '-fno-pie','-fno-stack-protector','-DHB_STORE_SONY_LIBC','-DHB_USE_POSIX_DEVICE_IO']
        libraries=['-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none',
                   '-Wl,--dynamic-linker=/lib/ld-linux.so.3',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
    artifact=output/('preview' if host else 'app')
    subprocess.run([compiler,*flags,*map(str,sources),*libraries,'-o',str(artifact)],cwd=ROOT,check=True)
    checks=[]
    for args in (['--help'],['--version'],['--selftest']):
        command=[str(artifact),*args] if host else ['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),*args]
        env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
        run=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True,timeout=15)
        if run.returncode: raise RuntimeError(run.stderr+run.stdout)
        checks.append({'args':args,'exit':run.returncode,'stdout':run.stdout})
    if not host:
        from elftools.elf.elffile import ELFFile
        with artifact.open('rb') as f:
            elf=ELFFile(f)
            if elf['e_machine']!='EM_ARM': raise ValueError('Wrong ELF')
            needed=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
            if needed!=['libc.so.6']: raise ValueError('Unexpected runtime dependency: '+repr(needed))
            interpreter=next(s for s in elf.iter_segments() if s['p_type']=='PT_INTERP').get_interp_name()
            if interpreter!='/lib/ld-linux.so.3': raise ValueError('Wrong loader')
        # The inventory must carry the font and SDK notices with the program.
        notices=output/'LICENSES';notices.mkdir()
        import shutil
        shutil.copyfile(ROOT/'third_party/qqmusic-stb/Noto-OFL.txt',notices/'Noto-OFL.txt')
        shutil.copyfile(ROOT/'sdk/LICENSE',notices/'X1000-SDK-MIT.txt')
    resources=definition/'resources'
    if resources.is_symlink():raise ValueError('Linked resources directory')
    if resources.is_dir():
        import shutil
        for p in resources.rglob('*'):
            if p.is_symlink() or (p.is_file() and not p.name.replace('-','').replace('_','').replace('.','').isalnum()):
                raise ValueError('Unsafe resource')
        shutil.copytree(resources,output/'assets')
    inputs=set(sources+list((ROOT/'sdk/include').rglob('*.h'))+list((ROOT/'runtime/platform/sdk').glob('*.h')))
    pending=list(inputs)
    while pending:
        parent=pending.pop()
        for name in re.findall(r'#include\s+"([^"\n]+)"',parent.read_text()):
            dependency=(parent.parent/name).resolve()
            if dependency.is_relative_to(ROOT) and dependency.is_file() and dependency not in inputs:
                inputs.add(dependency);pending.append(dependency)
    inputs=list(inputs)
    inputs += [ROOT/'sdk/VERSION',ROOT/'sdk/LICENSE',ROOT/'third_party/qqmusic-stb/Noto-OFL.txt',ROOT/'runtime/native/ui_font.h',definition/'build.json',definition/'app.json',definition/'VERSION',Path(__file__)]
    inputs += [p for directory in ('assets','resources') for p in (definition/directory).rglob('*') if p.is_file()]
    report={'sdk_version':sdk_version,'modules':modules,'app_version':version,'host':host,'safe_checks':checks,'stock_library_hashes':{} if host else LIBRARIES,
            'hardware_accessed':False,'firmware_created':False,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    output.with_suffix('.build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return artifact

def build(definition):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path);args=p.parse_args()
    folder=args.output or ROOT/'work/sdk-builds'/Path(definition).name
    print(compile_app(definition,folder))
