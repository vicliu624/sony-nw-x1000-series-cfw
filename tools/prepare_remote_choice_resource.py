"""Create a local Remote On/Off SWD using existing translated wording IDs."""
import argparse,hashlib,json,re,tarfile,time,sys
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
sys.path.insert(0,str(ROOT/'scripts'))
from resources import parse_stx
from remote_choice_resource import SOURCE as source,TARGET as target,compose
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host-review',required=True);args=parser.parse_args()
hp,host=receipt(args.host_review)
composition=json.loads((ROOT/host['source_composition_report']).read_text())
rp,resources=receipt(composition['settings_resource_review'])
stock=ROOT/'work/upg-jp/verified-3.bin'
assert digest(stock)=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(stock,'r:gz') as archive:
 assert './'+target not in archive.getnames()
 member=archive.getmember('./'+source);raw=archive.extractfile(member).read()
raw=compose(raw)
languages={}
for name,identity in resources['resource_overlay'].items():
 if '/stx/' not in name:continue
 path=rp.parent/'root-overlay'/name;assert digest(path)==identity['sha256']
 texts=parse_stx(path.read_bytes());assert all(texts[i] for i in (7310,255,256))
 languages[name.rsplit('-',1)[1][:-4]]=dict(path=path.relative_to(ROOT).as_posix(),sha256=digest(path),title=texts[7310],on=texts[255],off=texts[256])
assert len(languages)==11
out=ROOT/'work/remote-choice-resource'/str(time.time_ns());dest=out/'root-overlay'/target;dest.parent.mkdir(parents=True);dest.write_bytes(raw)
report=dict(prepared=True,resource_id=13901,artifact=dest.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
 original_template=source,mode=member.mode,uid=member.uid,gid=member.gid,
 languages=languages,existing_wording_ids=True,wording_files_modified=False,device_accessed=False,firmware_created=False,
 source_hashes={p:digest(ROOT/p) for p in ('tools/prepare_remote_choice_resource.py','tools/remote_choice_resource.py')},
 limits=['Unused original filename and existing wording are checked; production loader/ownership still need verification.',
         'No firmware overlay is installed or added to the production builder.'])
(out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),bytes=len(raw),languages=len(languages),device_accessed=False),indent=2))
