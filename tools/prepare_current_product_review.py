"""Bind current libc apps, unchanged Sony overlay and actual execution evidence.

PC-only local review tree. No UPG, installer, deployment or device operations.
"""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,tarfile,tempfile
from evidence_checks import verify_report

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def records(folder):
    result=[]
    for path in sorted(folder.rglob('*')):
        assert not path.is_symlink(),path
        if path.is_file() and path.name!='manifest.json':
            result.append({'path':str(path.relative_to(folder)),'bytes':path.stat().st_size,'sha256':sha(path)})
    return result

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check',action='store_true')
options=parser.parse_args()
version=(ROOT/'VERSION').read_text().strip()
output=ROOT/'work'/('libc-product-review-'+version+'-r4')
fixture=ROOT/'work/store-setup-workflow-fixture'
old=ROOT/'work'/('libc-product-review-'+version+'-r3')
packed=ROOT/'work/upg-jp/verified-3.bin'
assert sha(packed)=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
reports={
    'launcher':'work/libc-directory-review/build.json',
    'store':'work/store-setup-review/build.json',
    'graphics':'work/libc-apps-graphics-review/build.json',
    'store_failure':'sources/native-store-setup-failure.json',
    'workflows':'sources/workflow-profiles/store-setup/native-actual-app-workflows.json',
    'manager':'work/arm-system-manager-live-review-r4/system-probe.json',
}
loaded={key:verify_report(ROOT,path) for key,path in reports.items()}
assert loaded['launcher']['passed'] and loaded['graphics']['passed']
assert loaded['store']['runtime_backend']=='stock-libc'
assert loaded['store_failure']['all_bounded_checks_passed']
assert loaded['store_failure']['candidate_sha256']==loaded['store']['sha256']
workflow=loaded['workflows'];manager=loaded['manager']
assert workflow['passed'] and workflow['composition']==str(fixture.relative_to(ROOT))
assert len(workflow['scenarios'])==11
for case in workflow['scenarios']:
    assert sha(ROOT/case['report'])==case['sha256']
    assert verify_report(ROOT,case['report'])['passed']
assert manager['passed'] and manager['test_home_client_not_sony_gui']
assert not manager['process_calls_interposed'] and not manager['ipc_interposed'] and not manager['mount_interposed']
manifest=json.loads((fixture/'manifest.json').read_text())
previous=json.loads((old/'manifest.json').read_text())
for row in manifest['files']:
    path=fixture/row['path'];assert path.resolve().is_relative_to(fixture.resolve()) and not path.is_symlink()
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
selected={'launcher':'external/HOMEBREW/launcher/app','store':'external/HOMEBREW/apps/store/app','graphics':'external/HOMEBREW/apps/graphics-demo/app'}
elfs={};dependencies={}
for name,relative in selected.items():
    path=fixture/relative;assert sha(path)==loaded[name]['sha256']
    assert path.read_bytes()[:6]==b'\x7fELF\x01\x01'
    symbols=subprocess.check_output(['arm-linux-gnueabi-nm',str(path)],text=True)
    assert 'x1000_oabi_call' not in symbols and 'x1000_rt_sigreturn' not in symbols
    dynamic=subprocess.check_output(['arm-linux-gnueabi-readelf','-d',str(path)],text=True)
    dependencies[name]=[line.split('[')[1].split(']')[0] for line in dynamic.splitlines() if '(NEEDED)' in line]
    assert 'libc.so.6' in dependencies[name]
    elfs[name]={'path':relative,'bytes':path.stat().st_size,'sha256':sha(path)}
    # The manager actually ran these exact two programs; store is covered by workflows.
    if name!='store':assert manager['source_hashes'][str(path.relative_to(ROOT))]==sha(path)
overlay=[row for row in manifest['files'] if row['path'].startswith('system-overlay/')]
old_overlay=[row for row in previous['files'] if row['path'].startswith('system-overlay/')]
assert overlay==old_overlay and len(overlay)==15
system_delta=0
with tarfile.open(packed,'r:gz') as archive:
    for row in overlay:
        member=archive.getmember('./'+row['path'].removeprefix('system-overlay/'));assert member.isfile()
        system_delta+=row['bytes']-member.size
