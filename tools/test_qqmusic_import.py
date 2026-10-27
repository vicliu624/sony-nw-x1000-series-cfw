"""Fresh synthetic source -> native QMC/Vorbis/tagged MP3 coordinator."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
from pathlib import Path
import base64,hashlib,importlib.util,json,struct,subprocess,tempfile,sys,socket,ssl,threading,re,zlib
binding_mode='--binding' in sys.argv;job_mode=binding_mode or '--job' in sys.argv;network_mode=job_mode or '--network' in sys.argv;file_mode=network_mode or '--files' in sys.argv
missing_cover='--missing-cover' in sys.argv
if missing_cover:assert job_mode and not binding_mode
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'work'/('qqmusic-binding-import' if binding_mode else ('qqmusic-job-import' if job_mode else ('qqmusic-transfer-import' if network_mode else ('qqmusic-file-import' if file_mode else 'qqmusic-import'))));base.mkdir(exist_ok=True)
if missing_cover:base=ROOT/'work/qqmusic-cover-job';base.mkdir(exist_ok=True)
(base/'report.json').unlink(missing_ok=True);work=Path(tempfile.mkdtemp(prefix='synthetic-',dir=base))
reference=ROOT/'third_party/qmc-reference/qmc2_reference.py';assert hashlib.sha256(reference.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_reference',reference);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
jpeg=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=8x8','-frames:v','1','-f','image2pipe','-vcodec','mjpeg','-'],check=True,capture_output=True).stdout
picture=struct.pack('>II',3,10)+b'image/jpeg'+struct.pack('>IIIIII',0,8,8,24,0,len(jpeg))+jpeg
source=work/'source.ogg'
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar','44100','-ac','2','-c:a','libvorbis','-q:a','4','-metadata','title=源标题','-metadata','artist=源艺人','-metadata','album=源专辑','-metadata','track=2/12','-metadata','disc=1/2','-metadata','date=2024-03-01','-metadata','CUSTOM_FIELD=源附加信息',*([] if missing_cover else ['-metadata','METADATA_BLOCK_PICTURE='+base64.b64encode(picture).decode()]),str(source)],check=True)
lib=ROOT/'work/arm-signal-tests/lib';codec=ROOT/'work/qqmusic-codec'
suffix='binding-import-tests' if binding_mode else ('job-import-tests' if job_mode else ('network-import-tests' if network_mode else ('file-import-tests' if file_mode else 'codec-tests')))
if file_mode:
 build_path=codec/('build-binding-import.json' if binding_mode else ('build-job-import.json' if job_mode else ('build-network-import.json' if network_mode else 'build-file-import.json')));built=json.loads(build_path.read_text())
 for path,digest in built['source_hashes'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
 assert 'tools/fixtures/qqmusic_volume.c' in built['source_hashes']
 assert hashlib.sha256((codec/(suffix+'.arm')).read_bytes()).hexdigest()==built['artifact_sha256']
 if not network_mode:assert hashlib.sha256((codec/(suffix+'.asan')).read_bytes()).hexdigest()==built['host_artifact_sha256']
backends={'arm':['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(codec),str(codec/(suffix+'.arm'))],'asan':[str(codec/(suffix+'.asan'))]}
if network_mode:
 resolver=ROOT/'work/stock-resolver-probe'
 prefix=['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(codec)+':'+str(resolver),str(codec/(suffix+'.arm'))]
 backends={'arm-fixed':prefix,'arm-chunked':prefix}
 host='isure.stream.qqmusic.qq.com';certificate=work/'cert.pem';private=work/'key.pem';der=work/'ca.der'
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(private),'-out',str(certificate),'-days','1','-subj','/CN='+host,'-addext','subjectAltName=DNS:'+host+',DNS:y.gtimg.cn','-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['openssl','x509','-in',str(certificate),'-outform','DER','-out',str(der)],check=True)
 frames=[]
 def network_run(prefix,args,payload,chunked):
  udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(.1)
  tcp=socket.socket();tcp.bind(('127.0.0.1',0));tcp.listen(1);tcp.settimeout(5)
  stop=threading.Event();errors=[];observed=[]
  def dns_server():
   try:
    while not stop.is_set():
     try:packet,peer=udp.recvfrom(1024)
     except socket.timeout:continue
     at=12;labels=[]
     while packet[at]:n=packet[at];at+=1;labels.append(packet[at:at+n]);at+=n
     at+=5;assert b'.'.join(labels).decode() in ((host,'y.gtimg.cn') if missing_cover else (host,))
     udp.sendto(packet[:2]+struct.pack('>HHHHH',0x8180,1,1,0,0)+packet[12:at]+b'\xc0\x0c'+struct.pack('>HHIH',1,1,60,4)+socket.inet_aton('127.0.0.1'),peer)
   except Exception as e:errors.append('dns-'+type(e).__name__)
  def tls_server():
   connection=None
   try:
    peer,_=tcp.accept();peer.settimeout(5);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(certificate,private)
    context.set_servername_callback(lambda connection,name,unused:setattr(connection,'fixture_name',name))
    connection=context.wrap_socket(peer,server_side=True);request=b''
    while b'\r\n\r\n' not in request:
     block=connection.recv(4096);assert block;request+=block;assert len(request)<8192
    source_file='O4M0MEDIA01.mgg' if args[3]=='output-128' else 'O8M0MEDIA01.mgg' if args[3]=='output-320' else 'O6M0MEDIA01.mgg'
    assert connection.fixture_name==host and request.startswith(('GET /'+source_file+'?vkey=synthetic HTTP/1.1\r\nHost: '+host+'\r\n').encode()) and b'cookie:' not in request.lower()
    observed.append(True)
    body=(b'Transfer-Encoding: chunked\r\n\r\n'+b''.join(('%x\r\n'%len(payload[i:i+1024])).encode()+payload[i:i+1024]+b'\r\n' for i in range(0,len(payload),1024))+b'0\r\n\r\n') if chunked else ('Content-Length: %d\r\n\r\n'%len(payload)).encode()+payload
    connection.sendall(b'HTTP/1.1 200 OK\r\n'+body);raw=connection.unwrap();connection=None;raw.close()
    if missing_cover:
     peer,_=tcp.accept();peer.settimeout(5);connection=context.wrap_socket(peer,server_side=True);request=b''
     while b'\r\n\r\n' not in request:
      block=connection.recv(4096);assert block;request+=block;assert len(request)<8192
     assert connection.fixture_name=='y.gtimg.cn' and request.startswith(b'GET /music/photo_new/T002R500x500M000ALBUM01.jpg HTTP/1.1\r\nHost: y.gtimg.cn\r\n') and b'cookie:' not in request.lower()
     observed.append('cover')
     connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nSet-Cookie: ignored=synthetic\r\nContent-Length: '+str(len(jpeg)).encode()+b'\r\n\r\n'+jpeg);raw=connection.unwrap();connection=None;raw.close()
   except Exception as e:errors.append('tls-'+type(e).__name__)
   finally:
    if connection:connection.close()
  threads=[threading.Thread(target=dns_server),threading.Thread(target=tls_server)]
  for thread in threads:thread.start()
  extra=[]
  if binding_mode:
   frame=work/('result-'+str(len(frames))+'.rgb565');frames.append(frame);extra=[str(ROOT/'work/qqmusic-font/QQMusicUI.otf'),str(frame)]
  try:result=subprocess.run(prefix+args+[str(udp.getsockname()[1]),str(tcp.getsockname()[1]),str(der)]+extra,cwd=ROOT,capture_output=True,timeout=60)
  finally:
   stop.set()
   for thread in threads:thread.join(6)
   udp.close();tcp.close()
  assert all(not thread.is_alive() for thread in threads) and not errors and observed,(errors,observed)
  if missing_cover:assert observed==[True,'cover'],observed
  calls=[line for line in result.stderr.decode(errors='replace').splitlines() if 'connect(' in line.lower() or 'sendto(' in line.lower()]
  assert calls and all('127.0.0.1' in line for line in calls),calls
  return result
inputs=[('vorbis',source,None)];plain=source.read_bytes()
for length in (64,512):
 key=bytes((i*37+19)%256 for i in range(length));keyfile=work/f'key-{length}';keyfile.write_bytes(base64.b64encode(key));encrypted=bytearray(plain)
 if length>300:ref.RC4(key).decrypt_into(encrypted,0)
 else:ref.map_decrypt(encrypted,key)
 path=work/f'source-{length}.mgg';path.write_bytes(encrypted);inputs.append((f'qmc-{length}',path,keyfile))
rows=[]
if job_mode:inputs=inputs[1:]
if missing_cover:inputs=inputs[:1]
for label,path,key in inputs:
 before=hashlib.sha256(path.read_bytes()).hexdigest()
 for backend,prefix in backends.items():
  args=[str(path),'192']+(['qmc',str(key)] if key else [])+['import']
  with tempfile.TemporaryDirectory(prefix='volume-',dir=work) as directory:
   if file_mode:args=[directory,str(path),str(key) if key else '-','ok']
   result=network_run(prefix,args,path.read_bytes(),backend.endswith('chunked')) if network_mode else subprocess.run(prefix+args,cwd=ROOT,capture_output=True,timeout=60)
   assert result.returncode==0,(label,backend,result.stderr[-4000:]);assert not list(Path(directory).iterdir())
  mp3=work/f'{label}-{backend}.mp3';mp3.write_bytes(result.stdout);assert result.stdout[:4]==b'ID3\x03'
  probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(mp3)],capture_output=True,check=True).stdout)
  tags={k.lower():v for k,v in probe['format']['tags'].items()}
  assert tags['title']=='源标题' and tags['artist']=='源艺人' and tags['album']=='源专辑' and tags['track']=='2/12' and tags['disc']=='1/2',tags
  assert tags['custom_field']=='源附加信息',tags
  if job_mode:assert 'album_artist' not in tags,tags
  else:assert tags['album_artist']=='接口专辑艺人',tags
  assert any(s['codec_type']=='audio' and s['codec_name']=='mp3' for s in probe['streams'])
  assert any(s['codec_name']=='mjpeg' and s['disposition']['attached_pic'] for s in probe['streams'])
  if missing_cover:
   extracted=subprocess.run(['ffmpeg','-v','error','-i',str(mp3),'-map','0:v:0','-c:v','copy','-f','image2pipe','-'],capture_output=True,check=True).stdout
   assert extracted==jpeg
  subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(mp3),'-map','0:a:0','-f','null','-'],capture_output=True,check=True)
  rows.append({'source':label,'backend':backend,'bytes':len(result.stdout),'source_first_tags':True,'fallback_album_artist':not job_mode,'source_cover':not missing_cover,'album_cover_fetched':missing_cover,'decoded':True})
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before
for mode in ([] if network_mode else (['limit','identity','stop','publish-sync','publish-rename','publish-stop'] if file_mode else ['import-limit','import-id'])):
 for backend,prefix in backends.items():
  with tempfile.TemporaryDirectory(prefix='failure-',dir=work) as directory:
   args=[directory,str(source),'-',mode] if file_mode else [str(source),'192',mode]
   result=subprocess.run(prefix+args,cwd=ROOT,capture_output=True,timeout=60);assert result.returncode==0 and not result.stdout,(mode,backend,result.stderr[-3000:]);assert not list(Path(directory).iterdir())
if binding_mode:
 for bitrate in (128,320):
  with tempfile.TemporaryDirectory(prefix='export-preset-',dir=work) as directory:
   result=network_run(backends['arm-fixed'],[directory,str(inputs[0][1]),str(inputs[0][2]),'output-'+str(bitrate)],inputs[0][1].read_bytes(),False)
   assert result.returncode==0,(bitrate,result.returncode,result.stderr[-4000:]);assert not list(Path(directory).iterdir())
  output=work/('preset-'+str(bitrate)+'.mp3');output.write_bytes(result.stdout)
  probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,check=True).stdout)
  audio=next(s for s in probe['streams'] if s['codec_type']=='audio');assert audio['codec_name']=='mp3' and int(audio['bit_rate'])==bitrate*1000 and probe['format']['tags']['title']=='源标题'
  subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-map','0:a:0','-f','null','-'],capture_output=True,check=True)
  rows.append({'source':'qmc-64','backend':'arm-fixed-preset-'+str(bitrate),'output_bitrate_kbps':bitrate,'bytes':len(result.stdout),'source_first_tags':True,'decoded':True})
if job_mode and not binding_mode and not missing_cover:
 for mode in ['checkpoint-source','checkpoint-output','checkpoint-published']:
  with tempfile.TemporaryDirectory(prefix='checkpoint-failure-',dir=work) as directory:
   result=network_run(backends['arm-fixed'],[directory,str(inputs[0][1]),str(inputs[0][2]),mode],inputs[0][1].read_bytes(),False)
   assert result.returncode==0 and not result.stdout,(mode,result.returncode,result.stderr[-4000:]);assert not list(Path(directory).iterdir())
for _,_,key in inputs:
 if key:key.unlink()
report={'passed':True,'scope':'native_import_conversion_coordinator','synthetic_audio':True,'real_account_tested':False,'device_tested':False,'cases':rows,'negative':['output budget fails before publishing bytes','song identity mismatch fails before output'],'source_files_unchanged':True,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/apps/qqmusic/qqmusic_import.c','runtime/apps/qqmusic/qqmusic_import.h','tools/fixtures/qqmusic_codec.c']},'limits':['Callback output only; protected source/output file transactions and publication are not connected.','Application import remains blocked; no download or Sony library refresh executed.']}
if file_mode:
 report['build_manifest_sha256']=hashlib.sha256(build_path.read_bytes()).hexdigest()
 report['scope']='native_verified_source_file_to_published_tagged_mp3';report['negative']=['output limit aborts output and retains source','identity mismatch aborts output and retains source','stop retains source without output']
 report['publication_checks']=['readback SHA256 before and after rename','all ID3 and MPEG frame boundaries match conversion report','incorrect tag length, sample rate and sample count rejected','existing final file preserved','existing album publish lock refuses operation','completed MP3 moved to verified artist/album directory','published file protected from stage abort']
 report['publication_faults']=['rename error retains temporary for retry','post-rename fsync failure retains final and lock for review','post-rename stop retains final and lock for review']
 report['sources'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/apps/qqmusic/qqmusic_file_import.c','runtime/apps/qqmusic/qqmusic_file_import.h','runtime/apps/qqmusic/qqmusic_source.c','runtime/apps/qqmusic/qqmusic_output.c','runtime/apps/qqmusic/qqmusic_stage.c','runtime/apps/qqmusic/qqmusic_volume.c','runtime/apps/qqmusic/qqmusic_directory.c','runtime/apps/qqmusic/qqmusic_mp3.c','runtime/apps/qqmusic/qqmusic_mp3.h','runtime/apps/qqmusic/qqmusic_publish.c','runtime/apps/qqmusic/qqmusic_publish.h','tools/fixtures/qqmusic_file_import.c','tools/fixtures/qqmusic_volume.c']})
 report['limits']=['Actual PC files, stat and IO with synthetic mount/path mapping; no Sony FAT or USB qualification.','No-replace check requires exclusive application namespace; old-kernel rename is not atomic against noncooperating outside writers.','No actual Sony indexing, real QQ download or application import enabled.']
if network_mode:
 private.unlink();report['scope']='same_arm_process_tls_download_source_decode_tags_directory_publish';report['negative']=[];report['publication_faults']=[]
 report['sources']['tools/fixtures/qqmusic_transfer_import.h']=hashlib.sha256((ROOT/'tools/fixtures/qqmusic_transfer_import.h').read_bytes()).hexdigest()
 report['network_cases']=['fresh audio fetched over actual loopback DNS/TCP/TLS','fixed and chunked transfers','completed downloaded source used directly by conversion','no direct memory/file copy substitutes download','downloaded source retained and exact readback checked','cookie-free exact host request and loopback-only sockets']
 report['limits']=['New synthetic audio and encryption, local service and temporary CA; not QQ account evidence.','Actual ARM native IO/codecs/network with fixture mount/path mapping; no Sony FAT/Wi-Fi/USB qualification.','Runtime import UI, expiry, recovery and stock indexing are not connected.']
if job_mode:
 report['scope']='native_worker_child_executes_real_download_conversion_publish_with_checkpoints';report['publication_checks']=[]
 report['worker_checks']=['real fork with parent nonblocking poll','real native job callback and actual network/file/codecs','parent resource wiped after start','child-only inherited descriptor detach','no success before child exit and final IPC','native journal scan locates retained source and final MP3 after worker exit','native journal matches independent test audit','five ordered chained and synced checkpoint records','checkpoint provider and exclusivity provider required','unverified album artist not invented']
 report['checkpoint_failures']=['source checkpoint failure retains source and records review','output checkpoint failure retains source and complete temporary MP3','published checkpoint failure retains source and final MP3 without success']
 report['job_preflight']=['missing checkpoint provider refuses','missing or denying exclusivity provider refuses','missing recovery metadata budget refuses','expired authorization refuses before checkpoint/download','resource filename mismatch refuses','versioned exact media filename, quality, type, nonce and digests retained']
 for unused in ['tools/fixtures/qqmusic_codec.c','tools/fixtures/qqmusic_file_import.c','tools/fixtures/qqmusic_transfer_import.h']:report['sources'].pop(unused,None)
 report['sources'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/apps/qqmusic/qqmusic_job.c','runtime/apps/qqmusic/qqmusic_job.h','runtime/apps/qqmusic/qqmusic_job_record.h','runtime/apps/qqmusic/qqmusic_journal.c','runtime/apps/qqmusic/qqmusic_journal.h','runtime/apps/qqmusic/qqmusic_worker.c','runtime/apps/qqmusic/qqmusic_worker.h','tools/fixtures/qqmusic_job.c']})
 report['limits']=['Synthetic encrypted audio and loopback service with temporary CA, fixture mount/path mapping.','Native journal format/read-only scan used; exclusivity and detach adapters are test fixtures, automatic recovery actions not implemented.','No production UI/child-device detach binding, Sony FAT/power-loss/USB/Wi-Fi, real account or stock indexing qualification.']
if binding_mode:
 report['scope']='runtime_ui_native_binding_worker_job_journal_and_device_detach';report['checkpoint_failures']=[]
 report['worker_checks']=[item for item in report['worker_checks'] if item!='native journal matches independent test audit']
 report['binding_checks']=['import tap starts actual native pipeline','all export presets request MGG sources without MP3 fallback','128 and320 MP3 output bitrates verified independently in addition to192','MUSIC root and at-most-eight-level candidate path enforced','explicit denied lease prevents child start','native binding supplies journal without test audit','child clears inherited account and closes device copy','child releases font and pixels while parent keeps rendering','actual loop renders confirmed result only after reap','runtime close then binding destroy reclaims resources','repeat binding destroy preserves stdin']
 report['sources'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/apps/qqmusic/qqmusic_stock_path.c','runtime/apps/qqmusic/qqmusic_stock_path.h','runtime/apps/qqmusic/qqmusic_import_binding.c','runtime/apps/qqmusic/qqmusic_import_binding.h','runtime/apps/qqmusic/qqmusic_entry_import.c','runtime/apps/qqmusic/qqmusic_program_import.c','runtime/apps/qqmusic/qqmusic_entry.c','runtime/apps/qqmusic/qqmusic_program.c','runtime/apps/qqmusic/qqmusic_runtime.c','tools/fixtures/qqmusic_binding.h']})
 report['frames']=[]
 for raw in frames:
  values=struct.unpack('<103680H',raw.read_bytes());pixels=bytearray()
  for y in range(432):
   pixels.append(0)
   for v in values[y*240:(y+1)*240]:pixels.extend((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
  def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
  path=raw.with_suffix('.png');path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b''));report['frames'].append(str(path.relative_to(ROOT)))
 report['limits']=['Synthetic pre-authenticated selection and loopback service; QR/account service not tested here.','Actual UI/loop/worker/job/journal and common device detach execute; only bottom display IO and mount/path mapping are fixtures.','Lease callback is a test policy; physical USB exclusion, Sony FAT/power-loss/Wi-Fi and stock indexing remain unqualified.','Import-capable entry API compiled, default main remains disabled until qualified policy provided.']
if missing_cover:
 report['scope']='native_worker_download_missing_cover_fetch_convert_publish';report['checkpoint_failures']=[]
 report['network_cases']+=['exact bound album MID triggers one additional cookie-free HTTPS image request','cover response cookies ignored','APIC JPEG bytes independently equal fetched image']
 report['evidence_directory']=str(work.relative_to(ROOT))
(base/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps(report,indent=2,ensure_ascii=False))
