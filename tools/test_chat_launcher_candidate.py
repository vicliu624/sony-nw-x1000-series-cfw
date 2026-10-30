"""Validate the actual ARM launcher/chat candidate without launching any app."""
from pathlib import Path
import hashlib,json,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/chat-managed-launcher-dev3-review'
launcher=OUT/'launcher.elf';build=json.loads((OUT/'build.json').read_text())
assert hashlib.sha256(launcher.read_bytes()).hexdigest()==build['sha256']
for name,digest in build['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
source=ROOT/'work/espnow-chat-app/HOMEBREW/apps/espnow-chat'
lines=(source/'files.sha256').read_text().splitlines();assert lines[0]=='HBFILES1'
files={}
for line in lines[1:]:
    digest,size,name=line.split();assert name in ('app','app.ini','radio-worker','launch.contract') and name not in files
    data=(source/name).read_bytes();assert len(data)==int(size) and hashlib.sha256(data).hexdigest()==digest;files[name]=digest
assert set(files)=={'app','app.ini','radio-worker','launch.contract'}
base=['qemu-arm','-cpu','arm926',str(ROOT/'work/arm-signal-tests/lib/ld-linux.so.3'),'--library-path',str(ROOT/'work/arm-signal-tests/lib'),str(launcher)]
with tempfile.TemporaryDirectory(dir=OUT) as temporary:
    apps=Path(temporary);app=apps/'espnow-chat';shutil.copytree(source,app)
    run=subprocess.run(base+['--managed-check',str(apps)],capture_output=True,text=True,timeout=15);assert run.returncode==0 and run.stdout=='espnow-chat MANAGED\n'
    run=subprocess.run(base+['--check',str(apps)],capture_output=True,text=True,timeout=15);assert run.returncode==0 and run.stdout=='espnow-chat VERIFIED\n'
    record=(app/'launch.contract').read_bytes();assert len(record)==80
    changed=bytearray(record);changed[15]=ord('0') if changed[15]!=ord('0') else ord('1');(app/'launch.contract').write_bytes(changed)
    run=subprocess.run(base+['--managed-check',str(apps)],capture_output=True,text=True,timeout=15);assert run.returncode==3
    (app/'launch.contract').unlink();run=subprocess.run(base+['--managed-check',str(apps)],capture_output=True,text=True,timeout=15);assert run.returncode==0 and run.stdout=='espnow-chat LEGACY\n'
report={'passed':True,'actual_arm_launcher':True,'chat_files_sha256':files,'launcher_sha256':build['sha256'],'valid_contract_recognized':True,'wrong_hash_contract_rejected':True,'missing_contract_is_legacy':True,'app_executed':False,'radio_driver_accessed':False,'device_accessed':False,'hardware_qualified':False}
(OUT/'chat-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
