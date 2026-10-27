"""ARM DNS/connect/BearSSL runtime-ops integration; loopback fixtures only."""
from pathlib import Path
import hashlib,json,os,re,socket,ssl,struct,subprocess,tempfile,threading,time,sys
files='--files' in sys.argv;media=files or '--media' in sys.argv;target_host='isure.stream.qqmusic.qq.com' if media else 'graph.qq.com'
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work'/('qqmusic-media-files' if files else ('qqmusic-media-network' if media else 'qqmusic-network'));work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
sources=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in ('session','protocol','cookie','http','response','tls','network','json','credential','cgi','resource')]
sources+=['runtime/store/'+name+'.c' for name in ('https_url','resolver','connect_step','socket_step','tls_socket_step','deadline','tls_platform','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]
sources+=['runtime/store/start.S','runtime/native/sha256.c','tools/fixtures/qqmusic_network.c']
if files:sources+=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in ('download','volume','storage','stage','stage_volume','source','output','directory','asset')]
app=work/'network-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC',
 '-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie',
 '-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),
 '-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),*(['-DQQ_NETWORK_MEDIA_FIXTURE'] if media else []),*(['-DQQ_NETWORK_FILE_FIXTURE','-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64'] if files else []),*sources,str(crypto/'arm-build/libbearssl.a'),
 str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
rows=[]
cases=['fixed','chunked','no-time','no-entropy','cancel-dns','cancel-tls','raw-eof','hostname','untrusted','deadline-dns','stall-close','unapproved-host','no-trust','nxdomain','address-fallback','expired']
if media:cases+=['sink-failure','body-limit','redirect','truncated']
payload=bytes(i%251 for i in range(1048576)) if media else b'hello'
with tempfile.TemporaryDirectory(prefix='local-certs-',dir=work) as directory:
 certificates=Path(directory)
 for name,host in [('good',target_host),('wrong','localhost')]:
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(certificates/(name+'.key')),
   '-out',str(certificates/(name+'.pem')),'-days','1','-subj','/CN='+host,'-addext','subjectAltName=DNS:'+host,
   '-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  subprocess.run(['openssl','x509','-in',str(certificates/(name+'.pem')),'-outform','DER','-out',str(certificates/(name+'.der'))],check=True)
 for mode,case in enumerate(cases):
  udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(.1)
  tcp=socket.socket();tcp.bind(('127.0.0.1',0));tcp.listen(2);tcp.settimeout(.8)
  dns_port=udp.getsockname()[1];tls_port=tcp.getsockname()[1]
  stopped=threading.Event();observed=[];queries=[];errors=[]
  def dns_server():
   try:
    while not stopped.is_set():
     try:packet,peer=udp.recvfrom(1024)
     except socket.timeout:continue
     at=12;parts=[]
     while packet[at]:length=packet[at];at+=1;parts.append(packet[at:at+length]);at+=length
     at+=5;name=b'.'.join(parts).decode();assert name==target_host;queries.append(name)
     if case=='deadline-dns':continue
     addresses=[] if case=='nxdomain' else ['127.0.0.2','127.0.0.1'] if case=='address-fallback' else ['127.0.0.1']
     answer=packet[:2]+struct.pack('>HHHHH',0x8183 if not addresses else 0x8180,1,len(addresses),0,0)+packet[12:at]
     for address in addresses:answer+=b'\xc0\x0c'+struct.pack('>HHIH',1,1,60,4)+socket.inet_aton(address)
     udp.sendto(answer,peer)
   except Exception as exc:errors.append('fixture-dns-'+type(exc).__name__)
  def tls_server():
   connection=None
   try:
    peer,_=tcp.accept();peer.settimeout(5 if media else 2)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
    cert='wrong' if case=='hostname' else 'good'
    context.load_cert_chain(certificates/(cert+'.pem'),certificates/(cert+'.key'))
    connection=context.wrap_socket(peer,server_side=True)
    request=b''
    while b'\r\n\r\n' not in request:
     part=connection.recv(4096)
     if not part:return
     request+=part;assert len(request)<=8192
    head,body=request.split(b'\r\n\r\n',1)
    if media:
     assert head.startswith(('GET /M500MEDIA01.mp3?vkey=synthetic HTTP/1.1\r\nHost: '+target_host+'\r\n').encode()) and not body
     assert b'cookie:' not in head.lower() and b'must-not-enter-transport' not in request
    else:
     length=int(next(value.split(b':',1)[1] for value in head.split(b'\r\n') if value.lower().startswith(b'content-length:')))
     while len(body)<length:body+=connection.recv(4096)
     assert head.startswith(b'POST /oauth2.0/authorize HTTP/1.1\r\nHost: graph.qq.com\r\n') and len(body)==length
    observed.append(True)
    response=b'HTTP/1.1 200 OK\r\n'+(b'' if media else b'Set-Cookie: fixture=synthetic; Secure\r\n')
    if case=='chunked':response+=b'Transfer-Encoding: chunked\r\n\r\n'+b''.join(('%x\r\n'%len(payload[i:i+1024])).encode()+payload[i:i+1024]+b'\r\n' for i in range(0,len(payload),1024))+b'0\r\n\r\n'
    else:response+=('Content-Length: %d\r\n\r\n'%len(payload)).encode()+(payload[:-100] if case=='truncated' else payload)
    if case=='redirect':response=b'HTTP/1.1 302 Found\r\nLocation: https://unapproved.invalid/\r\nContent-Length: 0\r\n\r\n'
    connection.sendall(response)
    if case=='stall-close':time.sleep(1.5 if media else .6)
    if case=='raw-eof':os.close(connection.detach());connection=None
    else:raw=connection.unwrap();connection=None;raw.close()
   except (ssl.SSLError,ConnectionError,TimeoutError,OSError) as exc:errors.append(type(exc).__name__)
   except Exception as exc:errors.append('fixture-'+type(exc).__name__)
   finally:
    if connection:connection.close()
    tcp.close()
  dns=threading.Thread(target=dns_server,daemon=True);server=threading.Thread(target=tls_server,daemon=True)
  dns.start();server.start()
  anchor='wrong' if case in ('hostname','untrusted') else 'good'
  volume=certificates/('volume-'+str(mode))
  if files:volume.mkdir()
  process=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver),
   str(app),str(dns_port),str(tls_port),str(certificates/(anchor+'.der')),str(mode),*([str(volume)] if files else [])],cwd=ROOT,capture_output=True,text=True,timeout=40 if files else (25 if media else 12))
  stopped.set();dns.join(2);server.join(3);udp.close()
  assert not dns.is_alive() and not server.is_alive(),case
  assert process.returncode==0,(case,process.returncode,process.stderr[-4000:])
  if files:assert not list(volume.iterdir());volume.rmdir()
  assert not any(error.startswith('fixture-') for error in errors),(case,errors)
  operations=[line for line in process.stderr.splitlines() if re.search(r'\b(?:connect|sendto)\(',line)]
  assert all('127.0.0.' in line for line in operations),(case,operations)
  if case in ('no-time','unapproved-host','no-trust'):assert not operations and not queries and not observed,case
  if case in ('fixed','chunked','raw-eof','stall-close','address-fallback'):assert observed,case
  rows.append({'case':case,'passed':True,'dns_queries':len(queries),'application_request_observed':bool(observed)})
