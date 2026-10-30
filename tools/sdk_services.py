"""SDK native-service contracts and compiler binding for existing C/C++ apps.

The service API deliberately retains the proven function names, wire structures,
caller-owned buffers and callback semantics. Existing applications keep their
main, UI, storage policy, protocol logic and ordered compiler arguments.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from app_registry import ROOT

def manifest():
    data=json.loads((ROOT/'sdk/services.json').read_text())
    if data.get('schema')!=1 or data.get('target')!='sony-nw-x1000-jp':raise ValueError('Unsupported SDK services')
    return data['modules']

def resolve(modules):
    available=manifest();ordered=[];visiting=set()
    def visit(name):
        if name in visiting:raise ValueError('SDK module dependency cycle')
        if name in ordered:return
        if name not in available:raise ValueError('Unknown SDK service: '+str(name))
        visiting.add(name)
        for dependency in available[name].get('requires',[]):visit(dependency)
        visiting.remove(name);ordered.append(name)
    if not isinstance(modules,list) or not modules or any(not isinstance(n,str) for n in modules) or len(modules)!=len(set(modules)):raise ValueError('SDK services must be a nonempty unique string list')
    for name in modules:visit(name)
    return ordered

def definition_contract(definition):
    definition=Path(definition).resolve()
    info=json.loads((definition/'app.json').read_text());contract=info.get('sdk')
    if not contract or contract.get('profile')!='native-services':raise ValueError('Application has no SDK native-services contract')
    if contract.get('version')!=(ROOT/'sdk/VERSION').read_text().strip():raise ValueError('Application SDK version pin differs from sdk/VERSION')
    if info.get('id')!=definition.name or info.get('target')!='sony-nw-x1000-jp':raise ValueError('Wrong application/SDK target')
    contract=dict(contract,id=info['id'],resolved_modules=resolve(contract['modules']))
    return contract

def service_files(modules):
    result=[]
    for name in resolve(modules):
        for path in manifest()[name]['sources']:
            if path not in result:result.append(path)
    return result

def prepare_modules(modules):
    """Build generated host-side inputs for explicitly selected services only."""
    import sys
    completed=set()
    for name in resolve(modules):
        for relative in manifest()[name].get('prepare',[]):
            path=(ROOT/relative).resolve()
            if not path.is_relative_to(ROOT/'runtime/platform') or path.suffix!='.py' or not path.is_file():
                raise ValueError('Invalid SDK service preparation script')
            if path not in completed:
                subprocess.run([sys.executable,str(path)],cwd=ROOT,check=True)
                completed.add(path)

def inputs(contract):
    modules=manifest();paths={ROOT/'sdk/VERSION',ROOT/'sdk/services.json',Path(__file__)}
    for name in contract['resolved_modules']:
        item=modules[name]
        paths.update(ROOT/p for p in item['sources'])
        paths.update(ROOT/p for p in item.get('exports',{}).values())
        paths.update(ROOT/p for p in item.get('inputs',[]))
    paths.update((ROOT/'sdk/include/x1000/services').glob('*.h'))
    pending=list(paths)
    import re
    while pending:
        path=pending.pop()
        if not path.is_file():raise ValueError('Missing SDK service implementation: '+str(path))
        for include in re.findall(r'#include\s+"([^"\n]+)"',path.read_text(errors='strict')):
            found=(path.parent/include).resolve()
            if found.is_relative_to(ROOT) and found.is_file() and found not in paths:paths.add(found);pending.append(found)
    return sorted(paths)

def compiler(definition):
    """Return a subprocess-compatible run function for one app's compiler calls.

    Non-compiler fixture/help commands are passed through unchanged. Compiler
    source order, CPU flags, linking, paths and arguments remain exact. This
    function verifies every shared runtime input against the declared SDK
    implementation graph, then records a new, source-bound SDK build receipt.
    """
    definition=Path(definition).resolve();contract=definition_contract(definition)
    prepare_modules(contract['modules'])
    allowed=set(service_files(contract['modules']));modules=manifest()
    owned={p for item in modules.values() for p in item['sources']}
    receipt=ROOT/'work/sdk-services'/contract['id']/'compiler.jsonl'
    receipt.parent.mkdir(parents=True,exist_ok=True)
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs(contract)}
    generated_hashes={}
    for name in contract['resolved_modules']:
        for relative in modules[name].get('generated',[]):
            path=(ROOT/relative).resolve()
            if not path.is_relative_to(ROOT/'work') or not path.is_file():
                raise ValueError('Missing generated SDK service input')
            generated_hashes[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
    def run(command,*args,**kwargs):
        if not isinstance(command,(list,tuple)) or not command or Path(str(command[0])).name not in ('gcc','g++','arm-linux-gnueabi-gcc','arm-linux-gnueabi-g++'):
            return subprocess.run(command,*args,**kwargs)
        cwd=Path(kwargs.get('cwd',Path.cwd())).resolve();used=[]
        for argument in command[1:]:
            candidate=Path(str(argument))
            if candidate.suffix not in ('.c','.cpp','.S'):continue
            path=(candidate if candidate.is_absolute() else cwd/candidate).resolve()
            if not path.is_relative_to(ROOT):continue
            name=path.relative_to(ROOT).as_posix()
            if name.startswith(('runtime/native/','runtime/store/','runtime/platform/')) and name not in owned:
                raise ValueError('Runtime source has no public SDK module: '+name)
            if name in owned:
                if name not in allowed:raise ValueError(contract['id']+' compiles undeclared SDK implementation: '+name)
                used.append(name)
        dependencies={}
        from sdk_build import LIBRARIES
        from sdk_bootstrap import SERVICE_LIBRARIES
        pins={**LIBRARIES,**SERVICE_LIBRARIES}
        for argument in command[1:]:
            path=Path(str(argument))
            if not (path.name.endswith('.a') or '.so' in path.name):continue
            path=(path if path.is_absolute() else cwd/path).resolve()
            if path.is_file() and path.is_relative_to(ROOT):
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                # Resolve may expose the versioned name of an original alias.
                logical=Path(str(argument)).name
                if logical in pins and digest!=pins[logical]:raise ValueError('Pinned SDK library mismatch: '+logical)
                dependencies[path.relative_to(ROOT).as_posix()]=digest
        result=subprocess.run(command,*args,**kwargs)
        row={'sdk_version':contract['version'],'id':contract['id'],'profile':contract['profile'],
             'modules':contract['resolved_modules'],'sdk_sources':used,'exit':result.returncode,
             'ordered_command_sha256':hashlib.sha256(json.dumps(list(map(str,command)),separators=(',',':')).encode()).hexdigest(),
             'source_hashes':source_hashes,'generated_input_hashes':generated_hashes,'linked_dependency_hashes':dependencies,
             'hardware_accessed':False}
        with receipt.open('a') as stream:stream.write(json.dumps(row,separators=(',',':'))+'\n')
        return result
    return run

def compile_native(definition,output):
    """Build a custom-main SDK client from local source plus service modules.

    Existing complex builders use compiler() with their proven ordered recipes;
    new clients can let this declarative path resolve their service dependencies.
    """
    from sdk_build import fresh_work,LIBRARIES
    definition=Path(definition).resolve();contract=definition_contract(definition)
    recipe=json.loads((definition/'build.json').read_text());out=fresh_work(output)
    if recipe.get('profile')!='native-services':raise ValueError('Expected custom-main native-services recipe')
    selected=contract['resolved_modules']
    if 'startup' not in selected:raise ValueError('Custom-main recipes require the startup module')
    if 'signals-libc' in selected and 'signals-oabi' in selected:raise ValueError('Select one signal backend per declarative build')
    if 'clock-libc' in selected and 'clock-oabi' in selected:raise ValueError('Select one clock backend per declarative build')
    local=[]
    for name in recipe['sources']:
        path=(definition/name).resolve()
        if not path.is_relative_to(definition) or not path.is_file() or (definition/name).is_symlink():raise ValueError('Source must be local to this app')
        if path.suffix not in ('.c','.S'):raise ValueError('This SDK profile accepts C and ARM assembly')
        local.append(str(path))
    sources=local+[str(ROOT/p) for p in service_files(contract['modules'])]
    version=(definition/'VERSION').read_text().strip()
    from market_metadata import parse_version
    parse_version(version)
    flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE',
           '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_BUILD_VERSION="'+version+'"',
           '-I'+str(ROOT/'sdk/include'),'-march=armv5te','-marm','-mfloat-abi=soft',
           '-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector']
    libraries=[]
    for name in selected:
        item=manifest()[name]
        for flag in item.get('flags',[]):
            if flag.startswith('-I'):flag='-I'+str(ROOT/flag[2:])
            if flag not in flags:flags.append(flag)
        for path in item.get('libraries',[]):
            actual=ROOT/path
            if not actual.is_file():raise ValueError('Missing service library '+path+'; run sdk.py setup --services')
            if str(actual) not in libraries:libraries.append(str(actual))
    flags+=recipe.get('cflags',[])
    lib=ROOT/'work/arm-signal-tests/lib'
    for name,digest in LIBRARIES.items():
        if not (lib/name).is_file() or hashlib.sha256((lib/name).read_bytes()).hexdigest()!=digest:raise ValueError('Pinned Sony input mismatch')
    runner=compiler(definition);artifact=out/'app'
    runner(['arm-linux-gnueabi-gcc',*flags,*sources,*libraries,
            '-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none',
            '-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(ROOT/'work/stock-resolver-probe'),
            str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),*recipe.get('ldflags',[]),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD');checks=[]
    for arguments in recipe.get('checks',[['--help'],['--version']]):
        run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(ROOT/'work/stock-resolver-probe'),str(artifact),*arguments],cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
        if run.returncode:raise RuntimeError(run.stderr+run.stdout)
        checks.append({'args':arguments,'exit':run.returncode,'stdout':run.stdout})
    out.with_suffix('.sdk-report.json').write_text(json.dumps({'sdk':contract,'checks':checks,'hardware_accessed':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs(contract)}},indent=2)+'\n')
    import shutil
    notices=out/'LICENSES';notices.mkdir()
    shutil.copyfile(ROOT/'sdk/LICENSE',notices/'X1000-SDK-MIT.txt')
    shutil.copyfile(ROOT/'third_party/qqmusic-stb/Noto-OFL.txt',notices/'Noto-OFL.txt')
    if 'images' in selected:shutil.copyfile(ROOT/'third_party/qqmusic-stb/LICENSE',notices/'stb-LICENSE.txt')
    if 'network' in selected or 'crypto-aes' in selected:shutil.copyfile(ROOT/'work/external-tls-probe/bearssl-0.6/LICENSE.txt',notices/'BearSSL-MIT.txt')
    return artifact
