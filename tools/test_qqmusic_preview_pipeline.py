"""Native candidate pipeline with local synthetic HTTPS MGG and modeled OSS only."""
from pathlib import Path
import argparse,base64,hashlib,importlib.util,json,os,shutil,socket,ssl,struct,subprocess,tempfile,threading
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--candidate',default='work/qqmusic-device-preview-3');args=p.parse_args()
if os.geteuid()!=0:raise SystemExit('Use a privileged isolated development environment for the actual proc FD scan.')
candidate=(ROOT/args.candidate).resolve();assert candidate.is_relative_to(ROOT/'work')
build=json.loads((candidate/'build.json').read_text());assert build['audio_preview_enabled']
for name,digest in build['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
w=ROOT/'work/qqmusic-preview-pipeline';w.mkdir(exist_ok=True)
run=Path(tempfile.mkdtemp(prefix='synthetic-',dir=w));host='isure.stream.qqmusic.qq.com'
key=bytes((i*37+19)%256 for i in range(64));ekey=base64.b64encode(key).decode();(run/'key.synthetic').write_text(ekey)
ogg=run/'generated.ogg';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar','44100','-ac','2','-c:a','libvorbis',str(ogg)],check=True)
reference=ROOT/'third_party/qmc-reference/qmc2_reference.py';assert hashlib.sha256(reference.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_ref',reference);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
payload=bytearray(ogg.read_bytes());ref.map_decrypt(payload,key);payload=bytes(payload);(run/'generated.mgg').write_bytes(payload)
cert=run/'cert.pem';private=run/'key.pem';der=run/'ca.der'
subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(private),'-out',str(cert),'-days','1','-subj','/CN='+host,'-addext','subjectAltName=DNS:'+host,'-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['openssl','x509','-in',str(cert),'-outform','DER','-out',str(der)],check=True)
header=[]
for line in (candidate/'qqmusic_profile.h').read_text().splitlines():
 if line.startswith('#define QQ_PROFILE_CA_COUNT '):break
 header.append('#define QQ_PROFILE_SOURCE "/dev/mock-user"' if line.startswith('#define QQ_PROFILE_SOURCE ') else line)
data=der.read_bytes();header+=['#define QQ_PROFILE_CA_COUNT 1','static const unsigned char ca_0[]={'+','.join(str(b) for b in data)+'};','static const unsigned char *const qq_profile_ca[]={ca_0};','static const size_t qq_profile_ca_size[]={sizeof(ca_0)};']
(w/'qqmusic_profile.h').write_text('\n'.join(header)+'\n');shutil.copyfile(candidate/'qqmusic_preview_profile.h',w/'qqmusic_preview_profile.h')
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';codec=ROOT/'work/qqmusic-codec';fixture=w/'pipeline.o'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DQQ_NATIVE_FULL','-DQQ_NATIVE_PREVIEW','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-DQQ_PIPELINE_SYNTHETIC_KEY='+json.dumps(ekey),'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(w),'-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb','-c','tools/fixtures/qqmusic_preview_pipeline.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[]
for i,name in enumerate(build['sources']):
 if Path(name).suffix not in ('.c','.S') or name in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/native/syscalls.S'):continue
 obj=codec/(str(i)+'-'+Path(name).stem+'.o');assert obj.is_file();objects.append(str(obj))
app=w/'pipeline.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=qq_runtime_bind_preview,--wrap=qq_runtime_step,--wrap=qq_runtime_close,--wrap=qq_preview_runtime_run,--wrap=qq_preview_device_posix_io,--wrap=qq_import_binding_detach_child,--wrap=qq_preview_source_job_run,--wrap=qq_volume_open,--wrap=qq_network_media_begin,--wrap=qq_preview_service_pump',str(fixture),*objects,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
worker=ROOT/'work/qqmusic-preview-decode-worker';worker_report=json.loads((worker/'report.json').read_text())
for name,digest in worker_report['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
expected=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(worker/'worker.arm'),str(run/'generated.mgg'),str(run/'key.synthetic'),'30000'],capture_output=True,check=True,timeout=20).stdout
assert len(expected)==176400 and any(expected)
short_payload=payload;short_expected=expected
long_ogg=run/'long.ogg';subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=31','-ar','44100','-ac','2','-c:a','libvorbis',str(long_ogg)],check=True)
long_payload=bytearray(long_ogg.read_bytes());ref.map_decrypt(long_payload,key);long_payload=bytes(long_payload);(run/'long.mgg').write_bytes(long_payload)
long_expected=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(worker/'worker.arm'),str(run/'long.mgg'),str(run/'key.synthetic'),'30000'],capture_output=True,check=True,timeout=30).stdout;assert len(long_expected)==5292000
cases=[]
for mode in range(6):
 payload=long_payload if mode==5 else short_payload;expected=long_expected if mode==5 else short_expected
 case=run/f'case-{mode}';case.mkdir();shutil.copyfile(ROOT/'work/qqmusic-font/QQMusicUI.otf',case/'font.otf')
 udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(.1)
 tcp=socket.socket();tcp.bind(('127.0.0.1',0));tcp.listen(1);tcp.settimeout(10)
 stop=threading.Event();errors=[];requests=[]
 def dns():
  try:
   while not stop.is_set():
    try:packet,peer=udp.recvfrom(1024)
    except socket.timeout:continue
    at=12;labels=[]
    while packet[at]:n=packet[at];at+=1;labels.append(packet[at:at+n]);at+=n
    at+=5;assert b'.'.join(labels).decode()==host
    udp.sendto(packet[:2]+struct.pack('>HHHHH',0x8180,1,1,0,0)+packet[12:at]+b'\xc0\x0c'+struct.pack('>HHIH',1,1,60,4)+socket.inet_aton('127.0.0.1'),peer)
  except Exception as e:
   if not stop.is_set():errors.append('DNS '+type(e).__name__)
 def serve():
  connection=None
  try:
   peer,_=tcp.accept();peer.settimeout(3);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(cert,private);context.set_servername_callback(lambda c,name,unused:setattr(c,'fixture_host',name));connection=context.wrap_socket(peer,server_side=True);request=b''
   while b'\r\n\r\n' not in request:
    block=connection.recv(4096);assert block;request+=block;assert len(request)<8192
   assert connection.fixture_host==host and request.startswith(b'GET /O6M0MEDIA01.mgg?vkey=synthetic HTTP/1.1\r\n') and b'cookie:' not in request.lower();requests.append(True)
   connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: '+str(len(payload)).encode()+b'\r\nConnection: close\r\n\r\n'+(payload[:len(payload)//2] if mode==2 else payload))
   if mode!=2:
    try:connection.unwrap()
    except (ssl.SSLError,socket.timeout,ConnectionError):pass
  except Exception as e:errors.append('HTTPS '+type(e).__name__)
  finally:
   if connection:connection.close()
 threads=[threading.Thread(target=dns,daemon=True),threading.Thread(target=serve,daemon=True)]
 for t in threads:t.start()
 try:
  r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{codec}',str(app),str(case),str(tcp.getsockname()[1]),str(udp.getsockname()[1]),str(mode)],cwd=ROOT,capture_output=True,timeout=35)
  assert r.returncode==0,(mode,r.returncode,r.stderr[-2600:],errors,len(requests))
 finally:
  stop.set();udp.close();tcp.close()
  for t in threads:t.join(2)
 assert not errors and len(requests)==1,(mode,errors,len(requests))
 result=json.loads((case/'result.json').read_text());accepted=(case/'accepted.pcm').read_bytes();assert accepted[:result['pcm_bytes']]==expected[:result['pcm_bytes']];assert accepted[result['pcm_bytes']:]==b'\0'*result['padding']
 workspace=case/'contents/HOMEBREW/data/qqmusic';sources=list(workspace.glob('.qq-source-*.part'));receipts=list(workspace.glob('.qq-preview-source-*.bin'));assert not list((case/'contents/MUSIC').rglob('*.mp3'))
 if mode!=2:
  assert len(sources)==len(receipts)==1 and sources[0].read_bytes()==payload
  record=receipts[0].read_bytes();assert len(record)==384 and record[:8]==b'QQPVSR1\0' and struct.unpack_from('<Q',record,8)[0]==len(payload) and record[16:48]==hashlib.sha256(payload).digest() and hashlib.sha256(record[:352]).digest()==record[352:]
  assert ekey.encode() not in record and b'vkey' not in record
 else:assert not sources and not receipts
 result['case']=['normal EOF','preview cancel','truncated HTTPS','UI shutdown','UI SIGKILL','30-second prefix of 31-second source'][mode];cases.append(result)
report={'passed':True,'candidate_sha256':build['app_sha256'],'cases':cases,'actual_local_https_new_download':True,'actual_user_stage_receipt_source_decode_transport_client_service':True,'same_candidate_module_objects':True,'physical_device_accessed':False,'real_account_accessed':False,'limits':['Synthetic selected song/authorization and explicit local test CA/DNS; no real account APIs.','Software preflight and OSS driver effects are modeled; no audio node is opened.','Physical timing, sound output and AudioC restoration remain unqualified.'],'fixture_sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['tools/fixtures/qqmusic_preview_pipeline.c','tools/fixtures/qqmusic_entry_boot.c','tools/fixtures/qqmusic_volume.c']}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))





