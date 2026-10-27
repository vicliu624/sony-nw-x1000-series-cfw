"""Read-only candidate audit; separate artifact consistency from device qualification."""
from pathlib import Path
import hashlib,io,json,tarfile
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
manifest=json.loads((area/'manifest.json').read_text());assert manifest['version']==version
native=json.loads((ROOT/'work/native-frontend-build.json').read_text())
home=json.loads((ROOT/'work/home-entry-candidate/candidate.json').read_text())
assert native['version']==home['version']==version
verified=[]
for entry in manifest['files']:
    path=(area/entry['path']).resolve();assert path.is_relative_to(area.resolve())
    data=path.read_bytes();assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
    assert path.suffix.lower() not in ('.py','.pyc','.upg','.exe')
    verified.append(entry['path'])
launcher=(area/'external/HOMEBREW/launcher/app').read_bytes()
assert launcher[:6]==b'\x7fELF\x01\x01' and hashlib.sha256(launcher).hexdigest()==native['sha256']
assert hashlib.sha256((area/'system-overlay/usr/local/bin/SpiderApp').read_bytes()).hexdigest()==home['candidate_sha256']
overlays={entry['path'].removeprefix('system-overlay/') for entry in manifest['files'] if entry['path'].startswith('system-overlay/')}
expected={'usr/local/bin/SpiderApp','etc/AppList.conf',
          'usr/local/share/gemini/res/swd/ucs2-dev-sid-000-10.swd','usr/local/share/gemini/res/swd/ucs2-dev-sid-000-11.swd'}
expected|={'usr/local/share/gemini/res/stx/ucs2-dev-'+language+'.stx' for language in ('en','jp','fr','de','it','es','cs','ct','ru','kr','pt')}
assert overlays==expected
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
    stock=tar.extractfile('./etc/AppList.conf').read()
    assert all(tar.getmember('./'+path).isfile() for path in overlays)
fragment=(area/'review/AppList.fragment.NOT_INSTALLED').read_bytes()
assert (area/'system-overlay/etc/AppList.conf').read_bytes()==stock+(b'' if stock.endswith(b'\n') else b'\n')+fragment
full=json.loads((ROOT/'sources/native-applist-full-config.json').read_text());assert full['original_registrations_preserved']
contract=(ROOT/'sources/native-entry-exit-contract.json').read_bytes();latest=json.loads(contract)
staged=(area/'review/entry-exit-evidence.json').read_bytes()
assert latest['all_passed'] and not latest['Sony_return_validated']
for key,evidence in latest['reports'].items():
    current=(ROOT/'sources'/key).read_bytes()
    assert hashlib.sha256(current).hexdigest()==evidence['sha256'],key
assert latest['reports']['native-proxy-frontend-contract.json']['evidence']['program_sha256']==native['sha256']
footprint=json.loads((ROOT/'sources/native-installation-footprint.json').read_text())
assert footprint['version']==version and footprint['dense_measurement_overlay_equivalence']['matches']
identity_path=ROOT/'sources/native-device-target-match.json'
identity=json.loads(identity_path.read_text()) if identity_path.exists() else None
if identity:
    current_device=json.loads((ROOT/'sources/device-under-test.json').read_text())
    assert identity['reported_device']==current_device and identity['model_version_configuration_match']
result={'version':version,'structural_offline_checks_passed':True,'verified_manifest_files':len(verified),
        'system_overlay_paths':sorted(overlays),'original_config_prefix_preserved':True,
        'external_native_launcher_matches_build':True,'all_bounded_evidence_hashes_match':True,
        'staged_evidence_matches_latest':staged==contract,
        'local_dense_fit_equivalent':True,'system_block_growth_bytes':footprint['ext2_regular_file_growth_bytes'],
        'device_runtime_language':'C plus ARM assembly; no added Python payload',
        'ready_to_flash':False,'device_qualification_complete':False,'firmware_package_created':False,
        'remaining_required':['Matching Japanese physical model/current firmware information (user has hardware, details pending).',
                              'Verify actual partition mapping/capacity against stock148MiB definition.',
                              'Actual display/touch release and recovery, original IPC/process scheduling and native application execution.',
                              'USB handoff through actual storage unmount/export and reconnection.',
                              'Matching recovery evidence and final installer review before any later flashable-package request.'],
        'separate_product_work':['App store/download/install not implemented.','Homebrew entry still reuses Settings icon.'],
        'limits':['Bounded simulated checks do not qualify a physical player.','Audit reads local files only; no device or updater operations.']}
if identity:
    result['reported_device']=identity['reported_device']
    result['reported_model_version_matches_stock_configuration']=True
    result['remaining_required']=result['remaining_required'][1:]
    result['remaining_required'].insert(0,'User reports Japanese NW-X1060/1.11, matching stock DEVICE01; actual device identity and hardware configuration not read.')
(ROOT/'sources/native-integration-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