old_sizes={name:next(row['bytes'] for row in previous['files'] if row['path']==relative) for name,relative in selected.items()}
size_comparison={name:{'r3_bytes':old_sizes[name],'current_bytes':elfs[name]['bytes'],'delta_bytes':elfs[name]['bytes']-old_sizes[name]} for name in selected}
inputs=[Path(__file__),ROOT/'VERSION',packed,fixture/'manifest.json',old/'manifest.json']+[ROOT/path for path in reports.values()]
input_hashes={str(path.relative_to(ROOT)):sha(path) for path in inputs}
if options.check:
    result=json.loads((output/'manifest.json').read_text())
    assert result['source_hashes']==input_hashes and result['files']==records(output)
    assert not result['ready_to_flash'] and not result['firmware_created']
else:
    assert not output.exists(),'Preserve r4; use --check.'
    paths=[row['path'] for row in overlay]+list(selected.values())
    for app in ('store','graphics-demo'):
        paths.append('external/HOMEBREW/apps/'+app+'/app.ini')
        optional='external/HOMEBREW/apps/'+app+'/files.sha256'
        if (fixture/optional).is_file():paths.append(optional)
    for relative in paths:assert (fixture/relative).is_file() and not (fixture/relative).is_symlink(),relative
    staging=Path(tempfile.mkdtemp(prefix='current-product-',dir=ROOT/'work'))
    for relative in paths:
        source=fixture/relative;assert source.is_file() and not source.is_symlink()
        destination=staging/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        if destination.read_bytes()[:4]==b'\x7fELF':destination.chmod(0o755)
    (staging/'REVIEW.md').write_text(
        '# Local review only\n\nNot an installation tree or flashable firmware.\n\n'
        'The existing Sony menu overlay is unchanged. Launcher, Network Store and graphics example use stock libraries; apps remain external.\n\n'
        'Actual app workflows and the original manager/proxy execution are bound by ELF hashes. The manager test uses a C Home client, simulated devices and RAM state volumes; it does not validate Sony GUI recovery or physical hardware.\n\n'
        'No test preload library, test init, kernel, mock NVP, Python runtime, ROM or updater is included.\n',encoding='utf-8')
    rows=records(staging)
    assert all(Path(row['path']).suffix.lower() not in ('.py','.pyc','.upg','.exe','.zip','.ko') for row in rows)
    result={'version':version,'profile':'stock-libc-complete-runtime-review','composition_revision':4,
            'files':rows,'source_hashes':input_hashes,'elfs':elfs,'dynamic_dependencies':dependencies,
            'size_comparison_with_r3':size_comparison,'system_overlay_unchanged_from_r3':True,
            'system_file_length_delta_from_stock':system_delta,'ready_to_flash':False,
            'hardware_tested':False,'firmware_created':False,'Sony_GUI_return_validated':False,
            'limits':['Application evidence is byte-bound; original menu patch remains independently unqualified on hardware.',
                      'Original-manager return uses a C Home client, not Sony GUI; devices and state volumes are simulated.',
                      'File lengths are not allocated filesystem blocks, physical capacity or installation safety.']}
    (staging/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');staging.rename(output)
lib=ROOT/'work/arm-signal-tests/lib'
command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(output/selected['launcher'])]
for mode in ('--catalog','--check'):
    run=subprocess.run(command+[mode,str(output/'external/HOMEBREW/apps')],capture_output=True,text=True,timeout=15)
    assert run.returncode==0,(mode,run.stderr)
    if mode=='--check':assert set(run.stdout.splitlines())=={'store VERIFIED','graphics-demo VERIFIED'}
    else:assert run.stdout.splitlines()[0]=='store\tNetwork Store'
print(json.dumps({'output':str(output.relative_to(ROOT)),'elf_sizes':size_comparison,'logical_system_delta':system_delta,'ready_to_flash':False},indent=2))
