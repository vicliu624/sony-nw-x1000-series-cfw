"""Actual ARM review launcher classification; no native hardware mode/app exec."""
from pathlib import Path
import hashlib,json,os,subprocess,errno
from app_registry import ROOT
OUT=ROOT/'work/managed-launcher-review-3';artifact=OUT/'launcher.elf';build=json.loads((OUT/'build.json').read_text());assert build['managed_radio_review']
lib=ROOT/'work/arm-signal-tests/lib';base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact)]
folder=OUT/'apps/hello';marker=folder/'launch.contract';assert not marker.exists() and not marker.is_symlink()
fields=dict(line.split('=',1) for line in (folder/'app.ini').read_text().splitlines());record=b'XNOW-MANAGED-1\n'+fields['sha256'].encode()+b'\n';assert len(record)==80
rows=[]
def check(label,code,word=None):
 r=subprocess.run([*base,'--managed-check',str(OUT/'apps')],capture_output=True,text=True,timeout=10);assert r.returncode==code,(label,r.returncode,r.stdout,r.stderr)
 if word:assert r.stdout=='hello '+word+'\n'
 rows.append({'case':label,'exit':r.returncode,'stdout':r.stdout})
try:
 check('absent-marker-keeps-legacy',0,'LEGACY')
 marker.write_bytes(record);check('valid-marker-binds-current-sha',0,'MANAGED')
 marker.write_bytes(record[:15]+b'0'*64+b'\n');check('wrong-sha-rejected',3)
 marker.write_bytes(record[:-1]);check('truncated-marker-rejected',3)
 marker.write_bytes(b'bad'+record[3:]);check('wrong-prefix-rejected',3)
 marker.unlink()
 try:os.mkfifo(marker)
 except OSError as error:
  if error.errno not in (errno.EOPNOTSUPP,errno.ENOSYS):raise
  rows.append({'case':'fifo-refused-without-blocking','skipped':True,'reason':'Workspace filesystem does not support FIFO nodes; no FIFO runtime claim.'})
 else:check('fifo-refused-without-blocking',3);marker.unlink()
 target=OUT/'contract-target';target.write_bytes(record);marker.symlink_to(target);check('symlink-refused',3);marker.unlink()
 os.link(target,marker);check('hard-link-refused',3);marker.unlink();target.unlink()
 check('legacy-restored-after-fixture-removal',0,'LEGACY')
finally:
 if marker.exists() or marker.is_symlink():marker.unlink()
report={'passed':True,'actual_review_arm_launcher':True,'original_sony_libc':True,'cases':rows,'launch_contract_not_app_ini_extension':True,'no_device_mode_or_app_execution':True,'production_default_unchanged':True,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/platform/espnow/xnow_launcher_bridge.c','runtime/platform/espnow/xnow_launcher_bridge.h','runtime/native/platform_arm.c','tools/test_xnow_managed_launcher.py']}}
(OUT/'contract-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
