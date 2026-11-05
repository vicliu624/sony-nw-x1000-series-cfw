"""Read-only catalog/package audit; reports are written only to PC work/."""
import argparse,json,sys,time
from pathlib import Path
from app_registry import ROOT
from verify_app_package import verify
sys.path.insert(0,str(ROOT/'runtime'))
from catalog import scan

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);args=parser.parse_args()
 catalog=scan(args.root);packages=[]
 for app in catalog['apps']:
  row=dict(id=app['id'],installed_version=app['version'])
  version=ROOT/'runtime/apps'/app['id']/'VERSION'
  row['source_version']=version.read_text().strip() if version.exists() else None
  try:row['package']=verify(args.root/app['id']);row['integrity_ok']=True
  except (OSError,ValueError,KeyError,UnicodeError) as error:row.update(integrity_ok=False,error=str(error))
  packages.append(row)
 report=dict(read_only=True,device_written=False,programs_executed=False,catalog_valid=len(catalog['apps']),catalog_rejected=catalog['rejected'],packages=packages)
 out=ROOT/'work/installed-app-audit'/str(time.time_ns());out.mkdir(parents=True)
 (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),catalog_valid=report['catalog_valid'],catalog_rejected=report['catalog_rejected'],package_failures=[row for row in packages if not row['integrity_ok']],version_differences=[dict(id=row['id'],installed=row['installed_version'],source=row['source_version']) for row in packages if row['source_version'] and row['installed_version']!=row['source_version']],device_written=False),indent=2,ensure_ascii=False))
if __name__=='__main__':main()
