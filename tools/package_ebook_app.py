"""Package reviewed external ebook app, font/mapping and original sample. No player I/O."""
from pathlib import Path
import json,hashlib,shutil,zipfile,subprocess
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-app';r=json.loads((w/'build.json').read_text());test=json.loads((ROOT/'work/ebook-tests/report.json').read_text());assert test['passed']
for n in ['full-book','full-book-arm','full-book-asan','malformed']:assert json.loads((ROOT/'work/epub-tests'/(n+'.json')).read_text())['passed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
app=w/'package/app';assert sha(app)==r['sha256']==test['cases'][-1]['sha256']
for n,h in r['source_hashes'].items():assert sha(ROOT/n)==h,n
project=(ROOT/'VERSION').read_text().strip();version=(ROOT/'runtime/apps/ebook/VERSION').read_text().strip();out=ROOT/'dist'/project/'ebook'/version;assert not out.exists(),'Preserve old package';out.mkdir(parents=True)
shutil.copytree(w/'package',out/'HOMEBREW/apps/ebook');(out/'HOMEBREW/data/ebook/books').mkdir(parents=True);shutil.copyfile(ROOT/'examples/books/阅读示例.txt',out/'HOMEBREW/data/ebook/books/阅读示例.txt')
shutil.copyfile(ROOT/'docs/apps/EBOOK.md',out/'README.md');shutil.copytree(ROOT/'third_party/ebook-data',out/'LICENSES');(out/'PREVIEW').mkdir()
for n in ['epub-miniz','epub-stb']:shutil.copytree(ROOT/'third_party'/n,out/'SOURCE/third_party'/n)
(out/'REVIEW').mkdir(exist_ok=True)
for p in (ROOT/'work/epub-tests').glob('*.json'):shutil.copyfile(p,out/'REVIEW'/p.name)
for p in (ROOT/'work/ebook-preview').glob('0[1-5]-*.png'):shutil.copyfile(p,out/'PREVIEW'/p.name)
(out/'REVIEW').mkdir(exist_ok=True)
for source,name in [(w/'build.json','build.json'),(ROOT/'work/ebook-tests/report.json','tests.json'),(ROOT/'work/ebook-data/encoding.json','encoding.json')]:shutil.copyfile(source,out/'REVIEW'/name)
for folder in ['runtime/apps/ebook','runtime/native']:shutil.copytree(ROOT/folder,out/'SOURCE'/folder,ignore=shutil.ignore_patterns('__pycache__','*.o'))
for folder,names in [('runtime/apps/emulators',['platform.c','platform.h']),('runtime/apps/dictionary',['dictionary.c','dictionary.h']),('runtime/store',['stock_fs_bridge.c','stock_fs_bridge.h','stock_stat64.c','stock_stat64.h','start.c','start.S'])]:
 for n in names:
  p=out/'SOURCE'/folder/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/folder/n,p)
for n in ['build_ebook_assets.py','build_ebook_encoding.py','prepare_ebook_fixtures.py','build_ebook_app.py','test_ebook_app.py','package_ebook_app.py','render_ebook.py','test_ebook.c','test_ebook_epub.c','test_ebook_epub.py','test_ebook_storage.c','render_ebook.c','fixtures/ebook_host_stat.c','fixtures/device_preload.c']:
 p=out/'SOURCE/tools'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'tools'/n,p)
shutil.copytree(ROOT/'examples/books',out/'SOURCE/examples/books');(out/'SOURCE/VERSION').write_text(project+'\n')
checks=[];lib=ROOT/'work/arm-signal-tests/lib';launcher=ROOT/'dist/0.1.0-dev.16/first-device-test-candidate8/02_PLAYER_FILES/HOMEBREW/launcher/app'
for command in ['--catalog','--check']:
 run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),command,str(out/'HOMEBREW/apps')],capture_output=True,text=True,timeout=20);assert run.returncode==0 and 'ebook'in run.stdout,(run.stdout,run.stderr);checks.append({'command':command,'stdout':run.stdout,'exit':run.returncode})
identity={'app_version':version,'id':'ebook','bytes':app.stat().st_size,'sha256':sha(app),'supported':'TXT UTF8/GB18030/UTF16; reflowable EPUB2/3, TOC, basic CSS, JPEG/PNG','max_book_bytes':67108864,'shelf_limit':128,'font_sizes':[16,20,24],'progress_slot_bytes':6208,'progress_slots':2,'checkpoints_seconds':30,'firmware_created':False,'device_written':False,'hardware_tested':False,'launcher_checks':checks};(out/'REVIEW/identity.json').write_text(json.dumps(identity,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
z=out.parent/('NW-X1000-ebook-'+version+'.zip');assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6)as a:
 for p in sorted(out.rglob('*')):
  if p.is_file():a.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(z)as a:
 assert a.testzip() is None
 for p in out.rglob('*'):
  if p.is_file():assert a.read(p.relative_to(out).as_posix())==p.read_bytes()
 assert not any(n.startswith('HOMEBREW/launcher')or n.lower().endswith(('.upg','.sav'))for n in a.namelist())
print(json.dumps({'zip':str(z),'zip_bytes':z.stat().st_size,'zip_sha256':sha(z),**identity},indent=2))
