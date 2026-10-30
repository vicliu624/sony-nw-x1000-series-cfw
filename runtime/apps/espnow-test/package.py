"""Create a private local experiment review ZIP; no deployment or publication."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[3];work=ROOT/'work/autonomous-espnow-test'
build=json.loads((work/'build.json').read_text());assert build['built'] and not build['device_written']
for name,digest in build['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
binary=work/'espnow-test.arm';assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['sha256']
files={'PLAYER_FILES/HOMEBREW/apps/espnow-test/espnow-test.arm':binary.read_bytes(),'READ_FIRST.md':(ROOT/'runtime/apps/espnow-test/README.md').read_bytes()}
radio=ROOT/'work/espnow-full-radio-review-3';manifest=json.loads((radio/'manifest.json').read_text())
for name,key in [('sd8686.bin','candidate_sha256'),('helper_sd.bin','helper_sha256')]:
 data=(radio/'candidate'/name).read_bytes();assert hashlib.sha256(data).hexdigest()==manifest[key];files['PLAYER_FILES/HOMEBREW/data/espnow-test/candidate/'+name]=data
for name in ('build.json','tests.json','detach-tests.json','loader-tests.json'):
 p=work/name;document=json.loads(p.read_text());assert document.get('passed',document.get('built'))
 if 'source_sha256' in document:
  for source,digest in document['source_sha256'].items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,source
 files['EVIDENCE/'+name]=p.read_bytes()
for name in ('analyze_espnow_capture_log.py','espnow_known_key_frame.py'):files['PC/'+name]=(ROOT/'tools'/name).read_bytes()
files['PC/README.txt']=b'Python is PC-only. Install pycryptodome locally. Analyze the returned journal with analyze_espnow_capture_log.py --log JOURNAL --lmk-file PRIVATE_LMK_FILE. No key is included.\n'
files['REVIEW.json']=(json.dumps({'version':build['version'],'local_review_only':True,'physical_radio_qualified':False,'APF_USB_sleep_ownership_qualified':False,'graphical_app':False,'original_firmware_updater_used':False,'system_partition_added_bytes':0,'legacy_chat_candidate_directory_untouched':True,'radio_sha256':build['radio_candidate_sha256'],'files':{name:hashlib.sha256(data).hexdigest() for name,data in files.items()}},indent=2)+'\n').encode()
out=ROOT/'dist/espnow-test'/build['version'];out.mkdir(parents=True,exist_ok=True)
target=out/('espnow-test-'+build['version']+'-local-review.zip')
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as archive:
 for name,data in sorted(files.items()):archive.writestr(name,data)
 archive.writestr('PLAYER_FILES/HOMEBREW/data/espnow/',b'')
with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
digest=hashlib.sha256(target.read_bytes()).hexdigest();target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n')
print(json.dumps({'archive':str(target.relative_to(ROOT)),'bytes':target.stat().st_size,'sha256':digest,'device_written':False,'published':False,'physical_qualification_pending':True},indent=2))
