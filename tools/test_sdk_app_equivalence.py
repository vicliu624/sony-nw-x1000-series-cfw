"""Build immutable pre-SDK apps and SDK consumers at the SAME project path.

CI-only source substitution is always restored in finally. Work output is an
isolated ephemeral volume. No player, personal package, account or ROM is used.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from app_registry import ROOT

BASELINE='b27cff1'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    if not os.environ.get('GITHUB_ACTIONS'):raise RuntimeError('Run in clean Linux CI; do not substitute source in an active user checkout')
    if sys.flags.optimize:raise RuntimeError('Assertions must remain enabled')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise RuntimeError('CI source must start clean')
    root=ROOT/'work/sdk-migration'/('ci-'+str(time.time_ns()));root.mkdir(parents=True)
    apps=json.loads(git('show',BASELINE+':config/release.json'))['apps']+['pet','qqcheck']
    info={'commit':git('rev-parse',BASELINE).decode().strip(),'apps':apps,
          'versions':{a:git('show',BASELINE+':runtime/apps/'+a+'/VERSION').decode().strip() for a in apps},
          'source_hashes':{},'user_report':'User reports all prior apps passed on their unit using local builds; exact personal packages are not available to CI.',
          'ci_inputs':'Pinned public sources, synthetic pet artwork and ephemeral test-only terminal identity; no user state.'}
    (root/'baseline.json').write_text(json.dumps(info,indent=2)+'\n')
    # The pet accepts fixed RGB565LE+alpha records; every pose/direction is unique.
    pet=ROOT/'work/pet-build/HOMEBREW/apps/pet';pet.mkdir(parents=True,exist_ok=True)
    sprites=bytearray()
    for frame in range(72):
        color=((frame*7%31)<<11)|((frame*13%63)<<5)|(frame*17%31)
        for y in range(104):
            for x in range(96):sprites.extend((color&255,color>>8,255 if 8<=x<88 and 8<=y<96 else 0))
    (pet/'sprites.bin').write_bytes(sprites)
    identity=ROOT/'work/terminal-review/private-identity';identity.mkdir(parents=True,exist_ok=True)
    subprocess.run(['openssl','ecparam','-name','prime256v1','-genkey','-noout','-out',str(identity/'server-key.pem')],check=True)
    subprocess.run(['openssl','req','-new','-x509','-sha256','-days','2','-key',str(identity/'server-key.pem'),'-subj','/CN=SDK CI fixture only/','-out',str(identity/'server-cert.pem')],check=True)
    changed=git('diff','--name-only',BASELINE,'--','runtime/apps','tools/native_app_build.py','tools/build_app.py','tools/build_qqmusic_codec.py').decode().splitlines()
    originals={};saved={}
    for name in changed:
        old=subprocess.run(['git','show',BASELINE+':'+name],cwd=ROOT,capture_output=True)
        path=ROOT/name
        if old.returncode==0 and path.is_file():originals[name]=old.stdout;saved[name]=path.read_bytes()
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD',PYTHONDONTWRITEBYTECODE='1',
             SOURCE_DATE_EPOCH=git('show','-s','--format=%ct',BASELINE).decode().strip())
    def phase(name):
        log=root/(name+'-driver.log')
        print('Running '+name+' apps from source at the same path',flush=True)
        with log.open('wb') as stream:
            result=subprocess.run([sys.executable,'tools/sdk_migration.py',name,'--baseline',str(root)],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            # Only the public fixture log is in this CI checkout; no local identity is uploaded.
            print(log.read_text(errors='replace')[-8000:],flush=True);raise RuntimeError(name+' application build failed')
    try:
        for name,data in originals.items():(ROOT/name).write_bytes(data)
        phase('baseline')
    finally:
        for name,data in saved.items():(ROOT/name).write_bytes(data)
    phase('verify')
    report=json.loads((root/'migrated/report.json').read_text())
    assert set(report['apps'])==set(apps)
    assert all(r['passed'] and r['identical_installed_payload'] for r in report['apps'].values())
    output=ROOT/'work/sdk-migration/equivalence.json'
    output.write_text(json.dumps({'passed':True,'baseline_commit':info['commit'],'migrated_commit':git('rev-parse','HEAD').decode().strip(),
             'apps':{a:{'version':r['version'],'identical_installed_payload':True,'payload_hashes':r['payload_hashes']} for a,r in report['apps'].items()},
             'same_build_path':True,'same_toolchain_and_inputs':True,'user_device_accessed':False,'firmware_built':False},indent=2)+'\n')
    print('PASS: all16 application installation payloads are byte-identical to their pre-SDK builds',flush=True)

if __name__=='__main__':main()
