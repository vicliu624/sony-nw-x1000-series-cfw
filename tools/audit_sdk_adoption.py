"""Audit real SDK service imports, builder binding and unchanged application logic."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from app_registry import ROOT,applications
from sdk_services import definition_contract,manifest,resolve

POLICY=json.loads((ROOT/'config/sdk-migration.json').read_text())
BASELINE=POLICY['baseline_commit']
def source_relocations():
    """Map moved implementations to immutable original sources, not new baselines."""
    moves = POLICY.get('source_relocations', {})
    if not isinstance(moves, dict) or len(set(moves.values())) != len(moves):
        raise ValueError('Source relocation targets must be unique')
    for original, current in moves.items():
        for name in (original, current):
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Invalid source relocation: ' + name)
        if not original.startswith('runtime/apps/') or not current.startswith('runtime/platform/'):
            raise ValueError('Expected app-to-platform source relocation')
        if (ROOT / original).exists() or not (ROOT / current).is_file():
            raise ValueError('Source relocation must remove the old implementation: ' + original)
        if (ROOT / current).is_symlink():
            raise ValueError('Linked source relocation: ' + current)
    return moves

def current_source(path):
    if path.is_relative_to(ROOT):
        name = path.relative_to(ROOT).as_posix()
        return ROOT / source_relocations().get(name, name)
    return path

def source_refactors():
    """A split is recorded separately; it cannot qualify as byte-preserving relocation."""
    refactors = POLICY.get('source_refactors', {})
    for original, targets in refactors.items():
        if not original.startswith('runtime/apps/') or (ROOT / original).exists():
            raise ValueError('Expected a replaced application source: ' + original)
        if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets):
            raise ValueError('Expected unique refactor source targets: ' + original)
        for target in targets:
            path = (ROOT / target).resolve()
            if not path.is_relative_to(ROOT / 'runtime/platform') or not path.is_file():
                raise ValueError('Invalid refactor source: ' + target)
    return refactors

def declared_include_target(source, quoted):
    """Follow the declared application or SDK module include directories."""
    path = current_source(source).relative_to(ROOT)
    name = path.as_posix()
    if path.parts[:2] == ('runtime', 'apps'):
        for directory in POLICY.get('app_include_dirs', {}).get(path.parts[2], []):
            target = (ROOT / directory / quoted).resolve()
            if target.is_relative_to(ROOT) and target.is_file():
                return target
    modules = manifest()
    owners = [module for module, item in modules.items()
              if name in item['sources'] or name in item.get('exports', {}).values()]
    for owner in owners:
        for module in resolve([owner]):
            flags = modules[module].get('flags', [])
            for index, flag in enumerate(flags):
                if flag in ('-I', '-isystem') and index + 1 < len(flags):
                    directory = flags[index + 1]
                elif flag.startswith('-I') and len(flag) > 2:
                    directory = flag[2:]
                else:
                    continue
                target = (ROOT / directory / quoted).resolve()
                if target.is_relative_to(ROOT) and target.is_file():
                    return target
    return None

def baseline_commit(name):
    parts=Path(name).parts
    ident=parts[2] if len(parts)>2 and parts[:2]==('runtime','apps') else None
    return POLICY.get('app_baselines',{}).get(ident,{}).get('commit',BASELINE)

def baseline(name):
    result=subprocess.run(['git','show',baseline_commit(name)+':'+name],cwd=ROOT,capture_output=True)
    if result.returncode:raise ValueError('Missing immutable baseline source: '+name)
    return result.stdout.decode('utf-8').replace('\r\n','\n')

def without_includes(text):
    return re.sub(r'^\s*#\s*include[^\n]*\n','',text,flags=re.M).replace('\r\n','\n').strip()

def effective_includes(path,text):
    """Prove the forwarding headers preserve the original include graph.

    Service headers contain only a fresh guard and one original header import;
    they cannot add packing, flags, inline code or runtime state. This also
    covers conditional app branches needing private device identity inputs.
    """
    result=[]
    for match in re.finditer(r'#include\s+(?:"([^"\n]+)"|<([^>\n]+)>)',text):
        quoted,system=match.groups()
        if system:result.append('<'+system+'>');continue
        target=(path.parent/quoted).resolve()
        if target.is_relative_to(ROOT/'sdk/include/x1000/services'):
            wrapper=target.read_text();imports=re.findall(r'#include\s+"([^"\n]+)"',wrapper)
            if target.name=='runtime.h':
                if imports or re.sub(r'/\*.*?\*/|^\s*#.*$','',wrapper,flags=re.S|re.M).strip():raise ValueError('Console SDK header adds runtime code')
                continue
            if len(imports)!=1:raise ValueError('Service header is not a single original import: '+str(target))
            guard=re.search(r'#ifndef\s+(\w+)',wrapper)
            if not guard:raise ValueError('Missing service guard')
            for line in wrapper.splitlines():
                if line.startswith('#') and not (line in ('#ifndef '+guard[1],'#define '+guard[1],'#endif') or line.startswith('#include "')):
                    raise ValueError('SDK service changes preprocessing policy: '+str(target))
            stripped=re.sub(r'/\*.*?\*/','',wrapper,flags=re.S)
            if re.sub(r'^\s*#.*$','',stripped,flags=re.M).strip():raise ValueError('SDK service adds C runtime code')
            target=(target.parent/imports[0]).resolve()
            if re.search(r'\b__(?:FILE|LINE|INCLUDE_LEVEL|COUNTER)__\b',target.read_text()):
                raise ValueError('Header path/depth-dependent code needs separate regression evidence: '+str(target))
        target = current_source(target)
        if not target.is_file():
            target = declared_include_target(path, quoted) or target
        result.append(target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target))
    return result

def audit(check_logic=False, apps=None):
    scope = POLICY['apps'] if apps is None else apps
    if not scope or len(set(scope)) != len(scope) or any(name not in POLICY['apps'] for name in scope):
        raise ValueError('Select unique applications from the migration policy')
    moves = source_relocations()
    refactors = source_refactors()
    originals = {current: original for original, current in moves.items()}
    discovered=applications();rows=[];errors=[]
    checked={ROOT/'config/sdk-migration.json',ROOT/'sdk/services.json',ROOT/'sdk/VERSION',
             ROOT/'tools/audit_sdk_adoption.py',ROOT/'tools/sdk_services.py'}
    exports={str((ROOT/p).resolve()) for item in manifest().values() for p in item.get('exports',{}).values()}
    for ident in scope:
        definition=ROOT/'runtime/apps'/ident;contract=definition_contract(definition)
        checked.update(path for name in ('build.py','build.json','app.json','VERSION')
                       if (path:=definition/name).is_file())
        imports=[];unchanged=[]
        builder=(definition/'build.py').read_text()
        if ('from native_app_build import build' in builder.splitlines()
                and (definition/'build.json').is_file()):
            checked.add(ROOT/'tools/native_app_build.py')
        elif 'sdk_compiler' not in builder:
            errors.append(ident+': builder bypasses SDK compiler contract')
        old_metadata=json.loads(baseline('runtime/apps/'+ident+'/app.json')) if check_logic else None
        if old_metadata is not None and {k:v for k,v in discovered[ident].items() if k!='sdk'}!={k:v for k,v in old_metadata.items() if k!='sdk'}:
            errors.append(ident+': application metadata/installed presentation changed')
        directories=[definition]
        if ident in ('gbc','tamagotchi-id','ebook','dictionary'):directories.append(ROOT/'runtime/apps/emulators')
        sources = [path for directory in directories for path in directory.rglob('*')]
        sources += [ROOT / current for original, current in moves.items()
                    if original.startswith('runtime/apps/' + ident + '/')]
        split_sources = {ROOT / target for original, targets in refactors.items()
                         if original.startswith('runtime/apps/' + ident + '/') for target in targets}
        sources += sorted(split_sources)
        if check_logic and split_sources:
            errors.append(ident + ': structural refactor requires semantic acceptance; historical byte equivalence is not claimed')
        for path in sources:
            if not path.is_file() or path.suffix not in ('.c','.h','.cpp','.inc'):continue
            text=path.read_text(encoding='utf-8')
            checked.add(path)
            for include in re.findall(r'#include\s+"([^"\n]+)"',text):
                target=(path.parent/include).resolve()
                if target.is_file() and target.is_relative_to(ROOT):checked.add(target)
                if target.is_relative_to(ROOT/'sdk/include/x1000/services'):imports.append(str(path.relative_to(ROOT)))
                elif path.is_relative_to(definition) and str(target) in exports and target.stem!=path.stem:
                    errors.append(str(path.relative_to(ROOT))+': direct private service header '+include)
            if check_logic and path not in split_sources:
                name=path.relative_to(ROOT).as_posix()
                original = originals.get(name, name)
                try:
                    old_text = baseline(original)
                except ValueError as error:
                    errors.append(str(error))
                    continue
                if without_includes(text)!=without_includes(old_text):
                    errors.append(name+': non-include application logic changed')
                elif effective_includes(path,text)!=effective_includes(ROOT / original,old_text):
                    errors.append(name+': effective private/standard include order changed')
                else:unchanged.append(name)
        if not imports:errors.append(ident+': no public SDK service imports')
        rows.append({'id':ident,'sdk':contract['version'],'profile':contract['profile'],'modules':contract['resolved_modules'],
                     'sdk_consumer_files':sorted(set(imports)),'unchanged_application_logic_files':len(set(unchanged))})
    return {'passed':not errors,'baseline_commit':BASELINE,'app_baselines':POLICY.get('app_baselines',{}),'source_relocations':moves,'source_refactors':refactors,'apps':rows,'errors':sorted(set(errors)),
            'source_check_only':True,'hardware_accessed':False,
            'source_hashes':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in sorted(checked)}}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-logic',action='store_true')
    p.add_argument('--app', action='append', choices=POLICY['apps'])
    p.add_argument('--output', type=Path)
    args=p.parse_args()
    result=audit(args.check_logic, args.app)
    out=(args.output or ROOT/'work/sdk-migration'/str(time.time_ns())/'adoption-audit.json').resolve()
    if not out.is_relative_to(ROOT/'work') or out.exists():
        raise ValueError('Select a new audit file under work/')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'apps':len(result['apps']),'errors':result['errors'],'report':str(out.relative_to(ROOT))},indent=2))
    raise SystemExit(0 if result['passed'] else 1)
