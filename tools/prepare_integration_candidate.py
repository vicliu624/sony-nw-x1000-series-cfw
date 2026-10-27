"""Build and stage a reviewable local integration tree; never UPG/device writes.

Host-only tool. Sony overlay files stay under ignored work/. AppList fragment
is deliberately separate from the overlay and is not an installable config.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(script):
    subprocess.run([sys.executable,'tools/'+script],cwd=ROOT,check=True)

def main():
    version=(ROOT/'VERSION').read_text().strip()
    assert re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',version)
    for script in ('build_native_frontend.py','build_home_candidate.py','check_proxy_frontend_contract.py'):
        run(script)
    native=json.loads((ROOT/'work/native-frontend-build.json').read_text())
    home=json.loads((ROOT/'work/home-entry-candidate/candidate.json').read_text())
    assert native['version']==home['version']==version
    output=ROOT/'work'/('integration-'+version)
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    def stage(source,target,role,stock=None):
        data=source.read_bytes();destination=output/target
        assert destination.resolve().is_relative_to(output.resolve())
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
        item={'path':target,'role':role,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if stock is not None:item.update(stock_bytes=stock,growth_bytes=len(data)-stock)
        records.append(item)
    frontend=ROOT/native['artifact'];sony=ROOT/home['artifact']
    assert hashlib.sha256(frontend.read_bytes()).hexdigest()==native['sha256']
    assert hashlib.sha256(sony.read_bytes()).hexdigest()==home['candidate_sha256']
    stage(frontend,'external/HOMEBREW/launcher/app','External native ARM launcher')
    stage(sony,'system-overlay/usr/local/bin/SpiderApp','Analysis-only Sony menu candidate',sony.stat().st_size-home['growth_bytes'])
    overlay=ROOT/'work/home-entry-candidate/overlay'
    for path in sorted(overlay.rglob('*')):
        if path.is_file():stage(path,'system-overlay/'+path.relative_to(overlay).as_posix(),'Menu resource addition')
    stage(ROOT/'work/home-entry-candidate/AppList.fragment.NOT_INSTALLED','review/AppList.fragment.NOT_INSTALLED','Uninstalled registration fragment; must not replace AppList.conf')
    for name in ('apps','data','cache'):(output/'external/HOMEBREW'/name).mkdir(exist_ok=True)
    evidence=(ROOT/'sources/native-entry-exit-contract.json').read_bytes()
    contract=json.loads(evidence)
    assert contract['all_passed'] and not contract['Sony_return_validated']
    assert contract['reports']['native-proxy-frontend-contract.json']['evidence']['program_sha256']==native['sha256']
    stage(ROOT/'sources/native-entry-exit-contract.json','review/entry-exit-evidence.json','Bounded offline evidence; no hardware qualification')
    manifest={'version':version,'scope':'Local review tree only; NOT a firmware or installation package',
              'files':records,'external_program_bytes':frontend.stat().st_size,
              'sony_elf_growth_bytes':home['growth_bytes'],'apps_included':[],
              'app_store_implemented':False,'ROMs_included':False,'device_operations':False,
              'flashable_package_created':False,'capacity_qualified':False,'hardware_qualified':False,
              'limits':['Empty apps directory; no store or game is falsely supplied as a working app.',
                        'File lengths are not installed filesystem allocation or partition capacity.',
                        'AppList is merged only in this local overlay; nothing is installed. Entry icon remains a placeholder.',
                        'Do not copy system-overlay or run launcher on a player in this research phase.']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'REVIEW.txt').write_text('LOCAL ANALYSIS CANDIDATE — DO NOT INSTALL\n'
        'external/: intended visible-storage layout, not installed.\n'
        'system-overlay/: proprietary modified Sony files for local review only.\n'
        'review/: uninstalled AppList fragment and bounded simulation evidence.\n'
        'No firmware/update container, installer, app store, games or ROMs included.\n')
    print(json.dumps({'version':version,'directory':str(output.relative_to(ROOT)),'files':len(records),
                      'external_program_bytes':frontend.stat().st_size,'sony_elf_growth_bytes':home['growth_bytes'],
                      'firmware_created':False},indent=2))

if __name__=='__main__':main()
