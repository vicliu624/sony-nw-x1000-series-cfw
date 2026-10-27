"""PC-only temporary HTTPS repository for unchanged-store integration tests."""
from pathlib import Path
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import hashlib,json,runpy,ssl,subprocess,tempfile,threading,urllib.request
ROOT=Path(__file__).resolve().parents[1]
def openssl(*arguments):
 subprocess.run(['openssl',*map(str,arguments)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
@contextmanager
def repository_fixture(package,hold_path=None):
 work=ROOT/'work/production-store-https';work.mkdir(exist_ok=True)
 publisher=runpy.run_path(str(ROOT/'tools/publish_repository.py'))
 configuration=runpy.run_path(str(ROOT/'tools/prepare_repository_config.py'))
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temporary:
  area=Path(temporary);root=area/'root.pem';rootkey=area/'root.key';leaf=area/'server.pem';leafkey=area/'server.key';csr=area/'server.csr'
  openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout',rootkey,'-out',root,'-days','2','-sha256','-subj','/CN=Offline Store Test Root','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
  openssl('req','-new','-newkey','rsa:2048','-nodes','-keyout',leafkey,'-out',csr,'-subj','/CN=localhost')
  extension=area/'extensions.cnf';extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
  openssl('x509','-req','-in',csr,'-CA',root,'-CAkey',rootkey,'-CAcreateserial','-out',leaf,'-days','1','-sha256','-extfile',extension)
  openssl('verify','-CAfile',root,'-verify_hostname','localhost',leaf)
  rootder=area/'root.der';openssl('x509','-in',root,'-outform','DER','-out',rootder)
  requests=[];requested=threading.Event();proceed=threading.Event()
  class Handler(SimpleHTTPRequestHandler):
   def log_message(self,*args):pass
   def finish(self):
    super().finish()
    self.connection.settimeout(2)
    try:self.connection.unwrap().close()
    except (OSError,ssl.SSLError):pass
   def do_GET(self):
    assert self.client_address[0]=='127.0.0.1';requests.append(self.path)
    if self.path==hold_path:requested.set();assert proceed.wait(15)
    try:return super().do_GET()
    except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
  web=area/'publication/web'
  server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(web)))
  url='https://localhost:'+str(server.server_port)+'/'
  published=publisher['publish']([Path(package)],url,area/'publication')
  configuration['prepare'](published['catalog_url'],web/'catalog.txt',rootder,area/'configuration')
  context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(leaf,leafkey);server.socket=context.wrap_socket(server.socket,server_side=True)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:yield {'area':area,'url':url,'web':web,'configuration':area/'configuration/HOMEBREW/repository','ca_pem':root,'ca_der':rootder,'requests':requests,'package':Path(package),'requested':requested,'proceed':proceed}
  finally:proceed.set();server.shutdown();server.server_close();thread.join(timeout=5);assert not thread.is_alive()
if __name__=='__main__':
 package=ROOT/'work/hello-app/package'
 with repository_fixture(package) as fixture:
  trusted=ssl.create_default_context(cafile=str(fixture['ca_pem']))
  with urllib.request.urlopen(fixture['url']+'catalog.txt',context=trusted,timeout=10) as response:catalog=response.read()
  assert catalog==(fixture['web']/'catalog.txt').read_bytes()
  assert fixture['requests']==['/catalog.txt']
  try:urllib.request.urlopen(fixture['url']+'catalog.txt',context=ssl.create_default_context(),timeout=10)
  except urllib.error.URLError as error:assert isinstance(error.reason,ssl.SSLCertVerificationError)
  else:raise AssertionError('Untrusted test root was accepted')
  report={'passed':True,'scope':'host-only local HTTPS fixture; actual ARM store not yet connected','loopback_only':True,'hostname_and_CA_verified':True,'untrusted_CA_rejected':True,'catalog_sha256':hashlib.sha256(catalog).hexdigest(),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tools/publish_repository.py',ROOT/'tools/prepare_repository_config.py',package/'app',package/'app.ini',package/'files.sha256']},'hardware_tested':False,'keys_temporary_and_not_packaged':True}
  (ROOT/'sources/native-production-store-https-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Loopback HTTPS fixture: trusted localhost catalog accepted; unknown test root rejected; server closed.')


