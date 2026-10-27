"""Independently verify local resource-feedback candidate bytes and archive changes."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,sys,tarfile,re,collections,platform,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_stx

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('candidate');parser.add_argument('--report');args=parser.parse_args();area=(ROOT/args.candidate).resolve();assert area.is_relative_to(ROOT/'dist') and area.is_dir()
if not __debug__:
 raise RuntimeError('Verification requires Python assertions enabled; do not use -O')
audit={'schema':1,'candidate':str(area.relative_to(ROOT)),'python':platform.python_version(),'verifier_sha256':sha(Path(__file__)),'stages':{},'passed':False}
report_path=(ROOT/args.report).resolve() if args.report else None
if report_path:
 if not report_path.is_relative_to(ROOT/'work') or report_path.exists():
  raise ValueError('Use a new report path inside project work/')
 report_path.parent.mkdir(parents=True,exist_ok=True)
def save_audit():
 if report_path:report_path.write_text(json.dumps(audit,indent=2)+'\n')
def audit_failure(kind,error,tb):
 audit['failure']={'type':kind.__name__,'message':str(error),'traceback':traceback.format_exception(kind,error,tb)}
 save_audit();sys.__excepthook__(kind,error,tb)
sys.excepthook=audit_failure
listed=set()
for line in (area/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1);relative=PurePosixPath(name);assert not relative.is_absolute() and '..' not in relative.parts and name not in listed
 p=area/name;assert p.resolve().is_relative_to(area) and p.is_file() and not p.is_symlink() and sha(p)==digest;listed.add(name)
assert listed=={str(p.relative_to(area)) for p in area.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
j=json.loads((area/'review/verification.json').read_text());assert j['profile']=='compact-resource-feedback-local-review' and not any(j[x] for x in ['ready_to_flash','device_written','hardware_tested','physical_capacity_verified'])
for name,digest in j['inputs'].items():
 p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and p.is_file() and sha(p)==digest
upg=area/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';upg_bytes=upg.read_bytes()
audit['stages']['candidate_snapshot']={'sha256':hashlib.sha256(upg_bytes).hexdigest(),'bytes':len(upg_bytes)}
assert hashlib.sha256(upg_bytes).hexdigest()==j['upg_sha256'] and len(upg_bytes)==j['upg_bytes']
original_bytes=(ROOT/'work/updater-jp/NW_WM_FW.UPG').read_bytes()
audit['stages']['original_snapshot']={'sha256':hashlib.sha256(original_bytes).hexdigest(),'bytes':len(original_bytes)}
_,actual_parts=unpack(upg_bytes,require_stock=False);_,original_parts=unpack(original_bytes);assert actual_parts[:3]==original_parts[:3]
audit['stages']['component_hashes']=[hashlib.sha256(x).hexdigest() for x in actual_parts]
base=ROOT/'dist'/j['version']/'diagnostic-review-3';_,baseparts=unpack((base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes(),require_stock=False)
extra='usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd';changes={x['path']:x for x in j['system_changes']};assert len(changes)==16 and {x['path'] for x in j['system_changes'] if x['new_file']}=={extra}
metadata=('name','type','mode','uid','gid','mtime','linkname','uname','gname','devmajor','devminor','pax_headers')
with tarfile.open(fileobj=io.BytesIO(actual_parts[3]),mode='r:gz') as actual,tarfile.open(fileobj=io.BytesIO(original_parts[3]),mode='r:gz') as original,tarfile.open(fileobj=io.BytesIO(baseparts[3]),mode='r:gz') as prior:
 a=actual.getmembers();b=original.getmembers();counts=collections.Counter(x.name for x in a)
 audit['stages']['archive_counts']={'candidate':len(a),'original':len(b),'candidate_unique':len(counts),'duplicate_names':{k:v for k,v in counts.items() if v>1}}
 save_audit()
 assert len(a)==1433 and len(b)==1432 and len({x.name for x in a})==len(a),(len(a),len(b),len({x.name for x in a}))
 for old,new in zip(b,a[:1432]):
  assert all(getattr(old,k)==getattr(new,k) for k in metadata),old.name
  if not old.isfile():assert old.size==new.size;continue
  data=actual.extractfile(new).read();stock=original.extractfile(old).read();name=old.name.removeprefix('./')
  if name in changes:
   row=changes[name];assert len(stock)==row['before_bytes'] and hashlib.sha256(stock).hexdigest()==row['before_sha256'];assert len(data)==row['after_bytes'] and hashlib.sha256(data).hexdigest()==row['after_sha256']
  else:assert data==stock,name
  if name.startswith('usr/local/share/gemini/res/stx/'):
   before=prior.extractfile(new.name).read();assert parse_stx(data)==parse_stx(before)+['Homebrew unavailable.\nCheck HOMEBREW.']
 new=a[-1];template=original.getmember('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd');assert new.name=='./'+extra and new.isfile()
 assert all(getattr(new,k)==getattr(template,k) for k in metadata if k!='name')
 data=actual.extractfile(new).read();assert len(data)==changes[extra]['after_bytes'] and hashlib.sha256(data).hexdigest()==changes[extra]['after_sha256'];assert b'sid-999-99' in data and re.search(rb'tid\.0:\s*"tid-7309"',data)
 font_sha=hashlib.sha256(actual.extractfile('./usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf').read()).hexdigest()
 elf=actual.extractfile('./usr/local/bin/SpiderApp').read();assert hashlib.sha256(elf).hexdigest()==j['candidate_elf_sha256']=='91b28344c4839e0dc9ce967ce6101634c23dfc6b794c316acc4f4e3c3fe28d16'
assert {str(p.relative_to(area/'external')):sha(p) for p in (area/'external').rglob('*') if p.is_file()}=={str(p.relative_to(base/'external')):sha(p) for p in (base/'external').rglob('*') if p.is_file()}
assert j['actual_font_metrics_verified']
metrics=json.loads((area/'review/real-font-layout-report.json').read_text());assert metrics['passed'] and metrics['actual_font_metrics_verified'] and metrics['metric_functions_not_interposed'] and len(metrics['cases'])==11 and all(c['real_font_line_count']==2 and c['height_with_real_font']==80 for c in metrics['cases'])
assert metrics['font_sha256']==font_sha and all(c['real_font_max_line_width']<=180 for c in metrics['cases'])
assert j['logical_system_growth_bytes']==sum(x['after_bytes']-x['before_bytes'] for x in changes.values())
audit['passed']=True;audit['stages']['all_content_checks_passed']=True;save_audit()
print(json.dumps({'passed':True,'checksums_verified':len(listed),'original_entries_metadata_preserved':1432,'new_entries':1,'rootfs_entries':1433,'system_changes':16,'unchanged_components':[0,1,2],'external_files_match_candidate3':True,'logical_system_growth_bytes':j['logical_system_growth_bytes'],'ready_to_flash':False,'device_access':False},indent=2))
