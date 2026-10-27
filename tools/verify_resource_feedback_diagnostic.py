"""Independently verify local resource-feedback candidate bytes and archive changes."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,sys,tarfile,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_stx

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('candidate');args=parser.parse_args();area=(ROOT/args.candidate).resolve();assert area.is_relative_to(ROOT/'dist') and area.is_dir()
listed=set()
for line in (area/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1);relative=PurePosixPath(name);assert not relative.is_absolute() and '..' not in relative.parts and name not in listed
 p=area/name;assert p.resolve().is_relative_to(area) and p.is_file() and not p.is_symlink() and sha(p)==digest;listed.add(name)
assert listed=={str(p.relative_to(area)) for p in area.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
j=json.loads((area/'review/verification.json').read_text());assert j['profile']=='resource-feedback-local-review' and not any(j[x] for x in ['ready_to_flash','device_written','hardware_tested','actual_font_metrics_verified','physical_capacity_verified'])
for name,digest in j['inputs'].items():
 p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and p.is_file() and sha(p)==digest
upg=area/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert sha(upg)==j['upg_sha256'] and upg.stat().st_size==j['upg_bytes']
_,actual_parts=unpack(upg.read_bytes(),require_stock=False);_,original_parts=unpack((ROOT/'work/updater-jp/NW_WM_FW.UPG').read_bytes());assert actual_parts[:3]==original_parts[:3]
base=ROOT/'dist'/j['version']/'diagnostic-review-3';_,baseparts=unpack((base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes(),require_stock=False)
extra='usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd';changes={x['path']:x for x in j['system_changes']};assert len(changes)==16 and {x['path'] for x in j['system_changes'] if x['new_file']}=={extra}
metadata=('name','type','mode','uid','gid','mtime','linkname','uname','gname','devmajor','devminor','pax_headers')
with tarfile.open(fileobj=io.BytesIO(actual_parts[3]),mode='r:gz') as actual,tarfile.open(fileobj=io.BytesIO(original_parts[3]),mode='r:gz') as original,tarfile.open(fileobj=io.BytesIO(baseparts[3]),mode='r:gz') as prior:
 a=actual.getmembers();b=original.getmembers();assert len(a)==1433 and len(b)==1432 and len({x.name for x in a})==len(a)
 for old,new in zip(b,a[:1432]):
  assert all(getattr(old,k)==getattr(new,k) for k in metadata),old.name
  if not old.isfile():assert old.size==new.size;continue
  data=actual.extractfile(new).read();stock=original.extractfile(old).read();name=old.name.removeprefix('./')
  if name in changes:
   row=changes[name];assert len(stock)==row['before_bytes'] and hashlib.sha256(stock).hexdigest()==row['before_sha256'];assert len(data)==row['after_bytes'] and hashlib.sha256(data).hexdigest()==row['after_sha256']
  else:assert data==stock,name
  if name.startswith('usr/local/share/gemini/res/stx/'):
   before=prior.extractfile(new.name).read();assert parse_stx(data)==parse_stx(before)+['Homebrew unavailable.\nCheck HOMEBREW folder.']
 new=a[-1];template=original.getmember('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd');assert new.name=='./'+extra and new.isfile()
 assert all(getattr(new,k)==getattr(template,k) for k in metadata if k!='name')
 data=actual.extractfile(new).read();assert len(data)==changes[extra]['after_bytes'] and hashlib.sha256(data).hexdigest()==changes[extra]['after_sha256'];assert b'sid-999-99' in data and re.search(rb'tid\.0:\s*"tid-7309"',data)
 elf=actual.extractfile('./usr/local/bin/SpiderApp').read();assert hashlib.sha256(elf).hexdigest()==j['candidate_elf_sha256']=='91b28344c4839e0dc9ce967ce6101634c23dfc6b794c316acc4f4e3c3fe28d16'
assert {str(p.relative_to(area/'external')):sha(p) for p in (area/'external').rglob('*') if p.is_file()}=={str(p.relative_to(base/'external')):sha(p) for p in (base/'external').rglob('*') if p.is_file()}
assert j['logical_system_growth_bytes']==sum(x['after_bytes']-x['before_bytes'] for x in changes.values())
print(json.dumps({'passed':True,'checksums_verified':len(listed),'original_entries_metadata_preserved':1432,'new_entries':1,'rootfs_entries':1433,'system_changes':16,'unchanged_components':[0,1,2],'external_files_match_candidate3':True,'logical_system_growth_bytes':j['logical_system_growth_bytes'],'ready_to_flash':False,'device_access':False},indent=2))
