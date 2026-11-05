"""Freeze verified SDK rebuilds and old app packages for a bounded PC-side update."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
from app_registry import ROOT
from market_metadata import compare_versions
from verify_app_package import verify
sys.path.insert(0,str(ROOT/'runtime'))
from catalog import read_app

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def private(value):
 path=Path(value)
 if not path.is_absolute():path=ROOT/path
 path=path.resolve()
 if not path.is_relative_to(ROOT/'work'):raise ValueError('Expected private build input')
 return path
def entries(folder,prefix):
 return [dict(relative=prefix+p.relative_to(folder).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inventory',required=True);parser.add_argument('--reviews',nargs='+',required=True);parser.add_argument('--launcher-review',required=True);parser.add_argument('--apps-root',type=Path,required=True);args=parser.parse_args()
 inventory=json.loads(private(args.inventory).read_text());sdk=(ROOT/'sdk/VERSION').read_text().strip();rebuilt={}
 for value in args.reviews:
  report=json.loads(private(value).read_text())
  for row in report['apps']:
   if row.get('verified') and row.get('sdk')==sdk:rebuilt[row['id']]=row
 consumers={row['id'] for row in inventory if row['contract']}
 if consumers-set(rebuilt):raise ValueError('SDK consumers not rebuilt: '+str(sorted(consumers-set(rebuilt))))
 lp=private(args.launcher_review);launcher=json.loads(lp.read_text());launcher_file=private(launcher['artifact'])
 if not launcher['passed'] or not launcher['managed_radio_review'] or sha(launcher_file)!=launcher['sha256']:raise ValueError('Launcher build identity mismatch')
 contracts=json.loads((lp.parent/'contract-tests.json').read_text())
 if not contracts['passed'] or contracts['artifact_sha256']!=launcher['sha256']:raise ValueError('Launcher contract test mismatch')
 out=private(args.inventory).parent/('install-'+str(time.time_ns()));out.mkdir()
 changed=[];unchanged=[];new_files=[];old_files=[]
 for item in inventory:
  if not item['contract']:continue
  row=rebuilt[item['id']];package=private(row['package']);info=verify(package);installed=read_app(args.apps_root/item['id'])
  if installed['sha256']!=item['installed_sha256']:raise ValueError('Installed executable changed since inventory')
  if sha(package/'app')!=row['sha256']:raise ValueError('Rebuild artifact changed')
  if row['sha256']==installed['sha256']:
   unchanged.append(dict(id=item['id'],version=installed['version'],sdk=sdk,binary_sha256=row['sha256']));continue
  if compare_versions(info['version'],installed['version'])<=0:raise ValueError('Changed app requires higher version: '+item['id'])
  verify(args.apps_root/item['id'])
  dest=out/'new/apps'/item['id'];old=out/'previous/apps'/item['id']
  shutil.copytree(package,dest);shutil.copytree(args.apps_root/item['id'],old)
  verify(dest);verify(old)
  changed.append(dict(id=item['id'],before=installed['version'],after=info['version'],sdk=sdk))
  new_files+=entries(dest,'apps/'+item['id']+'/');old_files+=entries(old,'apps/'+item['id']+'/')
 old_launcher=args.apps_root.parent/'launcher/app'
 for side,source in [('new',launcher_file),('previous',old_launcher)]:
  dest=out/side/'launcher/app';dest.parent.mkdir(parents=True);shutil.copy2(source,dest)
 new_files+=entries(out/'new/launcher','launcher/');old_files+=entries(out/'previous/launcher','launcher/')
 plan=dict(schema='x1000-sdk-app-refresh-v1',sdk=sdk,apps=changed,unchanged=unchanged,not_sdk_consumers=[r['id'] for r in inventory if not r['contract']],
  launcher_version=launcher['version'],new_files=new_files,old_files=old_files,total_new_bytes=sum(r['bytes'] for r in new_files),device_written=False,
  limits=['Only launcher and app package directories are updated. No firmware, account, ROM or save paths.',
   'Current-SDK binary identity is software evidence, not physical execution acceptance.'])
 (out/'plan.private.json').write_text(json.dumps(plan,indent=2)+'\n')
 print(json.dumps(dict(directory=out.relative_to(ROOT).as_posix(),sdk=sdk,apps=changed,byte_identical=len(unchanged),not_sdk_consumers=plan['not_sdk_consumers'],total_new_bytes=plan['total_new_bytes'],device_written=False),indent=2))
if __name__=='__main__':main()
