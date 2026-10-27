"""Native loop/UI/runtime over actual local DNS/TLS and synthetic QQ protocol."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
from pathlib import Path
import argparse,hashlib,json,re,socket,ssl,struct,subprocess,tempfile,threading,time,shutil
import qrcode,zxingcpp
from urllib.parse import urlsplit,parse_qs
parser=argparse.ArgumentParser();parser.add_argument('--devices',action='store_true');parser.add_argument('--entry-boot',action='store_true');options=parser.parse_args()
if options.entry_boot:options.devices=True
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work'/('qqmusic-entry-boot' if options.entry_boot else ('qqmusic-device-loop' if options.devices else 'qqmusic-loop'));work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';math=ROOT/'work/qqmusic-codec/libm.so.6'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
font=ROOT/'work/qqmusic-font/QQMusicUI.otf'
qr=qrcode.QRCode(version=3,error_correction=qrcode.constants.ERROR_CORRECT_M,border=0);qr.add_data('walkman-qq-synthetic');qr.make(fit=False);matrix=qr.get_matrix()
import zlib
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
pixels=bytearray()
for y in range(87):pixels.append(0);pixels.extend(0 if matrix[y//3][x//3] else 255 for x in range(87))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',87,87,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export','ui','image','runtime','identity','qimei','tls','network','loop')
sources=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in modules]
sources+=['runtime/store/'+name+'.c' for name in ('https_url','resolver','connect_step','socket_step','tls_socket_step','deadline','tls_platform','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]
sources+=['runtime/store/start.S','runtime/native/sha256.c','tools/fixtures/qqmusic_loop.c']
if options.entry_boot:sources[-1]='tools/fixtures/qqmusic_entry_boot.c'
if options.devices:sources+=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in ('devices','entry','program','asset','volume','storage')]+['runtime/native/linux_devices.c','runtime/native/frontend.c']
if options.entry_boot:sources+=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in ('source','output','directory','stage','stage_volume')]
app=work/'loop-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC',
 '-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie',
 '-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),
 '-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb',*(['-DQQ_LOOP_DEVICE_BRIDGE'] if options.devices else []),*(['-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64'] if options.entry_boot else []),*sources,
 str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
if options.entry_boot:
 for fault in range(3):
  with tempfile.TemporaryDirectory(prefix='boot-',dir=work) as directory:
   shutil.copyfile(font,Path(directory)/'font.otf')
   process=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app),directory,str(fault)],cwd=ROOT,capture_output=True,text=True,timeout=30)
   assert process.returncode==0,(fault,process.returncode,process.stderr[-4000:]);assert not list(Path(directory).iterdir())
 report={'passed':True,'scope':'actual_entry_and_program_volume_asset_font_runtime_ui_devices_loop','physical_device_tested':False,'real_qq_service_contacted':False,'checks':['real pinned font resource load','actual renderer submits nonempty frame','stop exits and closes devices','display failure cleanup','close failure propagation','readonly volume and asset regression','program identity and network initialization to same entry'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/fixtures/qqmusic_volume.c']},'arm_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'limits':['Mount table/path mapping and raw screen/touch syscalls are fixtures.','No login or network requests; program boot placeholder anchor is not used for TLS.','No device writes, downloads or stock index refresh.']}
 (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2));raise SystemExit(0)
hosts={'ssl.ptlogin2.qq.com','ssl.ptlogin2.graph.qq.com','graph.qq.com','u.y.qq.com'};rows=[]
with tempfile.TemporaryDirectory(prefix='local-certs-',dir=work) as directory:
 cert=Path(directory)
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(cert/'key.pem'),'-out',str(cert/'cert.pem'),
  '-days','1','-subj','/CN=graph.qq.com','-addext','subjectAltName='+','.join('DNS:'+host for host in sorted(hosts)),
  '-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['openssl','x509','-in',str(cert/'cert.pem'),'-outform','DER','-out',str(cert/'cert.der')],check=True)
 for mode in ((0,1,3) if options.devices else (0,1,2,3)):
  udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(.1)
  tcp=socket.socket();tcp.bind(('127.0.0.1',0));tcp.listen(4);tcp.settimeout(.2)
  dns_port=udp.getsockname()[1];tls_port=tcp.getsockname()[1];stop=threading.Event();observed=[];errors=[];polls=[0]
  def serve_dns():
   try:
    while not stop.is_set():
     try:data,peer=udp.recvfrom(1024)
     except socket.timeout:continue
     at=12;parts=[]
     while data[at]:size=data[at];at+=1;parts.append(data[at:at+size]);at+=size
     at+=5;assert b'.'.join(parts).decode() in hosts
     reply=data[:2]+struct.pack('>HHHHH',0x8180,1,1,0,0)+data[12:at]+b'\xc0\x0c'+struct.pack('>HHIH',1,1,60,4)+socket.inet_aton('127.0.0.1')
     udp.sendto(reply,peer)
   except Exception as exc:errors.append('DNS-'+type(exc).__name__)
  def serve_tls():
   context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
   context.load_cert_chain(cert/'cert.pem',cert/'key.pem')
   context.set_servername_callback(lambda connection,name,unused:setattr(connection,'fixture_sni',name))
   while not stop.is_set():
    connection=None
    try:
     try:peer,_=tcp.accept()
     except socket.timeout:continue
     peer.settimeout(3);connection=context.wrap_socket(peer,server_side=True);request=b''
     while b'\r\n\r\n' not in request:
      part=connection.recv(4096);assert part;request+=part;assert len(request)<=8192
     head,body=request.split(b'\r\n\r\n',1);lines=head.split(b'\r\n')
     header={key.lower():value.strip() for line in lines[1:] for key,value in [line.split(b':',1)]}
     length=int(header.get(b'content-length',b'0'))
     while len(body)<length:
      part=connection.recv(4096);assert part;body+=part
     assert len(body)==length
     host=header[b'host'].decode();assert host in hosts and connection.fixture_sni==host
     cookies=dict(part.strip().split(b'=',1) for part in header.get(b'cookie',b'').split(b';') if part.strip())
     path=urlsplit(lines[0].split()[1].decode()).path;status=b'200 OK';extra=b''
     if path=='/ptqrshow':
      assert host=='ssl.ptlogin2.qq.com';result=png;extra=b'Content-Type: image/png\r\nSet-Cookie: qrsig=synthetic; Secure\r\n';label='qr'
     elif path=='/ptqrlogin':
      assert cookies[b'qrsig']==b'synthetic'
      polls[0]+=1
      if polls[0]==1:result=b"ptuiCB('67','0','','0','scanned','');"
      else:result=b"ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=123456&service=ptqrlogin&ptsigx=synthetic_sig&s_url=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump','0','ok','test');"
      label='poll'
     elif path=='/check_sig':
      result=b'';status=b'302 Found';extra=b'Location: https://graph.qq.com/oauth2.0/login_jump\r\nSet-Cookie: p_skey=synthetic_key; Domain=.graph.qq.com; Path=/; Secure\r\nSet-Cookie: p_uin=o00123456; Domain=.graph.qq.com; Path=/; Secure\r\n';label='sig'
     elif path=='/oauth2.0/authorize':
      assert cookies[b'p_skey']==b'synthetic_key' and cookies[b'p_uin']==b'o00123456'
      params=parse_qs(body.decode());state=params['state'][0];assert re.fullmatch('[0-9a-f]{64}',state)
      result=b'';status=b'302 Found';extra=b'Location: https://y.qq.com/portal/wx_redirect.html?code=synthetic_code&state='+state.encode()+b'\r\n';label='oauth'
     else:
      assert host=='u.y.qq.com' and path=='/cgi-bin/musicu.fcg';payload=json.loads(body);method=payload['req_0']['method'];label=method
      if method!='QQLogin':assert payload['comm']['qq']=='123456' and payload['comm']['authst']=='synthetic_music_key'
      if method=='QQLogin':data={'musicid':123456,'musickey':'synthetic_music_key','encryptUin':'synthetic_uin','loginType':2}
      elif method=='GetLoginUserInfo':data={'musicid':123456}
      elif method=='GetPlaylistByUin':data={'total':1,'bFinish':True,'v_playlist':[{'tid':0,'dirid':201,'title':'我喜欢','songnum':1}]}
      elif method=='CgiGetDiss':
       assert payload['req_0']['param']['dirid']==201 and payload['req_0']['param']['enc_host_uin']=='synthetic_uin'
       data={'total_song_num':1,'hasmore':0,'songlist':[{'id':2,'mid':'MID02','title':'合成歌曲','album':{'id':1,'mid':'ALBUM1','name':'专辑'},'singer':[{'name':'歌手'}],'file':{'media_mid':'MEDIA02'}}]}
      else:
       assert method=='CgiGetEVkey';data={'expiration':60,'midurlinfo':[{'result':0,'songmid':'MID02','filename':'O4M0MEDIA02.mgg','purl':'O4M0MEDIA02.mgg?vkey=synthetic','ekey':'synthetic-only'}],'sip':['https://isure.stream.qqmusic.qq.com/']}
      result=json.dumps({'code':0,'req_0':{'code':0,'data':data}},ensure_ascii=False,separators=(',',':')).encode()
     observed.append(label)
     connection.sendall(b'HTTP/1.1 '+status+b'\r\n'+extra+b'Content-Length: '+str(len(result)).encode()+b'\r\n\r\n'+result)
     raw=connection.unwrap();connection=None;raw.close()
    except (ssl.SSLError,ConnectionError,TimeoutError,OSError):pass
    except Exception as exc:errors.append('TLS-'+type(exc).__name__)
    finally:
     if connection:connection.close()
  dns=threading.Thread(target=serve_dns,daemon=True);server=threading.Thread(target=serve_tls,daemon=True);dns.start();server.start()
  frame=work/f'qr-{mode}.rgb565'
  process=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app),str(dns_port),str(tls_port),str(cert/'cert.der'),str(font),str(frame),str(mode)],cwd=ROOT,capture_output=True,text=True,timeout=60)
  stop.set();dns.join(2);server.join(4);udp.close();tcp.close()
  assert not dns.is_alive() and not server.is_alive() and not errors,(mode,errors)
  assert process.returncode==0,(mode,process.returncode,process.stderr[-4000:])
  operations=[line for line in process.stderr.splitlines() if re.search(r'\b(?:connect|sendto)\(',line)]
  assert all('127.0.0.1' in line for line in operations)
  if mode==0:
   assert observed==['qr','poll','poll','sig','oauth','QQLogin','GetLoginUserInfo','GetPlaylistByUin','CgiGetDiss','CgiGetEVkey'],observed
   rgb=bytearray()
   for value in struct.unpack('<103680H',frame.read_bytes()):rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
   result=zxingcpp.read_barcode(memoryview(rgb).cast('B',shape=[432,240,3]));assert result and result.text=='walkman-qq-synthetic'
  rows.append({'mode':['protocol_chain','display_failure','clock_failure','close_failure'][mode],'passed':True,'observed_methods':observed})
report={'passed':True,'scope':'native_loop_runtime_actual_dns_tls_synthetic_service','real_qq_service_contacted':False,'device_tested':False,
 'platform_adapter_included':options.devices,'raw_hardware_io_mocked':True,
 'cases':rows,'arm_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_loop.h']},
 'limits':['Display/touch are fixtures, not physical devices.','Device identity and trust are explicit test inputs.','Import remains blocked; no player files or stock index operations.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
