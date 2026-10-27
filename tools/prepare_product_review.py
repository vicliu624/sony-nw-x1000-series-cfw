"""Compose existing pinned artifacts into one local review tree; never build/install firmware."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,tempfile
from evidence_checks import verify_report
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');parser.add_argument('--revision',type=int,default=1);parser.add_argument('--launcher-build-report');parser.add_argument('--launcher-tests-report');parser.add_argument('--store-build-report');parser.add_argument('--store-tests-report');parser.add_argument('--integration-tests-report',action='append',default=[]);options=parser.parse_args()
    assert options.revision>0
    if options.launcher_build_report:assert options.revision>=2 and options.launcher_tests_report
    else:assert not options.launcher_tests_report
    if options.store_build_report:assert options.revision>=4 and options.store_tests_report
    else:assert not options.store_tests_report
    version=(ROOT/'VERSION').read_text().strip()
    baseline=ROOT/'work'/('integration-'+version);external=ROOT/'work'/('network-external-'+version)
    output=ROOT/'work'/('product-review-'+version+('-r'+str(options.revision) if options.revision>1 else ''))
    bm=json.loads((baseline/'manifest.json').read_text());em=json.loads((external/'manifest.json').read_text())
    assert bm['version']==em['version']==version
    protected=[ROOT/'VERSION',baseline/'manifest.json']+[baseline/row['path'] for row in bm['files']]
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    for row in bm['files']:
        source=(baseline/row['path']).resolve();assert source.is_relative_to(baseline.resolve()) and not (baseline/row['path']).is_symlink()
        assert source.stat().st_size==row['bytes'] and sha(source)==row['sha256']
    for row in em['files']:
        source=(external/row['path']).resolve();assert source.is_relative_to(external.resolve()) and not (external/row['path']).is_symlink()
        assert source.stat().st_size==row['bytes'] and sha(source)==row['sha256']
    store_build_relative=options.store_build_report or 'sources/native-network-store-app-build.json'
    build=verify_report(ROOT,store_build_relative)
    layout=verify_report(ROOT,'sources/native-network-external-layout.json')
    lifecycle=verify_report(ROOT,'sources/native-home-entry-lifecycle-suite.json')
    footprint=verify_report(ROOT,'sources/native-installation-footprint.json')
    assert layout['review_manifest_sha256']==sha(external/'manifest.json')
    assert not em['repository_configured'] and not em['sample_CA_or_keys_included']
    assert sha(external/'HOMEBREW/launcher/app')==sha(baseline/'external/HOMEBREW/launcher/app')
    assert build['version']==version
    store_source=external/'HOMEBREW/apps/store/app'
    store_extra_inputs=[]
    if options.store_build_report:
        store_source=(ROOT/build['artifact']).resolve();assert store_source.is_relative_to(ROOT/'work') and build['review_only'] is True
        store_tests=verify_report(ROOT,options.store_tests_report)
        assert store_tests['all_bounded_checks_passed'] and store_tests['candidate_sha256']==build['sha256']
        verify_report(ROOT,'sources/native-store-platform-tests.json')
        store_extra_inputs=[ROOT/options.store_tests_report,ROOT/'sources/native-store-platform-tests.json']
    assert sha(store_source)==build['sha256']
    launcher_source=external/'HOMEBREW/launcher/app'
    extra_inputs=store_extra_inputs.copy()
    if options.launcher_build_report:
        candidate=verify_report(ROOT,options.launcher_build_report);tests=verify_report(ROOT,options.launcher_tests_report)
        assert candidate['version']==version and candidate['review_only'] is True
        launcher_source=(ROOT/candidate['artifact']).resolve();assert launcher_source.is_relative_to(ROOT/'work')
        assert tests['all_bounded_checks_passed'] and tests['program_sha256']==candidate['sha256'] and tests['artifact']==candidate['artifact']
        extra_inputs += [ROOT/options.launcher_build_report,ROOT/options.launcher_tests_report]
    overlay=[row for row in bm['files'] if row['path'].startswith('system-overlay/')]
    assert len(overlay)==15
    for row in overlay:
        relative=row['path'][len('system-overlay/'):]
        measured=next(change for change in footprint['changes'] if change['path']==relative)
        assert measured['after_sha256']==row['sha256']
    inputs=[baseline/'manifest.json',external/'manifest.json',ROOT/'VERSION',Path(__file__)]+[ROOT/'sources'/name for name in ('native-network-external-layout.json','native-home-entry-lifecycle-suite.json','native-installation-footprint.json')]
    for integration_relative in options.integration_tests_report:
        integration=verify_report(ROOT,integration_relative)
        assert integration['all_bounded_checks_passed'] and integration['physical_device_access'] is False
        extra_inputs.append(ROOT/integration_relative)
    inputs += [ROOT/store_build_relative,*extra_inputs]
    input_hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    if options.check:
        manifest=json.loads((output/'manifest.json').read_text())
        assert manifest['source_hashes']==input_hashes,'Inputs changed; review tree must be regenerated explicitly, not relabeled'
    else:
        assert not output.exists(),'Review tree already exists; use --check. Preserve before preparing another revision.'
        staging=Path(tempfile.mkdtemp(prefix='product-review-',dir=ROOT/'work'))
        records=[]
        def copy(source,target,role):
            destination=staging/target;assert destination.resolve().is_relative_to(staging.resolve())
            assert destination.suffix.lower() not in ('.py','.pyc','.upg','.exe','.zip')
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
            if destination.name=='app':destination.chmod(0o755)
            records.append({'path':target,'role':role,'bytes':destination.stat().st_size,'sha256':sha(destination)})
        for row in overlay:copy(baseline/row['path'],row['path'],'Sony system overlay; binary hook/resources, local review only')
        for row in em['files']:
            source=external/row['path']
            if row['path']=='HOMEBREW/launcher/app':source=launcher_source
            elif row['path']=='HOMEBREW/apps/store/app':source=store_source
            elif row['path']=='HOMEBREW/apps/store/app.ini':source=store_source.parent/'app.ini'
            copy(source,'external/'+row['path'],'External native launcher/store/configuration notes')
        for folder in ('cache','data','packages','repository'):(staging/'external/HOMEBREW'/folder).mkdir(exist_ok=True)
        notes=('LOCAL REVIEW ONLY — DO NOT INSTALL\n\n'
               'system-overlay/: existing dev.16 Sony menu hook and resources, unchanged.\n'
               'external/HOMEBREW/: native launcher and Network Store together.\n'
               'Repository endpoint and CA are not configured. No keys, ROMs or Python payload.\n'
               'This directory is not a firmware/update/install package. No device was written.\n'
               'Sony lifecycle/GUI and USB behavior remain hardware-unqualified.\n')
        (staging/'REVIEW.txt').write_text(notes,encoding='utf-8')
        records.append({'path':'REVIEW.txt','role':'Review instructions','bytes':(staging/'REVIEW.txt').stat().st_size,'sha256':sha(staging/'REVIEW.txt')})
        manifest={'version':version,'profile':'network-store-product-review','composition_revision':options.revision,'launcher_build_report':options.launcher_build_report,'launcher_tests_report':options.launcher_tests_report,'store_build_report':options.store_build_report,'store_tests_report':options.store_tests_report,'integration_tests_report':options.integration_tests_report,'scope':'Unified local review tree, not firmware or a device installation',
                  'files':records,'source_hashes':input_hashes,'apps_included':['store'],'repository_configured':False,
                  'launcher_bytes':(staging/'external/HOMEBREW/launcher/app').stat().st_size,'store_bytes':build['bytes'],
                  'system_overlay_paths':len(overlay),'system_block_growth_model_bytes':footprint['ext2_regular_file_growth_bytes'],
                  'capacity_qualified':False,'hardware_qualified':False,'ready_to_flash':False,'firmware_package_created':False,'physical_device_access':False,
                  'remaining':['Original menu execution and complete GUI/display/touch lifecycle on hardware.',
                               'Actual USB app stop, user-storage unmount/export/reconnect.',
                               'Repository endpoint/CA configuration and real Wi-Fi/time/download/install qualification.',
                               'Actual partition capacity and matching recovery evidence.',
                               'Startup-state, page-rebuild and backend model assumptions remain; no full boot established.']}
        (staging/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        staging.rename(output)
    expected={row['path'] for row in manifest['files']}|{'manifest.json'}
    assert {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}==expected
    for row in manifest['files']:
        path=output/row['path'];assert not path.is_symlink() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    launcher=output/'external/HOMEBREW/launcher/app';apps=output/'external/HOMEBREW/apps';checks={}
    for argument in ('--catalog','--check'):
        result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(launcher),argument,str(apps)],capture_output=True,text=True,timeout=15)
        assert result.returncode==0,(argument,result.stdout,result.stderr)
        assert '/dev/fb/' not in result.stderr and '/dev/icx_touch_screen' not in result.stderr
        checks[argument]=result.stdout
    assert checks=={'--catalog':'store\tNetwork Store\n','--check':'store VERIFIED\n'},checks
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in protected}
    report={'all_bounded_checks_passed':True,'review_directory':str(output.relative_to(ROOT)),'review_manifest_sha256':sha(output/'manifest.json'),
            'files_checked':len(manifest['files']),'catalog_checks':checks,'protected_files_unchanged':True,'physical_device_access':False,
            'hardware_qualified':False,'firmware_package_created':False,'source_hashes':{**input_hashes,str((output/'manifest.json').relative_to(ROOT)):sha(output/'manifest.json')},
            'limits':['Composition uses existing pinned local candidates, not a clean-input firmware build.',
                      'Catalog/check run the actual launcher ELF under QEMU, never launch store or access player devices.',
                      'No claim of successful combined display/network/Sony return or real installation.']}
    (ROOT/'sources/native-product-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'review':str(output.relative_to(ROOT)),'system_files':len(overlay),'apps':manifest['apps_included'],'launcher_store_discovery':True,'baseline_unchanged':True,'ready_to_flash':False},indent=2))
if __name__=='__main__':main()
