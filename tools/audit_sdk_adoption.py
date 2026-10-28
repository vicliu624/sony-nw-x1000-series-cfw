"""Audit real SDK service imports, builder binding and unchanged application logic."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from app_registry import ROOT,applications
from sdk_services import definition_contract,manifest

POLICY=json.loads((ROOT/'config/sdk-migration.json').read_text())
BASELINE=POLICY['baseline_commit']
def baseline(name):
    result=subprocess.run(['git','show',BASELINE+':'+name],cwd=ROOT,capture_output=True)
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
        result.append(target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target))
    return result

def audit(check_logic=False):
    scope=POLICY['apps']
    discovered=applications();rows=[];errors=[]
    exports={str((ROOT/p).resolve()) for item in manifest().values() for p in item.get('exports',{}).values()}
    for ident in scope:
        definition=ROOT/'runtime/apps'/ident;contract=definition_contract(definition)
        imports=[];unchanged=[]
        builder=(definition/'build.py').read_text()
        if 'sdk_compiler' not in builder:errors.append(ident+': builder bypasses SDK compiler contract')
        old_metadata=json.loads(baseline('runtime/apps/'+ident+'/app.json')) if check_logic else None
        if old_metadata is not None and {k:v for k,v in discovered[ident].items() if k!='sdk'}!=old_metadata:
            errors.append(ident+': application metadata/installed presentation changed')
        if check_logic and (definition/'VERSION').read_text().strip()!=baseline('runtime/apps/'+ident+'/VERSION').strip():
            errors.append(ident+': original app version changed before payload equivalence was established')
        directories=[definition]
        if ident in ('gbc','tamagotchi-id','ebook','dictionary'):directories.append(ROOT/'runtime/apps/emulators')
        for directory in directories:
            for path in directory.rglob('*'):
                if not path.is_file() or path.suffix not in ('.c','.h','.cpp','.inc'):continue
                text=path.read_text(encoding='utf-8')
                for include in re.findall(r'#include\s+"([^"\n]+)"',text):
                    target=(path.parent/include).resolve()
                    if target.is_relative_to(ROOT/'sdk/include/x1000/services'):imports.append(str(path.relative_to(ROOT)))
                    elif str(target) in exports and target.stem!=path.stem:
                        errors.append(str(path.relative_to(ROOT))+': direct private service header '+include)
                if check_logic:
                    name=path.relative_to(ROOT).as_posix()
                    if without_includes(text)!=without_includes(baseline(name)):
                        errors.append(name+': non-include application logic changed')
                    elif effective_includes(path,text)!=effective_includes(path,baseline(name)):
                        errors.append(name+': effective private/standard include order changed')
                    else:unchanged.append(name)
        if not imports:errors.append(ident+': no public SDK service imports')
        rows.append({'id':ident,'sdk':contract['version'],'profile':contract['profile'],'modules':contract['resolved_modules'],
                     'sdk_consumer_files':sorted(set(imports)),'unchanged_application_logic_files':len(set(unchanged))})
    return {'passed':not errors,'baseline_commit':BASELINE,'apps':rows,'errors':sorted(set(errors)),
            'source_check_only':True,'hardware_accessed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-logic',action='store_true');args=p.parse_args()
    result=audit(args.check_logic);out=ROOT/'work/sdk-migration/adoption-audit.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'apps':len(result['apps']),'errors':result['errors']},indent=2))
    raise SystemExit(0 if result['passed'] else 1)