report={'passed':True,'real_qq_service_contacted':False,'device_tested':False,'cases':rows,
 'arm_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_network.h','runtime/apps/qqmusic/qqmusic_tls.h','runtime/apps/qqmusic/qqmusic_runtime.h','tools/test_qqmusic_network.py']},
 'dependencies':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [crypto/'arm-build/libbearssl.a',resolver/'libcares.so.2',resolver/'librt.so.1',lib/'libc.so.6',lib/'ld-linux.so.3']},
 'limits':['Local DNS/TLS with explicitly supplied temporary test CA only.','Production trust provisioning and device identity are not supplied.','No player storage, streaming import or physical Wi-Fi qualification.']}
if media:
 report['scope']='actual_dns_tls_cookieless_bounded_media_stream';report['payload_bytes']=len(payload);report['limits']=['Loopback server and synthetic 1MiB payload with explicit temporary CA.','Sink checks bytes/hash and lifecycle in memory; actual staged-file adapter not yet tested here.','No real QQ download or physical Wi-Fi/storage qualification.']
if files:
 report['scope']='actual_dns_tls_stream_to_verified_user_volume_source';report['sources']['tools/fixtures/qqmusic_volume.c']=hashlib.sha256((ROOT/'tools/fixtures/qqmusic_volume.c').read_bytes()).hexdigest()
 report['sources']['runtime/apps/qqmusic/qqmusic_download.h']=hashlib.sha256((ROOT/'runtime/apps/qqmusic/qqmusic_download.h').read_bytes()).hexdigest()
 report['file_checks']=['actual exclusive source file','mount and space rechecked for each block','completed source survives cancellation','completed source ownership transfer','independent source hash and exact readback','failure leaves no partial source or descriptors']
 report['limits']=['Loopback service and synthetic 1MiB payload; actual file IO with fixture mount/path mapping.','No actual QQ account or Sony FAT/Wi-Fi qualification.','Not yet connected to application import UI or authorization expiry.']
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
