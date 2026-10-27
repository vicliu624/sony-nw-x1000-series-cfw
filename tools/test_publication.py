"""Static publication acceptance/rejection with actual native package inputs."""
from pathlib import Path
import runpy,subprocess,tempfile,json,hashlib,shutil,os
ROOT=Path(__file__).resolve().parents[1]
app=runpy.run_path(str(ROOT/'tools/build_hello_app.py'));publisher=runpy.run_path(str(ROOT/'tools/publish_repository.py'));publish=publisher['publish'];work=ROOT/'work/publication-tests';work.mkdir(exist_ok=True)
original=ROOT/'work/hello-app/package';version=(ROOT/'VERSION').read_text().strip();rows=[]
def tree(root):return {str(p.relative_to(root)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in root.rglob('*')}
for mode in ('valid','existing-output','bad-url','credentials','query','too-long-base','corrupt-program','extra-file','manifest-link','asset-link','hardlink','bad-version','wrong-target','duplicate-id'):
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temporary:
  base=Path(temporary);package=base/'package';shutil.copytree(original,package);output=base/'snapshot';url='https://example.test/apps/';inputs=[package]
  if mode=='existing-output':output.mkdir();(output/'keep').write_bytes(b'KEEP')
  elif mode=='bad-url':url='http://example.test/'
  elif mode=='credentials':url='https://user:password@example.test/'
  elif mode=='query':url='https://example.test/?x/'
  elif mode=='too-long-base':url='https://example.test/'+'a'*500+'/'
  elif mode=='corrupt-program':(package/'app').write_bytes(b'X'*len((package/'app').read_bytes()))
  elif mode=='extra-file':(package/'secret.dat').write_bytes(b'MUST NOT PUBLISH')
  elif mode=='manifest-link':(package/'app.ini').unlink();(base/'outside').write_bytes(b'PRIVATE');(package/'app.ini').symlink_to(base/'outside')
  elif mode=='asset-link':(package/'link.dat').symlink_to(package/'app')
  elif mode=='hardlink':os.link(package/'app',base/'outside')
  elif mode=='bad-version':(package/'app.ini').write_text((package/'app.ini').read_text().replace('version='+version,'version=..'))
  elif mode=='wrong-target':(package/'app.ini').write_text((package/'app.ini').read_text().replace('sony-nw-x1000-jp','other-target'))
  elif mode=='duplicate-id':inputs=[package,package]
  before=tree(package);prior=tree(output) if output.exists() else None
  try:result=publish(inputs,url,output)
  except (ValueError,FileExistsError,subprocess.CalledProcessError):assert mode!='valid',mode
  else:
   assert mode=='valid';catalog=(output/'web/catalog.txt').read_bytes();assert hashlib.sha256(catalog).hexdigest()==result['catalog_sha256'];assert (output/'web/apps/hello'/version/'app').read_bytes()==(package/'app').read_bytes();assert not result['uploaded'] and not result['CA_or_keys_included']
  assert tree(package)==before
  if mode=='existing-output':assert tree(output)==prior
  elif mode!='valid':assert not output.exists(),mode
  rows.append({'case':mode,'passed':True})
assert not list(work.rglob('.publication-stage-*'))
sources=['tools/publish_repository.py','tools/inspect_publication_bundle.c','tools/inspect_publication_catalog.c','runtime/store/bundle_posix.c','runtime/store/inventory.c','runtime/store/package.c','runtime/store/remote_catalog.c','runtime/store/download_plan.c','runtime/store/cleanup_plan.c','runtime/store/https_url.c','runtime/native/sha256.c']
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Host-only publication preparation, no upload or device action.','Metadata and ELF-header/hash validation only; individual native app qualification remains separate.','Inputs/output roots are quiescent; not concurrent or adversarial mutation protection.']}
(ROOT/'sources/native-publication-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Repository publication:',len(rows),'accept/reject/snapshot preservation checks passed.')
