"""Repository config publication bridge: positive and rejected explicit inputs."""
from pathlib import Path
import runpy,tempfile,ssl,json,hashlib,subprocess,os
from prepare_repository_config import prepare
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'tools/build_hello_app.py'));publisher=runpy.run_path(str(ROOT/'tools/publish_repository.py'))
work=ROOT/'work/repository-config-tests';work.mkdir(exist_ok=True);crypto=ROOT/'work/external-tls-probe/bearssl-0.6';rows=[]
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temporary:
 base=Path(temporary);publication=base/'published';published=publisher['publish']([ROOT/'work/hello-app/package'],'https://example.test/homebrew/',publication);catalog=publication/'web/catalog.txt'
 for name in ('rsa','ec','leaf'):
  pem='cert-ee-rsa.pem' if name=='leaf' else 'cert-root-'+name+'.pem';(base/(name+'.der')).write_bytes(ssl.PEM_cert_to_DER_cert((crypto/'samples'/pem).read_text()))
 (base/'garbage.der').write_bytes(b'bad');(base/'bad-catalog').write_bytes(b'BAD\n');(base/'big-catalog').write_bytes(b'X'*32769)
 (base/'linked.der').symlink_to(base/'rsa.der');os.link(base/'ec.der',base/'hardlinked.der')
 cases=[('rsa',published['catalog_url'],catalog,base/'rsa.der',True),('leaf',published['catalog_url'],catalog,base/'leaf.der',False),('garbage',published['catalog_url'],catalog,base/'garbage.der',False),('http','http://example.test/catalog.txt',catalog,base/'rsa.der',False),('credentials','https://user:pass@example.test/catalog.txt',catalog,base/'rsa.der',False),('bad-catalog',published['catalog_url'],base/'bad-catalog',base/'rsa.der',False),('large-catalog',published['catalog_url'],base/'big-catalog',base/'rsa.der',False),('CA-symlink',published['catalog_url'],catalog,base/'linked.der',False),('CA-hardlink',published['catalog_url'],catalog,base/'hardlinked.der',False)]
 for name,url,cat,ca,accepted in cases:
  output=base/('output-'+name)
  try:report=prepare(url,cat,ca,output);actual=True
  except (ValueError,OSError,subprocess.CalledProcessError):actual=False
  assert actual==accepted,name
  assert output.exists()==accepted,name
  if accepted:
   repo=output/'HOMEBREW/repository';assert (repo/'ca.der').read_bytes()==ca.read_bytes();assert report['catalog_sha256']==hashlib.sha256(cat.read_bytes()).hexdigest();assert {p.name for p in repo.iterdir()}=={'ca.der','repository.conf'}
  rows.append({'case':name,'accepted':actual})
 try:prepare(published['catalog_url'],catalog,base/'rsa.der',base/'output-rsa')
 except FileExistsError:rows.append({'case':'existing output preserved','accepted':False})
 else:raise AssertionError('Existing output overwritten')
 assert not list(base.glob('.repository-config-*'))
report={'all_bounded_checks_passed':True,'physical_device_access':False,'generator_source':'tools/test_repository_config.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/prepare_repository_config.py','tools/inspect_repository_config.c','runtime/store/repository.c','runtime/store/https_url.c','runtime/store/remote_catalog.c','runtime/store/download_plan.c','runtime/store/inventory.c','runtime/store/package.c','runtime/store/cleanup_plan.c','runtime/native/sha256.c','tools/inspect_publication_catalog.c','tools/publish_repository.py']},'limits':['Host-side static publication/config/CA validation only, explicit public fixture CA.','No upload, actual server trust/hostname check, device writes or hardware qualification.']}
(ROOT/'sources/repository-config-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Repository config bridge: valid snapshot accepted; nine invalid/overwrite cases rejected.')
