"""Prepare a local pinned repository config, using explicit user-selected DER CA.
Host-only; never deploy, upload, generate keys or produce firmware.
"""
from pathlib import Path
import argparse,hashlib,json,stat,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]

def bounded(path,limit):
 path=Path(path).absolute()
 if path!=path.resolve():raise ValueError('Input must be canonical, without aliases')
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=limit:raise ValueError('Input must be a bounded single-link regular file')
 return path.read_bytes()

def prepare(catalog_url,catalog_file,ca_file,output):
 output=Path(output).absolute()
 if output!=output.resolve() or not output.is_relative_to((ROOT/'work').resolve()) or output==(ROOT/'work').resolve():raise ValueError('Output must be a new canonical directory below project work/')
 if output.exists():raise FileExistsError('Output already exists; select a new review directory')
 catalog=bounded(catalog_file,32768);ca=bounded(ca_file,8192)
 if not isinstance(catalog_url,str) or not catalog_url.isascii() or any(ord(c)<32 or ord(c)>126 for c in catalog_url):raise ValueError('Catalog URL must be printable ASCII HTTPS')
 digest=lambda data:hashlib.sha256(data).hexdigest()
 config=('HBREPO1\ncatalog_url='+catalog_url+'\ncatalog_bytes='+str(len(catalog))+'\ncatalog_sha256='+digest(catalog)+'\nca_sha256='+digest(ca)+'\n').encode('ascii')
 tools=ROOT/'work/repository-config-tools';tools.mkdir(exist_ok=True)
 crypto=ROOT/'work/external-tls-probe/bearssl-0.6'
 if not (crypto/'inc/bearssl.h').is_file():raise ValueError('Prepare pinned BearSSL with tools/probe_external_tls.py first')
 library=tools/'bearssl-host/libbearssl.a'
 subprocess.run(['make','-C',str(crypto),'-j4','lib','CC=gcc','AR=ar','CFLAGS=-O2','BUILD='+str(library.parent)],check=True,stdout=subprocess.DEVNULL)
 sources=['runtime/store/repository.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/inspect_repository_config.c']
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(crypto/'inc'),*sources,str(library),'-o',str(tools/'inspect')],cwd=ROOT,check=True)
 catalog_sources=['runtime/store/remote_catalog.c','runtime/store/download_plan.c','runtime/store/inventory.c','runtime/store/package.c','runtime/store/cleanup_plan.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/inspect_publication_catalog.c']
 subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*catalog_sources,'-o',str(tools/'catalog')],cwd=ROOT,check=True)
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.repository-config-',dir=output.parent) as temporary:
  stage=Path(temporary);repo=stage/'HOMEBREW/repository';repo.mkdir(parents=True)
  (repo/'repository.conf').write_bytes(config);(repo/'ca.der').write_bytes(ca)
  # Validate the copied bytes using the same C parsers/CA decoder as the app.
  (stage/'catalog.input').write_bytes(catalog)
  subprocess.run([str(tools/'catalog'),str(stage/'catalog.input')],check=True)
  subprocess.run([str(tools/'inspect'),str(repo)],check=True)
  (stage/'catalog.input').unlink()
  report={'catalog_url':catalog_url,'catalog_bytes':len(catalog),'catalog_sha256':digest(catalog),'ca_sha256':digest(ca),'config_sha256':digest(config),'physical_device_access':False,'uploaded':False,'firmware_package_created':False,'trust_policy':'Explicit caller-selected CA and catalog snapshot; hashing does not establish publisher identity.','limits':['Local review output only; no server connectivity, hostname or chain test.','Changing catalog content requires a new reviewed configuration snapshot.','No default/test CA or private key is supplied by this tool.']}
  (stage/'configuration.json').write_text(json.dumps(report,indent=2)+'\n')
  stage.rename(output)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--catalog-url',required=True);parser.add_argument('--catalog-file',type=Path,required=True);parser.add_argument('--ca-der',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 print(json.dumps(prepare(args.catalog_url,args.catalog_file,args.ca_der,args.output),indent=2))
