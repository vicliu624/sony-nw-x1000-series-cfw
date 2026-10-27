"""Package reviewed native dictionary and read-only data; no device access."""
from pathlib import Path
import subprocess,json,hashlib,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/dictionary-app';build=json.loads((w/'build.json').read_text());test=json.loads((ROOT/'work/dictionary-tests/report.json').read_text());assert test['passed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
app=w/'package/app';assert sha(app)==build['sha256'];assert test['cases'][-1]['sha256']==sha(app)
for n,h in build['source_hashes'].items():assert sha(ROOT/n)==h,n
version=(ROOT/'runtime/apps/dictionary/VERSION').read_text().strip();project=(ROOT/'VERSION').read_text().strip();out=ROOT/'dist'/project/'dictionary'/version;assert not out.exists(),'Preserve previous package';out.mkdir(parents=True)
shutil.copytree(w/'package',out/'PLAYER/HOMEBREW/apps/dictionary')
(out/'PREVIEW').mkdir()
for p in (ROOT/'work/dictionary-preview').glob('*.png'):shutil.copyfile(p,out/'PREVIEW'/p.name)
shutil.copyfile(ROOT/'docs/apps/DICTIONARY.md',out/'README.md');shutil.copytree(ROOT/'third_party/dictionary-data',out/'LICENSES')
(out/'REVIEW').mkdir();shutil.copyfile(w/'build.json',out/'REVIEW/build.json');shutil.copyfile(ROOT/'work/dictionary-tests/report.json',out/'REVIEW/tests.json')
for folder in ['runtime/apps/dictionary','runtime/native']:
 shutil.copytree(ROOT/folder,out/'SOURCE'/folder,ignore=shutil.ignore_patterns('*.o','__pycache__'))
for n in ['platform.c','platform.h']:
 p=out/'SOURCE/runtime/apps/emulators'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'runtime/apps/emulators'/n,p)
(out/'SOURCE/VERSION').write_text(project+'\n')
for n in ['stock_fs_bridge.c','stock_fs_bridge.h','stock_stat64.c','stock_stat64.h','start.c','start.S']:
 p=out/'SOURCE/runtime/store'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'runtime/store'/n,p)
for n in ['build_dictionary_data.py','build_dictionary_app.py','test_dictionary_app.py','package_dictionary_app.py','test_dictionary.c','render_dictionary.c','fixtures/dictionary_host_stat.c','fixtures/device_preload.c']:
 p=out/'SOURCE/tools'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'tools'/n,p)
# Verify discovery and executable integrity against the production launcher.
lib=ROOT/'work/arm-signal-tests/lib';launcher=ROOT/'dist/0.1.0-dev.16/first-device-test-candidate8/02_PLAYER_FILES/HOMEBREW/launcher/app'
for command in ['--catalog','--check']:
 r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),command,str(out/'PLAYER/HOMEBREW/apps')],capture_output=True,text=True,timeout=20);assert r.returncode==0 and 'dictionary'in r.stdout,(r.stdout,r.stderr)
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
z=out.parent/('NW-X1000-dictionary-'+version+'.zip');assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6)as archive:
 for p in sorted(out.rglob('*')):
  if p.is_file():archive.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(z)as archive:
 assert archive.testzip() is None
 for p in out.rglob('*'):
  if p.is_file():assert archive.read(p.relative_to(out).as_posix())==p.read_bytes()
print(json.dumps({'zip':str(z),'bytes':z.stat().st_size,'sha256':sha(z),'app_bytes':app.stat().st_size,'entries':build['assets']['entries'],'hardware_tested':False,'device_written':False},indent=2))
