"""Compare a complete proposed root file inventory; never creates an image or UPG."""
import argparse,hashlib,io,json,posixpath,sys,tarfile,time
from pathlib import Path
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack

def inventory(raw):
 result={}
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
  for item in archive.getmembers():
   name=item.name.removeprefix('./').rstrip('/')
   if name in ('','.'):continue
   if name.startswith('/') or posixpath.normpath(name)!=name or name.startswith('../') or name in result:raise ValueError('Ambiguous archive path: '+name)
   row=dict(kind='file' if item.isfile() else 'directory' if item.isdir() else 'symlink' if item.issym() else 'other',bytes=item.size if item.isfile() else 0,mode=item.mode,uid=item.uid,gid=item.gid)
   if item.isfile():row['sha256']=hashlib.sha256(archive.extractfile(item).read()).hexdigest()
   elif item.issym():row['target']=item.linkname
   else:
    if not item.isdir():row.update(tar_type=item.type.hex(),linkname=item.linkname,devmajor=item.devmajor,devminor=item.devminor)
   result[name]=row
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--layout-review',type=Path,required=True)
 parser.add_argument('--localization-firmware',type=Path,required=True)
 args=parser.parse_args()
 layout_path,layout=receipt(args.layout_review)
 source=private(args.localization_firmware)
 if digest(source)!=layout['localization_input_sha256']:raise ValueError('Localization input mismatch')
 if not layout['prepared'] or not layout['analysis_only'] or layout['player_copies_in_final_layout']!=1:raise ValueError('Expected single-player analysis layout')
 original=private('work/upg-jp/verified-3.bin')
 if digest(original)!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':raise ValueError('Original root mismatch')
 _,parts=unpack(source.read_bytes(),require_stock=False)
 stock=inventory(original.read_bytes());candidate=inventory(parts[3])
 for name,row in layout['files'].items():
  path=private(layout_path.parent/'root-overlay'/name)
  if digest(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('Overlay input mismatch: '+name)
  old=candidate.get(name)
  if old and old['kind']!='file':raise ValueError('Overlay replaces non-file')
  # The installation layout retains original ownership for replacements.
  candidate[name]=dict(kind='file',bytes=row['bytes'],sha256=row['sha256'],mode=int(row['mode'],8),
                       uid=old['uid'] if old else row.get('uid',0),gid=old['gid'] if old else row.get('gid',0))
 changes=[]
 for name in sorted(stock.keys()|candidate.keys()):
  a=stock.get(name);b=candidate.get(name)
  if a!=b:changes.append(dict(path=name,original=a,candidate=b,delta_bytes=(b or {}).get('bytes',0)-(a or {}).get('bytes',0)))
 total=lambda rows:sum(row['bytes'] for row in rows.values() if row['kind']=='file')
 rounded=lambda rows,block:sum((row['bytes']+block-1)//block*block for row in rows.values() if row['kind']=='file')
 report=dict(passed=True,analysis_only=True,ready_to_flash=False,device_accessed=False,firmware_created=False,
  original_regular_bytes=total(stock),candidate_regular_bytes=total(candidate),regular_file_delta_bytes=total(candidate)-total(stock),
  regular_file_allocation_models=[dict(block_bytes=block,delta_bytes=rounded(candidate,block)-rounded(stock,block)) for block in (1024,4096)],
  changed_paths=changes,layout_review=layout_path.relative_to(ROOT).as_posix(),layout_review_sha256=digest(layout_path),
  localization_sha256=digest(source),original_root_sha256=digest(original),
  capacity_margin_verified=False,limitations=['Complete proposed file inventory, not an allocated filesystem image.',
   'Block models omit inode/directory/indirect blocks, reserved space and flash translation/bad blocks.',
   'No current physical free-space measurement or partition-write qualification.',
   'No updater, kernel or initrd is generated or changed.'])
 out=ROOT/'work/managed-root-capacity'/str(time.time_ns());out.mkdir(parents=True)
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 (ROOT/'work/managed-root-capacity-latest.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,review=(out/'review.json').relative_to(ROOT).as_posix(),regular_file_delta_bytes=report['regular_file_delta_bytes'],changed_paths=len(changes),capacity_margin_verified=False),indent=2))
if __name__=='__main__':main()
