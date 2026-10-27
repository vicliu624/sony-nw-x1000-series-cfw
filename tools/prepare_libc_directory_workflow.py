"""Stage exact existing files with the new libc runtime for offline tests only."""
from pathlib import Path
import hashlib,json,shutil,argparse,re
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='work/libc-directory-workflow-fixture');parser.add_argument('--profile',default='libc-directory-workflow-fixture');parser.add_argument('--store-build-report');parser.add_argument('--store-failure-report');parser.add_argument('--graphics-build-report');options=parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]+',options.profile)
old=ROOT/'work/libc-product-review-0.1.0-dev.16-r3';output=(ROOT/options.output).resolve();assert output.is_relative_to(ROOT/'work') and output!=ROOT/'work'
assert not output.exists(),'Preserve existing fixture; use its manifest or a new revision explicitly'
manifest=json.loads((old/'manifest.json').read_text());build=verify_report(ROOT,'work/libc-directory-review/build.json');tests=verify_report(ROOT,'sources/native-libc-file-backend-tests.json');assert build['passed'] and tests['passed']
extra_inputs=[];app_overrides={}
if options.store_build_report:
 assert options.store_failure_report
 store=verify_report(ROOT,options.store_build_report);failure=verify_report(ROOT,options.store_failure_report)
 assert store['runtime_backend']=='stock-libc' and failure['all_bounded_checks_passed'] and failure['candidate_sha256']==store['sha256']
 app_overrides['store']=ROOT/store['artifact'];extra_inputs += [ROOT/options.store_build_report,ROOT/options.store_failure_report]
if options.graphics_build_report:
 graphics=verify_report(ROOT,options.graphics_build_report);assert graphics['passed']
 app_overrides['graphics-demo']=ROOT/graphics['artifact'];extra_inputs.append(ROOT/options.graphics_build_report)
for row in manifest['files']:
 source=old/row['path'];assert source.resolve().is_relative_to(old.resolve()) and not source.is_symlink()
 assert source.stat().st_size==row['bytes'] and hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
output.mkdir()
for row in manifest['files']:
 destination=output/row['path'];destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/row['path'],destination)
 if destination.name=='app':destination.chmod(0o755)
launcher=output/'external/HOMEBREW/launcher/app';shutil.copyfile(ROOT/build['artifact'],launcher);launcher.chmod(0o755)
for app_id,source in app_overrides.items():
 assert source.resolve().is_relative_to(ROOT/'work')
 target=output/'external/HOMEBREW/apps'/app_id
 for name in ('app','app.ini','files.sha256'):
  if (source.parent/name).is_file():shutil.copyfile(source.parent/name,target/name)
 (target/'app').chmod(0o755)
(output/'REVIEW.txt').write_text('OFFLINE WORKFLOW FIXTURE ONLY - NOT INSTALLABLE\nSelected libc runtime/app overrides; original r3 system overlay unchanged.\nNo firmware, device execution or hardware qualification.\n')
rows=[]
for path in sorted(output.rglob('*')):
 if path.is_file():rows.append({'path':str(path.relative_to(output)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
result={'version':(ROOT/'VERSION').read_text().strip(),'profile':options.profile,'files':rows,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),old/'manifest.json',ROOT/'work/libc-directory-review/build.json',ROOT/'sources/native-libc-file-backend-tests.json',*extra_inputs]},'ready_to_flash':False,'hardware_tested':False,'firmware_created':False}
(output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print('Staged offline libc directory workflow fixture; r3 left unchanged.')
