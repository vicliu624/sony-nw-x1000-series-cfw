"""PC-only readback audit of the explicitly authorized terminal app deployment."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
stage=Path(sys.argv[1]).resolve()
def read_json(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(b):return hashlib.sha256(b).hexdigest()
plan=read_json(stage/'plan.json')
install=read_json(stage/'install-report.json')
build=read_json(ROOT/'work/terminal-review/build.json')
tests=read_json(ROOT/'work/terminal-review/tests.json')
assert install['success'] and not install['firmware_written'] and not install['device_program_executed']
assert build['software_checks_passed'] and tests['passed'] and build['ui_render_and_touch_return_passed']
assert read_json(stage/'other-apps-before.json')==read_json(stage/'other-apps-after.json')
assert install['launcher_before']==install['launcher_after']
assert install['fm_data_before']==install['fm_data_after']
for name,sha in build['sources'].items():assert digest((ROOT/name).read_bytes())==sha,name
drive=Path(plan['target_drive']+'/')
expected={'app','app.ini','files.sha256','server-cert.der','server-key.der'}
installed=drive/'HOMEBREW/apps/terminal'
assert {p.name for p in installed.iterdir()}==expected
checked=[]
package_manifest=dict(l.split('=',1) for l in (installed/'app.ini').read_text(encoding='ascii').splitlines())
archive=ROOT/('work/terminal-review/WiFi-Terminal-'+package_manifest['version']+'-personal-experimental.zip')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for entry in plan['files']:
        data=(drive/entry['relative']).read_bytes()
        assert len(data)==entry['bytes'] and digest(data)==entry['sha256'],entry['relative']
        assert data==Path(entry['source']).read_bytes()==z.read(entry['relative'])
        checked.append({'file':entry['relative'],'bytes':len(data),'sha256':digest(data)})
    for name in ('terminal_client.py','server-cert.sha256'):
        assert (ROOT/'work/terminal-review/computer'/name).read_bytes()==z.read('computer/'+name)
index=(installed/'files.sha256').read_text(encoding='ascii').splitlines()
assert index[0]=='HBFILES1' and len(index)==5
for line in index[1:]:
    sha,size,name=line.split(' ')
    assert name in expected and name!='files.sha256'
    data=(installed/name).read_bytes();assert len(data)==int(size) and digest(data)==sha
manifest=dict(l.split('=',1) for l in (installed/'app.ini').read_text(encoding='ascii').splitlines())
assert manifest['id']=='terminal' and manifest['exec']=='app'
assert manifest['sha256']==digest((installed/'app').read_bytes())
pin=(ROOT/'work/terminal-review/computer/server-cert.sha256').read_text().strip()
assert pin==digest((installed/'server-cert.der').read_bytes())==build['certificate_pin']
audit={'deployment_complete':True,'software_checks_passed':True,'device_runtime_tested':False,'system_partition_added_bytes':0,'installed_bytes':sum(p['bytes'] for p in checked),'checked_files':checked,'zip_sha256':digest(archive.read_bytes()),'other_app_files_verified_unchanged':len(read_json(stage/'other-apps-before.json')),'launcher_unchanged':True,'fm_data_unchanged':True,'pc_certificate_pin_matches_device':True,'install_report':str(stage/'install-report.json'),'pc_client_directory':str(ROOT/'work/terminal-review/computer')}
(stage/'readback-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k!='checked_files'},indent=2))
