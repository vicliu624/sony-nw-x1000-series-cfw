"""Capture and compare existing app builds without installing or flashing anything.

All evidence stays under work/. The terminal's existing personal identity and
pet artwork are local-only inputs; neither is printed or published.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import difflib
from app_registry import ROOT, applications
from sdk_binary_equivalence import canonical_payload

def hashes(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and not p.is_symlink()}

def elf_difference(old,new,out,ident):
    """Only public CI program code/metadata, never libraries, artwork or keys."""
    from elftools.elf.elffile import ELFFile
    sections=[];strings=[]
    with old.open('rb') as first,new.open('rb') as second:
        a=ELFFile(first);b=ELFFile(second)
        names={s.name for s in a.iter_sections()}|{s.name for s in b.iter_sections()}
        for name in sorted(names):
            x=a.get_section_by_name(name);y=b.get_section_by_name(name)
            left=x.data() if x else b'';right=y.data() if y else b''
            if left==right:continue
            sections.append({'section':name,'allocated':bool((x or y)['sh_flags']&2),'old_bytes':len(left),'new_bytes':len(right),
                             'old_sha256':hashlib.sha256(left).hexdigest(),'new_sha256':hashlib.sha256(right).hexdigest()})
            if name in ('.rodata','.strtab','.dynstr','.comment'):
                import re
                old_strings=set(re.findall(rb'[ -~]{6,256}',left));new_strings=set(re.findall(rb'[ -~]{6,256}',right))
                strings.append({'section':name,'removed':[s.decode() for s in sorted(old_strings-new_strings)][:50],
                                'added':[s.decode() for s in sorted(new_strings-old_strings)][:50]})
    (out/('elf-'+ident+'.json')).write_text(json.dumps({'id':ident,'sections':sections,'string_differences':strings},indent=2)+'\n')
    before=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(old)],text=True)
    after=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(new)],text=True)
    difference=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='pre-SDK',tofile='SDK'))
    (out/('elf-'+ident+'.diff')).write_text(difference)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['baseline','verify'])
    p.add_argument('--baseline',type=Path,default=ROOT/'work/sdk-migration/baseline-b27cff1')
    p.add_argument('--apps',nargs='+');a=p.parse_args()
    baseline=a.baseline.resolve()
    if not baseline.is_relative_to(ROOT/'work/sdk-migration'):raise ValueError('Use project migration evidence directory')
    original=json.loads((baseline/'baseline.json').read_text());selected=a.apps or original['apps']
    if not set(selected)<=set(original['apps']):raise ValueError('Not part of the captured migration baseline')
    info=applications();out=baseline/('rebuilt' if a.phase=='baseline' else 'migrated')
    out.mkdir(exist_ok=True)
    # Preserve old generated packages before any builder can refresh them.
    if a.phase=='baseline':
        for ident in selected:
            source=ROOT/info[ident]['build']['package'];backup=baseline/'old-package-trees'/ident
            if source.is_dir() and not backup.exists() and ident!='terminal':shutil.copytree(source,backup)
        for name in ('package/HOMEBREW/apps/terminal','private-identity'):
            source=ROOT/'work/terminal-review'/name;backup=baseline/'old-terminal'/name
            if source.is_dir() and not backup.exists():shutil.copytree(source,backup)
    inputs=baseline/'inputs';inputs.mkdir(exist_ok=True)
    sprites=inputs/'pet-sprites.bin'
    if 'pet' in selected and not sprites.exists():shutil.copyfile(ROOT/'work/pet-build/HOMEBREW/apps/pet/sprites.bin',sprites)
    # The same public (non-account) profile and trust bytes are used in both phases.
    profile=inputs/'qqmusic-public.json'
    if 'qqmusic' in selected and not profile.exists():
        config=json.loads((ROOT/'config/qqmusic-public.json').read_text())
        ca=(ROOT/'work/external-tls-probe/github-ca.der').read_bytes();roots=[]
        while ca:
            count=ca[1]&127 if ca[1]&128 else 0;head=2+count
            size=int.from_bytes(ca[2:head],'big') if count else ca[1]
            cert=inputs/('ca-'+str(len(roots))+'.der');cert.write_bytes(ca[:head+size]);roots.append(str(cert));ca=ca[head+size:]
        config['ca_files']=roots;profile.write_text(json.dumps(config))
    report_path=out/'report.json'
    report=json.loads(report_path.read_text()) if report_path.exists() else {'phase':a.phase,'apps':{},'hardware_accessed':False,'firmware_created':False}
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    for ident in selected:
        if report['apps'].get(ident,{}).get('passed'):continue
        package=out/'packages'/ident;package.parent.mkdir(parents=True,exist_ok=True)
        if package.exists():raise ValueError('Partial package exists; inspect it and choose a fresh evidence phase')
        command=[sys.executable,'tools/build_app.py',ident,'--output',str(package)]
        if ident=='pet':
            command+=['--sprites',str(sprites),'--build-output',str(out/'builders/pet')]
        elif ident=='qqmusic':
            command+=['--profile',str(profile),'--build-output',str(out/'builders/qqmusic'),'--device-full','--public-installation']
        elif ident=='terminal':
            # Never create/rotate an identity merely to perform migration checks.
            if not all((ROOT/'work/terminal-review/private-identity'/n).is_file() for n in ('server-key.pem','server-cert.pem')):
                raise ValueError('Existing terminal identity missing; use a separate public-only compilation fixture')
        log=out/(ident+'.log');print(a.phase+': '+ident,flush=True)
        with log.open('wb') as stream:
            run=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        if run.returncode:
            report['apps'][ident]={'passed':False,'exit':run.returncode,'log':str(log.relative_to(ROOT))}
            report_path.write_text(json.dumps(report,indent=2)+'\n')
            print(log.read_text(errors='replace')[-6000:],flush=True);raise RuntimeError(ident+' baseline/build check failed')
        from verify_app_package import verify
        verify(package)
        payload=hashes(package);equivalent,noise=canonical_payload(package)
        row={'passed':True,'version':(ROOT/'runtime/apps'/ident/'VERSION').read_text().strip(),
             'payload_hashes':payload,'comparison_hashes':equivalent,'gcc_file_markers':noise,'log':str(log.relative_to(ROOT))}
        if a.phase=='verify':
            previous=json.loads((baseline/'rebuilt/report.json').read_text())['apps'][ident]
            row['raw_installed_payload_identical']=payload==previous['payload_hashes']
            row['equivalent_installed_payload']=equivalent==previous['comparison_hashes']
            row['changed_files']=sorted(k for k in payload.keys()|previous['payload_hashes'].keys() if payload.get(k)!=previous['payload_hashes'].get(k))
            if not row['equivalent_installed_payload']:
                row['passed']=False
                elf_difference(baseline/'rebuilt/packages'/ident/'app',package/'app',out,ident)
        report['apps'][ident]=row;report_path.write_text(json.dumps(report,indent=2)+'\n')
        if not row['passed']:print(ident+' changed runtime/resource payload: '+repr(row['changed_files']),flush=True)
    print(json.dumps({'phase':a.phase,'passed_apps':[k for k,v in report['apps'].items() if v['passed']],
                      'report':str(report_path.relative_to(ROOT)),'hardware_accessed':False},indent=2))
    if any(not row['passed'] for row in report['apps'].values()):raise RuntimeError('Installed-byte differences remain; see ELF diagnostics')
if __name__=='__main__':main()
