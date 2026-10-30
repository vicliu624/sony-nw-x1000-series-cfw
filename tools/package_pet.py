"""Package locally built BSOD app for manual device testing; no deployment."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,default=ROOT/'work/pet-build');options=parser.parse_args()
    work=options.build.resolve()
    if not work.is_relative_to(ROOT/'work') or work==ROOT/'work':raise ValueError('Build must be under work/')
    report=json.loads((work/'build.json').read_text())
    if not report['build_passed']:raise ValueError('Build has not passed')
    for name,digest in report['source_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Source changed: '+name)
    for name,digest in report.get('build_inputs',{}).items():
        if sha(ROOT/name)!=digest:raise ValueError('Build input changed: '+name)
    visual=json.loads((work/'visual-review.json').read_text())
    if visual['source_hashes']!=report['source_hashes']:raise ValueError('Visual review belongs to a different build')
    for name,digest in visual['frames'].items():
        if sha(work/name)!=digest:raise ValueError('Rendered frame changed')
    if len(visual['frames'])!=report.get('render_cases',14):raise ValueError('Incomplete visual review')
    bridge_work=ROOT/'work/pet-bridge/windows'
    bridge_report=json.loads((bridge_work/'build.json').read_text())
    for name,digest in bridge_report['source_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Bridge source changed: '+name)
    if sha(bridge_work/'Release/pet-bridge.exe')!=bridge_report['exe_sha256']:raise ValueError('Bridge executable changed')
    project=(ROOT/'VERSION').read_text().strip();version=(ROOT/'runtime/apps/pet/VERSION').read_text().strip()
    out=ROOT/'dist'/project/'pet'/version
    if out.exists():raise ValueError('Preserve existing package: '+str(out))
    folder=work/'HOMEBREW/apps/pet';inventory=(folder/'files.sha256').read_text().splitlines()
    if inventory[0]!='HBFILES1':raise ValueError('Inventory header')
    names=set()
    required={'app','app.ini','sprites.bin','font.bin','icon.svg','icon.png','about.json','LICENSES/UNIFONT-LICENSE.txt','LICENSES/UNIFONT-OFL-1.1.txt','LICENSES/PROVENANCE.md','LICENSES/BearSSL-MIT.txt','presentation.bin','app-info.json'}
    for line in inventory[1:]:
        digest,size,name=line.split(' ')
        if name not in required or name in names:raise ValueError('Unexpected inventory')
        names.add(name);p=folder/name
        if sha(p)!=digest or p.stat().st_size!=int(size):raise ValueError('Payload changed')
    if names!=required:raise ValueError('Incomplete payload')
    out.mkdir(parents=True);shutil.copytree(folder,out/'HOMEBREW/apps/pet')
    shutil.copyfile(ROOT/'docs/apps/PET.md',out/'README.md')
    shutil.copyfile(ROOT/'docs/apps/PET_LINK.md',out/'PET_LINK.md')
    review=out/'REVIEW';review.mkdir()
    report['review_scope']='Manual device test candidate; physical qualification pending'
    report['visual_review']='Local and linked states, pairing controls, read acknowledgements, long Chinese details and error states inspected at native size'
    report['pending']=['physical paired Wi-Fi/touch/HOME/USB/sleep qualification']
    report['manual_test_package_ready']=True
    (review/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copyfile(work/'visual-review.json',review/'visual-review.json')
    shutil.copyfile(bridge_work/'build.json',review/'windows-bridge-build.json')
    for path in ['work/pet-bridge/arm-tls-test/report.json','work/pet-bridge/real-codex-test/report.json','work/pet-bridge/discovery-test/report.json']:
        origin=ROOT/path
        if origin.is_file():shutil.copyfile(origin,review/('discovery.json' if 'discovery-test' in path else 'real-codex.json' if 'real-codex' in path else 'arm-tls.json'))
    for p in work.glob('frame-*.ppm'):shutil.copyfile(p,review/p.name)
    for name in report['source_hashes']:
        p=out/'SOURCE'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    p=out/'SOURCE/docs/apps/PET.md';p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'docs/apps/PET.md',p)
    for name in ['docs/apps/PET_LINK.md','docs/APP_SPEC.md']:
        p=out/'SOURCE'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    computer=out/'COMPUTER';computer.mkdir()
    bridge=ROOT/'work/pet-bridge/windows/Release/pet-bridge.exe'
    if not bridge.is_file():raise ValueError('Native computer bridge is not built')
    shutil.copyfile(bridge,computer/'pet-bridge.exe')
    shutil.copyfile(ROOT/'tools/prepare_pet_pairing.py',computer/'prepare_pet_pairing.py')
    notices=computer/'LICENSES';notices.mkdir()
    shutil.copyfile(ROOT/'third_party/pet-json/LICENSE.MIT',notices/'JSON-MIT.txt')
    shutil.copyfile(ROOT/'work/external-tls-probe/bearssl-0.6/LICENSE.txt',notices/'BearSSL-MIT.txt')
    (computer/'README.txt').write_text('Native Codex bridge for BSOD Pet\n\nIf a personal pairing folder was supplied, start its computer/Start Codex Pet.cmd.\nOtherwise, open a terminal in the unpacked ZIP root and run:\n  python COMPUTER/prepare_pet_pairing.py --list\n  python COMPUTER/prepare_pet_pairing.py --thread UUID --output work/my-pairing\n\nThis one-time preparation uses Python and Git/OpenSSL on the computer only.\nThe running bridge and player application are native C++/C. Copy the generated\nPLAYER/HOMEBREW/data/pet/link.pair to visible player storage and safely eject USB.\nStart the generated computer/Start Codex Pet.cmd and connect the player through\nthe original Sony Wi-Fi interface. Do not copy COMPUTER to the player.\nSee ../PET_LINK.md for controls, identity management and verification limits.\n')
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    archive=out.parent/('NW-X1000-BSOD-Pet-'+version+'-manual-test.zip')
    if archive.exists():raise ValueError('Preserve existing ZIP')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('ZIP CRC failed')
        for p in out.rglob('*'):
            if p.is_file() and z.read(p.relative_to(out).as_posix())!=p.read_bytes():raise ValueError('ZIP readback')
        if any(n.lower().endswith(('.upg','.sav','.rom')) or (n.lower().endswith('.exe') and n!='COMPUTER/pet-bridge.exe') for n in z.namelist()):raise ValueError('Unexpected firmware/state')
    result={'zip':str(archive.relative_to(ROOT)),'bytes':archive.stat().st_size,'sha256':sha(archive),'hardware_tested':False,'device_written':False,'firmware_created':False}
    (out.parent/'package.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
