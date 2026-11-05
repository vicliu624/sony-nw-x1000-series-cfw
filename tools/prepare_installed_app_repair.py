"""Freeze a metadata-only repair for an existing package; no device writes."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
from app_registry import ROOT
from app_presentation import install_presentation
from verify_app_package import verify
sys.path.insert(0,str(ROOT/'runtime'))
from catalog import read_app

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);args=parser.parse_args()
 app=read_app(args.folder)
 if app['id']!='espnow-chat' or app['version']!='0.1.0-dev.2':raise ValueError('This repair targets the retained Chat dev.2 package only')
 if {p.name for p in args.folder.iterdir()}!={'app','app.ini','radio-worker','files.sha256'}:raise ValueError('Unexpected installed package layout')
 lines=(args.folder/'files.sha256').read_text().splitlines()
 if not lines or lines[0]!='HBFILES1':raise ValueError('Old inventory missing')
 for line in lines[1:]:
  sha,size,name=line.split(' ')
  if name not in ('app','app.ini','radio-worker'):raise ValueError('Unexpected legacy file')
  path=args.folder/name
  if path.stat().st_size!=int(size) or digest(path)!=sha:raise ValueError('Legacy package integrity mismatch')
 out=ROOT/'work/app-metadata-repair'/str(time.time_ns());out.mkdir(parents=True)
 shutil.copytree(args.folder,out/'original');folder=out/'package';shutil.copytree(out/'original',folder)
 install_presentation(app['id'],folder,app['version'])
 info=json.loads((folder/'app-info.json').read_text());info['changes']='Completes launcher artwork and package metadata for the retained dev.2 program. Executables are unchanged.'
 (folder/'app-info.json').write_text(json.dumps(info,indent=2)+'\n')
 files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(folder.iterdir()) if p.name!='files.sha256'}
 (folder/'files.sha256').write_text('HBFILES1\n'+''.join(row['sha256']+' '+str(row['bytes'])+' '+name+'\n' for name,row in files.items()))
 verify(folder)
 for name in ('app','radio-worker','app.ini'):
  if digest(folder/name)!=digest(out/'original'/name):raise ValueError('Repair changed executable or version')
 report=dict(prepared=True,installed=False,id=app['id'],version=app['version'],metadata_only=True,executables_unchanged=True,
  old_inventory_sha256=digest(out/'original/files.sha256'),files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in folder.iterdir()},
  limits=['Repair of the retained physical dev.2 package, not a build or qualification of development dev.3.','No RF, account or user-data changes.'])
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,directory=out.relative_to(ROOT).as_posix(),version=app['version'],metadata_only=True,device_written=False),indent=2))
if __name__=='__main__':main()
