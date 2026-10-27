"""Offline actual-ELF app/store workflows. Not Sony hardware or flash qualification."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import argparse,hashlib,json,subprocess,sys,os
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=[
 ('test_libc_proxy_entry.py','native-libc-proxy-entry-tests.json'),
 ('test_libc_production_ui.py','native-libc-production-ui-tests.json'),
 ('test_libc_production_app_loop.py','native-libc-production-app-loop-tests.json'),
 ('test_libc_production_store_loop.py','native-libc-production-store-loop-tests.json'),
 ('test_production_store_catalog.py','native-production-store-catalog-tests.json'),
 ('test_production_store_install.py','native-production-store-install-tests.json'),
 ('test_production_store_launcher.py','native-production-store-launcher-tests.json'),
 ('test_production_store_reject.py','native-production-store-reject-tests.json'),
 ('test_production_store_trust.py','native-production-store-trust-tests.json'),
 ('test_production_store_stop.py','native-production-store-stop-tests.json'),
 ('test_production_store_recovery.py','native-production-store-recovery-tests.json')]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify-only',action='store_true');parser.add_argument('--profile');parser.add_argument('--composition');options=parser.parse_args()
if options.profile:os.environ['HB_WORKFLOW_PROFILE']=options.profile
if options.composition:os.environ['HB_WORKFLOW_COMPOSITION']=options.composition
work=work_area(ROOT,'actual-app-workflows')
if not options.verify_only:
 for script,report in SCENARIOS:
  with (work/(script+'.log')).open('w') as log:
   subprocess.run([sys.executable,str(ROOT/'tools'/script)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
  print('Passed:',script,flush=True)
# Check every report again at the end: shared test libraries must stay stable.
tracked=[Path(__file__),ROOT/'VERSION'];rows=[]
for script,relative in SCENARIOS:
 path=evidence_path(ROOT,relative);report=verify_report(ROOT,str(path.relative_to(ROOT)))
 assert report['composition']==str(composition_path(ROOT).relative_to(ROOT))
 assert report['passed'] is True
 tracked += [ROOT/'tools'/script,path]
 rows.append({'script':script,'report':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
composition=composition_path(ROOT);manifest=json.loads((composition/'manifest.json').read_text())
for row in manifest['files']:
 path=composition/row['path'];assert path.resolve().is_relative_to(composition.resolve()) and not path.is_symlink()
 assert path.stat().st_size==row['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
tracked.append(composition/'manifest.json')
result={'passed':True,'scope':'actual selected app-side workflow checks, not hardware or original Sony lifecycle qualification','composition':str(composition.relative_to(ROOT)),'scenarios':rows,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'firmware_created':False,'limits':['Virtual devices/path translation and explicit QEMU exec bridge remain.','Local TLS test roots/keys exist only in host fixtures.','No Sony GUI/proxy, real USB export, FAT storage, physical capacity/recovery or flashing qualification.']}
write_report(ROOT,'native-actual-app-workflows.json',result)
print('All actual-app workflow reports current; candidate files unchanged. Hardware/flash qualification remains false.')
