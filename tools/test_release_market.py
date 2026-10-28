"""Actual ARM market installation using a local HTTPS redirect server, PC only."""
from pathlib import Path
import ast,hashlib,http.server,json,os,shutil,ssl,subprocess,sys,tempfile,threading
from market_metadata import descriptions
ROOT=Path(__file__).resolve().parents[1]
upload=Path(sys.argv[1]).resolve();work=ROOT/'work/ci/market-probe';work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';sdk=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
recipe=json.loads((ROOT/'runtime/apps/store/build.json').read_text())
excluded={'network_main','network_app','platform_native','termination','linux_devices','linux_device_io_posix'}
sources=[(name[2:] if name.startswith('@/') else 'runtime/apps/store/'+name) for name in recipe['sources'] if Path(name).stem not in excluded]+['tools/release_market_probe.c']
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
 lines=content['catalog.tsv'].decode().splitlines();rewritten=['HBSTORE3'];info=descriptions()
 for line in lines[1:]:
  fields=line.split('\t');fields[2]=base
  if len(fields)==8:
   meta=info[fields[0]];index=content[fields[7]+'files.sha256'.encode().hex()]
   size=sum(int(row.split(' ')[1]) for row in index.decode().splitlines()[1:] if row.split(' ')[2]!='app.ini')
   manifest=content[fields[7]+'app.ini'.encode().hex()];actual_title=dict(row.split('=',1) for row in manifest.decode().splitlines())['name']
   fields.extend([actual_title,*[meta[k] for k in ('summary','description','changes','channel')],str(size)])
  rewritten.append('\t'.join(fields))
 listing=('\n'.join(rewritten)+'\n').encode();content['catalog.tsv']=listing;ca=(root/'repository/ca.der').read_bytes()
 (root/'repository/repository.conf').write_text(f'HBREPO1\ncatalog_url={base}catalog.tsv\ncatalog_bytes={len(listing)}\ncatalog_sha256={hashlib.sha256(listing).hexdigest()}\nca_sha256={hashlib.sha256(ca).hexdigest()}\n')
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(root/'cert.pem',root/'key.pem');server.socket=context.wrap_socket(server.socket,server_side=True)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();(root/'apps/unrelated').write_bytes(b'KEEP')
 try:
  scenarios=[]
  for scenario,old_version,status in [('install',None,0),('reinstall','same',1),('update','0.0.1',2),('downgrade','9.0.0',3)]:
   case=root/scenario;case.mkdir()
   for name in ('repository','cache','packages','apps'):(case/name).mkdir()
   for name in ('ca.der','repository.conf'):shutil.copyfile(root/'repository'/name,case/'repository'/name)
   (case/'apps/unrelated').write_bytes(b'KEEP')
   (case/'personal-data').mkdir();(case/'personal-data/save.bin').write_bytes(b'USER SAVE')
   if old_version:
    folder=case/'apps/hello';folder.mkdir()
    index=content['hello--'+b'files.sha256'.hex()];data={}
    for row in index.decode().splitlines()[1:]:
     path=row.split(' ')[2];data[path]=content['hello--'+path.encode().hex()]
    if old_version!='same':
     values=dict(line.split('=',1) for line in data['app.ini'].decode().splitlines());values['version']=old_version
     data['app.ini']=''.join(f'{k}={v}\n' for k,v in values.items()).encode()
    for path,value in data.items():
     target=folder/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
    (folder/'files.sha256').write_bytes(index if old_version=='same' else ('HBFILES1\n'+''.join(f'{hashlib.sha256(value).hexdigest()} {len(value)} {path}\n' for path,value in sorted(data.items()))).encode())
   command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(sdk),str(app),str(case)]
   result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=90,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'))
   (work/(scenario+'.log')).write_text(result.stdout+result.stderr)
   assert result.returncode==0,(scenario,result.returncode,result.stdout,result.stderr)
   assert 'local='+str(status) in result.stdout
   assert (case/'apps/hello/app').read_bytes()==content['hello--617070']
   assert (case/'apps/unrelated').read_bytes()==b'KEEP' and (case/'personal-data/save.bin').read_bytes()==b'USER SAVE'
   print(scenario,result.stdout);scenarios.append(scenario)
  assert any(x.startswith('/payload/hello--') for x in requests),requests
  print(result.stdout)
 finally:server.shutdown();server.server_close();thread.join(timeout=3)
(work/'report.json').write_text(json.dumps({'passed':True,'actual_arm_market':True,'original_sony_libc':True,'rich_catalog':True,'scenarios':scenarios,'rendered_list_and_selected_hello':True,'https_redirects_followed':True,'real_installer_and_file_hashes_verified':True,'unrelated_files_preserved':True,'requests':requests,'physical_device_accessed':False},indent=2)+'\n')
