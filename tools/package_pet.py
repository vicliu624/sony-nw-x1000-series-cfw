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
    visual=json.loads((work/'visual-review.json').read_text())
    if visual['source_hashes']!=report['source_hashes']:raise ValueError('Visual review belongs to a different build')
    for name,digest in visual['frames'].items():
        if sha(work/name)!=digest:raise ValueError('Rendered frame changed')
    if len(visual['frames'])!=14:raise ValueError('Incomplete visual review')
    project=(ROOT/'VERSION').read_text().strip();version=(ROOT/'runtime/apps/pet/VERSION').read_text().strip()
    out=ROOT/'dist'/project/'pet'/version
    if out.exists():raise ValueError('Preserve existing package: '+str(out))
    folder=work/'HOMEBREW/apps/pet';inventory=(folder/'files.sha256').read_text().splitlines()
    if inventory[0]!='HBFILES1':raise ValueError('Inventory header')
    names=set()
    required={'app','app.ini','sprites.bin','font.bin','icon.svg','icon.png','about.json','LICENSES/UNIFONT-LICENSE.txt','LICENSES/UNIFONT-OFL-1.1.txt','LICENSES/PROVENANCE.md'}
    for line in inventory[1:]:
        digest,size,name=line.split(' ')
        if name not in required or name in names:raise ValueError('Unexpected inventory')
        names.add(name);p=folder/name
        if sha(p)!=digest or p.stat().st_size!=int(size):raise ValueError('Payload changed')
    if names!=required:raise ValueError('Incomplete payload')
    out.mkdir(parents=True);shutil.copytree(folder,out/'HOMEBREW/apps/pet')
    shutil.copyfile(ROOT/'docs/apps/PET.md',out/'README.md')
    review=out/'REVIEW';review.mkdir()
    report['review_scope']='Manual device test candidate; physical qualification pending'
    report['visual_review']='Nine poses, menu, help, reset, save error and warning inspected at native size'
    report['pending']=['device touch/HOME/USB qualification']
    report['manual_test_package_ready']=True
    (review/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copyfile(work/'visual-review.json',review/'visual-review.json')
    for p in work.glob('frame-*.ppm'):shutil.copyfile(p,review/p.name)
    for name in report['source_hashes']:
        p=out/'SOURCE'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    p=out/'SOURCE/docs/apps/PET.md';p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'docs/apps/PET.md',p)
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
        if any(n.lower().endswith(('.upg','.sav','.rom','.exe')) for n in z.namelist()):raise ValueError('Unexpected firmware/state')
    launcher_work=ROOT/'work/pet-branding-launcher'
    if launcher_work.is_dir():
        lr=json.loads((launcher_work/'build.json').read_text())
        for name,digest in lr['source_hashes'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Launcher source changed: '+name)
        launcher=launcher_work/'launcher.elf'
        if not lr['passed'] or sha(launcher)!=lr['sha256']:raise ValueError('Launcher verification failed')
        launcher_zip=out.parent/('NW-X1000-Pet-icons-launcher-'+lr['version']+'-manual-test.zip')
        if launcher_zip.exists():raise ValueError('Preserve existing launcher ZIP')
        instructions='Optional launcher update for the BSOD robot icon. No firmware. Exit Homebrew, connect USB and back up HOMEBREW/launcher/app on the computer. Copy only the included HOMEBREW/launcher/app to visible storage, then safely eject. Keep the backup to roll back. This does not install Pet, publish apps or update repository settings. Physical-player qualification is pending.\n'
        with zipfile.ZipFile(launcher_zip,'w',zipfile.ZIP_DEFLATED,6) as z:
            z.writestr('README.txt',instructions);z.write(launcher,'HOMEBREW/launcher/app');z.writestr('SHA256SUMS',sha(launcher)+'  HOMEBREW/launcher/app\n');z.write(launcher_work/'build.json','REVIEW/build.json');z.write(ROOT/'third_party/qqmusic-stb/Noto-OFL.txt','LICENSES/Noto-OFL.txt')
        with zipfile.ZipFile(launcher_zip) as z:
            if z.testzip() or z.read('HOMEBREW/launcher/app')!=launcher.read_bytes():raise ValueError('Launcher ZIP readback')
    result={'zip':str(archive.relative_to(ROOT)),'bytes':archive.stat().st_size,'sha256':sha(archive),'hardware_tested':False,'device_written':False,'firmware_created':False}
    (out.parent/'package.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
