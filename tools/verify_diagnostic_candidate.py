"""Read a prepared local review candidate; never execute its UPG or updater."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,sys,tarfile
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('candidate');options=parser.parse_args()
candidate=(ROOT/options.candidate).resolve();assert candidate.is_relative_to(ROOT/'dist') and candidate.is_dir()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
listed=set()
for line in (candidate/'SHA256SUMS').read_text().splitlines():
 digest,relative=line.split('  ',1);path=PurePosixPath(relative)
 assert not path.is_absolute() and '..' not in path.parts and relative not in listed
 file=candidate/relative;assert file.resolve().is_relative_to(candidate) and file.is_file() and not file.is_symlink()
 assert sha(file)==digest,relative;listed.add(relative)
assert listed=={str(p.relative_to(candidate)) for p in candidate.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
report=verify_report(ROOT,str((candidate/'review/verification.json').relative_to(ROOT)))
assert report['firmware_created'] and not report['ready_to_flash'] and not report['device_written'] and not report['hardware_tested']
path=candidate/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert path.stat().st_size==report['upg_bytes'] and sha(path)==report['upg_sha256']
_,parts=unpack(path.read_bytes(),require_stock=False)
for i in range(3):assert parts[i]==(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes()
changes={row['path']:row for row in report['system_changes']};assert len(changes)==15
keys=('name','type','mode','uid','gid','mtime','linkname','uname','gname','devmajor','devminor','pax_headers')
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as actual,tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as original:
 before=original.getmembers();after=actual.getmembers();assert len(before)==len(after)==1432
 for a,b in zip(before,after):
  assert all(getattr(a,key)==getattr(b,key) for key in keys),a.name
  if not a.isfile():continue
  data=actual.extractfile(b).read();name=a.name.removeprefix('./')
  if name in changes:assert len(data)==changes[name]['after_bytes'] and hashlib.sha256(data).hexdigest()==changes[name]['after_sha256']
  else:assert data==original.extractfile(a).read(),name
diag=candidate/'external/HOMEBREW/apps/diagnostics/app';assert sha(diag)==report['diagnostics_sha256']
assert report['local_dense_ext2_model']['available_nonreserved_bytes']==29024256 and not report['local_dense_ext2_model']['physical_capacity_verified']
print(json.dumps({'checksums_verified':len(listed),'rootfs_entries':1432,'system_replacements':15,'unchanged_components':[0,1,2],'ready_to_flash':False,'device_access':False},indent=2))
