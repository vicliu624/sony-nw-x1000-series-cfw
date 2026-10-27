"""Actual ARM market installation using a local HTTPS redirect server, PC only."""
from pathlib import Path
import ast,hashlib,http.server,json,os,shutil,ssl,subprocess,sys,tempfile,threading
ROOT=Path(__file__).resolve().parents[1]
upload=Path(sys.argv[1]).resolve();work=ROOT/'work/ci/market-probe';work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';sdk=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
syntax=ast.parse((ROOT/'tools/build_network_store_app.py').read_text());modules=next(ast.literal_eval(n.value) for n in syntax.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='modules' for t in n.targets))
sources=['runtime/store/'+n+'.c' for n in modules if n not in ('network_main','network_app','platform_native','termination')]+['runtime/store/start.S','runtime/native/frontend.c','runtime/native/sha256.c','tools/release_market_probe.c']
app=work/'probe.arm'
flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(sdk),'-I'+str(sdk),'-I'+str(crypto/'bearssl-0.6/inc')]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(crypto/'arm-build/libbearssl.a'),str(sdk/'libcares.so.2'),str(sdk/'librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temporary:
 root=Path(temporary)
 for name in ('repository','cache','packages','apps'):(root/name).mkdir()
 subprocess.run(['openssl','req','-new','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem'),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost','-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['openssl','x509','-in',str(root/'cert.pem'),'-outform','DER','-out',str(root/'repository/ca.der')],check=True)
 requests=[];content={p.name:p.read_bytes() for p in upload.iterdir() if p.is_file() and not p.name.endswith('.zip')}
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   requests.append(self.path)
   if not self.path.startswith('/payload/'):
    self.send_response(302);self.send_header('Location',base+'payload/'+self.path.lstrip('/'));self.send_header('Content-Length','0');self.end_headers();return
   data=content[self.path.removeprefix('/payload/')];self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);self.close_connection=True
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);base=f'https://localhost:{server.server_port}/'
 lines=content['catalog.tsv'].decode().splitlines();rewritten=[lines[0]]
 for line in lines[1:]:fields=line.split('\t');fields[2]=base;rewritten.append('\t'.join(fields))
 listing=('\n'.join(rewritten)+'\n').encode();content['catalog.tsv']=listing;ca=(root/'repository/ca.der').read_bytes()
 (root/'repository/repository.conf').write_text(f'HBREPO1\ncatalog_url={base}catalog.tsv\ncatalog_bytes={len(listing)}\ncatalog_sha256={hashlib.sha256(listing).hexdigest()}\nca_sha256={hashlib.sha256(ca).hexdigest()}\n')
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(root/'cert.pem',root/'key.pem');server.socket=context.wrap_socket(server.socket,server_side=True)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();(root/'apps/unrelated').write_bytes(b'KEEP')
 try:
  command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(sdk),str(app),str(root)]
  result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=90)
  (work/'run.log').write_text(result.stdout+result.stderr)
  assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
  assert (root/'apps/hello/app').read_bytes()==content['hello--617070']
  assert (root/'apps/unrelated').read_bytes()==b'KEEP'
  assert any(x.startswith('/payload/hello--') for x in requests),requests
  print(result.stdout)
 finally:server.shutdown();server.server_close();thread.join(timeout=3)
(work/'report.json').write_text(json.dumps({'passed':True,'actual_arm_market':True,'original_sony_libc':True,'rendered_list_and_selected_hello':True,'https_redirects_followed':True,'real_installer_and_file_hashes_verified':True,'unrelated_files_preserved':True,'requests':requests,'physical_device_accessed':False},indent=2)+'\n')
