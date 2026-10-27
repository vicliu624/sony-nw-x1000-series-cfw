"""External-only review layout; no updater, system overlay, deployment or flash."""
from pathlib import Path
import hashlib,json,subprocess,sys,shutil,tempfile,struct
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();baseline=ROOT/'work'/('integration-'+version)
original_manifest=(baseline/'manifest.json').read_bytes();manifest=json.loads(original_manifest)
assert manifest['version']==version
protected=[ROOT/'VERSION',baseline/'manifest.json']+[baseline/f['path'] for f in manifest['files']]
def snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=snapshot()
for item in manifest['files']:assert hashlib.sha256((baseline/item['path']).read_bytes()).hexdigest()==item['sha256']
subprocess.run([sys.executable,str(ROOT/'tools/build_network_store_app.py')],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'tools/test_network_store_candidate_failure.py')],cwd=ROOT,check=True)
build=json.loads((ROOT/'sources/native-network-store-app-build.json').read_text());app=ROOT/build['artifact'];assert hashlib.sha256(app.read_bytes()).hexdigest()==build['sha256']
work=ROOT/'work'/('network-external-'+version);work.mkdir(exist_ok=True)
home=work/'HOMEBREW';launcher=home/'launcher';store=home/'apps/store'
allowed={'launcher/app','apps/store/app','apps/store/app.ini','repository/README.txt'}
if home.exists():
 assert all(str(p.relative_to(home)) in allowed and not p.is_symlink() for p in home.rglob('*') if p.is_file() or p.is_symlink()),'Unexpected file in review layout; preserve and inspect manually'
for p in (launcher,store,home/'cache',home/'packages',home/'repository'):p.mkdir(parents=True,exist_ok=True)
shutil.copyfile(baseline/'external/HOMEBREW/launcher/app',launcher/'app')
shutil.copyfile(app,store/'app');shutil.copyfile(app.parent/'app.ini',store/'app.ini');(launcher/'app').chmod(0o755);(store/'app').chmod(0o755)
(work/'NOT-INSTALLED.txt').write_text('External-only offline review layout. Not installed or hardware-qualified.\nNo system overlay or firmware package. Repository files intentionally absent.\n')
(home/'repository/README.txt').write_text('Provide a user-selected repository.conf and ca.der before native use.\nNo default endpoint, test certificate or key is included. See docs/apps/STORE.md.\n')
checks=[];traces=[]
def inspect(folder):
 results={}
 for option in ('--catalog','--check'):
  run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(launcher/'app'),option,str(folder)],capture_output=True,text=True,timeout=15)
  assert run.returncode==0,(option,run.returncode,run.stdout,run.stderr[-4000:])
  assert '/dev/fb/' not in run.stderr and '/dev/icx_touch_screen' not in run.stderr
  results[option]=run.stdout;traces.append(run.stderr)
 assert results['--catalog'].splitlines()[0]=='store\tNetwork Store'
 assert 'store VERIFIED' in results['--check'];return results
checks.append({'case':'review_layout','output':inspect(home/'apps')})
with tempfile.TemporaryDirectory(prefix='catalog-fixture-',dir=work) as temp:
 folder=Path(temp);demo=folder/'aaa-demo';demo.mkdir()
 data=bytearray(84);data[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',data,16,2,40);data=bytes(data)
 (demo/'app').write_bytes(data)
 (demo/'app.ini').write_text('api=1\nid=aaa-demo\nname=Demo\nversion=0.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes=84\nsha256='+hashlib.sha256(data).hexdigest()+'\n')
 shutil.copytree(store,folder/'store')
 checks.append({'case':'store_priority_with_other_app','output':inspect(folder)})
 # The synthetic ELF is metadata/hash input only, never executed.
assert before==snapshot()
files=[{'path':str(p.relative_to(work)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(home.rglob('*')) if p.is_file()]
review={'version':version,'scope':'External-only review tree, NOT installed or hardware-qualified','files':files,'system_overlay_included':False,'firmware_package_created':False,'ROMs_included':False,'sample_CA_or_keys_included':False,'repository_configured':False,'baseline_unchanged':True,'physical_device_access':False}
(work/'manifest.json').write_text(json.dumps(review,indent=2)+'\n')
report={'all_bounded_checks_passed':True,'physical_device_access':False,'baseline_unchanged':True,'review_manifest':str((work/'manifest.json').relative_to(ROOT)),'review_manifest_sha256':hashlib.sha256((work/'manifest.json').read_bytes()).hexdigest(),'checks':checks,'trace':'\n'.join(traces),'source_hashes':{'tools/prepare_network_external.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'limits':['Current dev.16 local baseline is an explicit input; not a clean-input release build.','QEMU launcher catalog/check reads files, never launches store or synthetic app.','No successful native display, Wi-Fi or Sony return qualification.','Layout has empty cache/packages/repository; production repository config not supplied.','No updater, system overlay, device write or flash package.']}
(ROOT/'sources/native-network-external-layout.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'review':str(work.relative_to(ROOT)),'store_bytes':build['bytes'],'launcher_discovered_store_first':True,'baseline_unchanged':True},indent=2))
