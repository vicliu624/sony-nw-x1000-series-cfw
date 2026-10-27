"""Compose current libc launcher with unchanged Sony overlay and external apps; never firmware."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,tempfile
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');parser.add_argument('--revision',type=int,default=3);options=parser.parse_args();assert options.revision>0
version=(ROOT/'VERSION').read_text().strip();old=ROOT/'work'/('product-review-'+version+'-r7')
output=ROOT/'work'/('libc-product-review-'+version+'-r'+str(options.revision))
original=json.loads((old/'manifest.json').read_text())
for row in original['files']:
 p=old/row['path'];assert p.resolve().is_relative_to(old.resolve()) and not p.is_symlink()
 assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
reports=['work/libc-launcher-review/build.json','sources/native-posix-full-loop-tests.json','sources/native-posix-launch-signal-race.json','sources/native-release-failure-tests.json','sources/native-posix-signal-tests.json','sources/native-libc-device-call-tests.json','sources/native-libc-device-failure-tests.json','work/graphics-demo-review/build.json','work/libc-device-store-review/build.json','sources/native-store-platform-tests.json','sources/native-libc-store-failure.json']
loaded={}
for relative in reports:
 report=verify_report(ROOT,relative)
 if 'passed' in report:assert report['passed'] is True
 if 'artifact' in report and 'sha256' in report:assert sha(ROOT/report['artifact'])==report['sha256']
 loaded[relative]=report
launcher=loaded['work/libc-launcher-review/build.json'];demo=loaded['work/graphics-demo-review/build.json'];store=loaded['work/libc-device-store-review/build.json']
assert launcher['passed'] and demo['passed']
assert store['device_io_backend']=='stock-libc'
assert loaded['sources/native-libc-store-failure.json']['candidate_sha256']==store['sha256']
inputs=[Path(__file__),ROOT/'VERSION',old/'manifest.json',*[ROOT/r for r in reports]]
input_hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
if options.check:
 manifest=json.loads((output/'manifest.json').read_text());assert manifest['source_hashes']==input_hashes
 assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}=={r['path'] for r in manifest['files']}|{'manifest.json'}
 for row in manifest['files']:
  p=output/row['path'];assert p.resolve().is_relative_to(output.resolve()) and not p.is_symlink()
  assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
else:
 assert not output.exists(),'Preserve existing composition; --check only'
 staging=Path(tempfile.mkdtemp(prefix='libc-product-',dir=ROOT/'work'))
 for row in original['files']:
  target=staging/row['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/row['path'],target)
 shutil.copyfile(ROOT/launcher['artifact'],staging/'external/HOMEBREW/launcher/app')
 store_source=ROOT/store['artifact']
 for name in ('app','app.ini'):shutil.copyfile(store_source.parent/name,staging/'external/HOMEBREW/apps/store'/name)
 demo_source=(ROOT/demo['artifact']).parent
 shutil.copytree(demo_source,staging/'external/HOMEBREW/apps/graphics-demo')
 (staging/'REVIEW.txt').write_text('LOCAL REVIEW ONLY - DO NOT INSTALL\nStock-libc launcher; unchanged r7 Sony overlay. External Network Store and C graphics example.\nNo firmware, updater, deployment, hardware qualification, configured repository or recovery guarantee.\nOld Sony lifecycle evidence is historical; this combination is not newly lifecycle-qualified.\n')
 records=[]
 for p in sorted(staging.rglob('*')):
  if not p.is_file():continue
  relative=str(p.relative_to(staging));assert p.suffix.lower() not in ('.py','.pyc','.exe','.upg','.zip')
  if p.name=='app':p.chmod(0o755)
  records.append({'path':relative,'bytes':p.stat().st_size,'sha256':sha(p)})
 overlay=[r for r in records if r['path'].startswith('system-overlay/')];assert len(overlay)==15
 assert overlay==sorted([{'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256']} for r in original['files'] if r['path'].startswith('system-overlay/')],key=lambda r:r['path'])
 manifest={'version':version,'profile':'stock-libc-product-review','composition_revision':options.revision,'files':records,'source_hashes':input_hashes,'apps_included':['store','graphics-demo'],'system_overlay_paths':15,'ready_to_flash':False,'hardware_tested':False,'firmware_created':False,'repository_configured':False,'limits':['Sony overlay byte identity only; historical lifecycle evidence not current-source qualification.','Linked test harnesses exercise app return, not physical driver or Sony UI integration.','No capacity, recovery, Wi-Fi or USB handoff qualification.']}
 (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');staging.rename(output)
lib=ROOT/'work/arm-signal-tests/lib';app=output/'external/HOMEBREW/launcher/app';apps=output/'external/HOMEBREW/apps'
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)]
for command in ('--catalog','--check'):
 result=subprocess.run(base+[command,str(apps)],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,(command,result.stdout,result.stderr)
 if command=='--check':assert set(result.stdout.splitlines())=={'store VERIFIED','graphics-demo VERIFIED'}
 else:assert result.stdout.splitlines()[0]=='store\tNetwork Store'
 print(result.stdout,end='')
print(str(output.relative_to(ROOT))+': review only; no firmware or hardware qualification.')




