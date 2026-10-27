"""Create a local static repository from verified native app directories.
No upload, device writes, CA/key generation or firmware packaging.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,tempfile,stat
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def semver(value):
 number=r'(?:0|[1-9][0-9]*)';identifier=r'(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
 return re.fullmatch(number+r'\.'+number+r'\.'+number+r'(?:-'+identifier+r'(?:\.'+identifier+r')*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?',value) is not None

def publish(packages,base_url,output):
 output=Path(output).absolute();resolved=output.resolve()
 if output!=resolved or not resolved.is_relative_to((ROOT/'work').resolve()) or resolved==(ROOT/'work').resolve():raise ValueError('output must be a new canonical directory under project work/')
 if output.exists():raise FileExistsError('output exists; preserve it and select a new snapshot directory')
 parts=urlsplit(base_url)
 if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or not base_url.endswith('/') or not base_url.isascii():raise ValueError('base URL must be absolute HTTPS ending /, without credentials/query/fragment')
 if not 1<=len(packages)<=32:raise ValueError('repository requires 1..32 packages')
 tools=ROOT/'work/publication-tools';tools.mkdir(exist_ok=True)
 bundle_sources=['runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/native/sha256.c','tools/inspect_publication_bundle.c']
 catalog_sources=['runtime/store/remote_catalog.c','runtime/store/download_plan.c','runtime/store/inventory.c','runtime/store/package.c','runtime/store/cleanup_plan.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/inspect_publication_catalog.c']
 for name,sources in [('bundle',bundle_sources),('catalog',catalog_sources)]:subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-o',str(tools/name)],cwd=ROOT,check=True)
 selected=[];ids=set()
 for raw in packages:
  package=Path(raw).absolute()
  if package!=package.resolve() or not package.is_dir():raise ValueError('package must be a canonical directory without a root alias')
  manifest_path=package/'app.ini';attributes=manifest_path.lstat()
  if not stat.S_ISREG(attributes.st_mode) or attributes.st_nlink!=1 or not 0<attributes.st_size<=1024:raise ValueError('manifest must be a bounded single-link regular file')
  content=manifest_path.read_bytes();fields={}
  for line in content.decode('utf-8').splitlines():
   key,sep,value=line.partition('=')
   if not sep or key in fields:raise ValueError('invalid or duplicate manifest field')
   fields[key]=value
  app_id=fields.get('id','');version=fields.get('version','')
  if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}',app_id) or not semver(version):raise ValueError('publication requires a valid app ID and SemVer version')
  if app_id in ids:raise ValueError('duplicate app ID in snapshot')
  ids.add(app_id);subprocess.run([str(tools/'bundle'),str(package),app_id],check=True)
  selected.append((app_id,version,package))
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.publication-stage-',dir=output.parent) as temporary:
  stage=Path(temporary);web=stage/'web';web.mkdir();rows=[];report_packages=[]
  for app_id,version,package in sorted(selected):
   destination=web/'apps'/app_id/version;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(package,destination,symlinks=True)
   subprocess.run([str(tools/'bundle'),str(destination),app_id],check=True)
   manifest=(destination/'app.ini').read_bytes();index=(destination/'files.sha256').read_bytes();base=base_url+'apps/'+app_id+'/'+version+'/'
   if len(base)>512:raise ValueError('app base URL exceeds device profile')
   rows.append('\t'.join([app_id,version,base,str(len(manifest)),sha(manifest),str(len(index)),sha(index)]))
   report_packages.append({'id':app_id,'version':version,'path':str(destination.relative_to(web)),'program_sha256':sha((destination/'app').read_bytes())})
  catalog=('HBSTORE1\n'+'\n'.join(rows)+'\n').encode('ascii');(web/'catalog.txt').write_bytes(catalog)
  subprocess.run([str(tools/'catalog'),str(web/'catalog.txt')],check=True)
  report={'catalog_url':base_url+'catalog.txt','catalog_bytes':len(catalog),'catalog_sha256':sha(catalog),'packages':report_packages,'physical_device_access':False,'uploaded':False,'hardware_qualified':False,'CA_or_keys_included':False,'firmware_package_created':False,'limits':['Static snapshot; runtime config/CA must be chosen separately.','Native ELF/metadata integrity validation is not ISA, dependency or hardware qualification.','Inputs must remain quiescent; not concurrent-mutation protection.']}
  (stage/'publication.json').write_text(json.dumps(report,indent=2)+'\n')
  if output.exists():raise FileExistsError('output appeared; no replacement performed')
  stage.rename(output)
 return report

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base-url',required=True);parser.add_argument('--output',required=True);parser.add_argument('packages',nargs='+');args=parser.parse_args()
 report=publish(args.packages,args.base_url,args.output);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
