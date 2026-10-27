"""Prepare an uninstalled resource-backed Homebrew message prototype, PC only."""
from pathlib import Path
import hashlib,json,re,tarfile
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.resources import append_stx,parse_stx
out=ROOT/'work/home-feedback-resource-review-2';out.mkdir(exist_ok=False)
review=ROOT/'work/libc-product-review-0.1.0-dev.16-r4';manifest=json.loads((review/'manifest.json').read_text())
rows=[r for r in manifest['files'] if r['path'].startswith('system-overlay/usr/local/share/gemini/res/stx/')]
assert len(rows)==11
text='Homebrew unavailable.\nCheck HOMEBREW.'
changes=[];ids=[]
for r in rows:
 p=review/r['path'];b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256']
 new,tid=append_stx(b,text);assert parse_stx(new)==parse_stx(b)+[text];ids.append(tid)
 name=r['path'].removeprefix('system-overlay/');target=out/'overlay'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(new)
 changes.append({'path':name,'original_candidate_sha256':r['sha256'],'new_sha256':hashlib.sha256(new).hexdigest(),'added_tid':tid,'growth_bytes':len(new)-len(b)})
assert len(set(ids))==1
sid=99999;name='usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd'
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:
 assert './'+name not in archive.getnames()
 stock=archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd').read()
 assert re.search(rb'tid\.0:\s*"tid-0027"',stock)
swd=('; Homebrew launch error prototype\ntype:\t"dialog" ""\nsid:\t"sid-999-99"\n\nitem:\t"Homebrew" ""\nperson:\t""\n\ntid.0:\t"tid-'+str(ids[0])+'"\n').encode()
target=out/'overlay'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(swd)
report={'prepared':True,'scope':'Uninstalled SWD/STX prototype; no ELF change or firmware package','proposed_sid':sid,'added_tid':ids[0],'language_files':11,'existing_strings_preserved':True,'all_languages_use_same_English_error':True,'stock_sid_file_999_99_absent':True,'resource_loader_registration_verified':False,'font_width_verified':False,'requires_new_swd_system_path':True,'system_entries':changes+[{'path':name,'new_sha256':hashlib.sha256(swd).hexdigest(),'bytes':len(swd),'new_file':True}],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidate3_changed':False,'ready_to_flash':False}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('prepared','proposed_sid','added_tid','language_files','resource_loader_registration_verified','ready_to_flash')},indent=2))
