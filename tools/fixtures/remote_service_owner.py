"""PC-only radio owner model around the actual ARM remote service; no hardware."""
import hashlib,hmac,os,select,signal,struct,subprocess,sys,time
peer=bytes.fromhex('020102030405');key=bytes(range(1,33));cookie=bytes(range(16))
session=1234567
mode_profile=os.environ.get('XW_FIXTURE_PLAY_MODE')=='1'
all_modes=os.environ.get('XW_FIXTURE_ALL_PLAY_MODES')=='1'
library_profile=os.environ.get('XW_FIXTURE_LIBRARY')=='1'
library_replies=0
seen_modes=set()
config_in,config_out=os.pipe();owner_in,client_out=os.pipe();client_in,owner_out=os.pipe();retire_in,retire_out=os.pipe()
for fd in (config_in,client_out,client_in,retire_in,owner_in):os.set_blocking(fd,False)
config=(b'XWRUN002' if mode_profile else b'XWRUN001')+struct.pack('<QQ',23,session)+peer+b'\0\0'+key+cookie
assert len(config)==80
process=subprocess.Popen(sys.argv[1:]+['--run',str(config_in),'3',str(client_in),str(client_out),str(retire_in)],
                         pass_fds=(3,config_in,client_in,client_out,retire_in))
for fd in (3,config_in,client_in,client_out,retire_in):os.close(fd)
os.write(config_out,config);os.close(config_out)
command=b'WRC1'+struct.pack('<QIIiII',session,1,1,0,0,0) # explicit PAUSE
command+=hmac.new(key,command,hashlib.sha256).digest()[:16]
def inbound(data=None):
 data=command if data is None else data
 return struct.pack('<4sII6sBB4sII',b'XNR1',32+len(data),0,peer,2,1,b'1234',2,0)+data
library_request=bytearray(120);struct.pack_into('<4sQIIIQ',library_request,0,b'WLBQ',session,1,0,0,0)
library_request[104:]=hmac.new(key,library_request[:104],hashlib.sha256).digest()[:16]
buffer=bytearray();statuses=receipts=modes=0;paused=False;requested_stop=False;owner_eof=False
deadline=time.monotonic()+12
try:
 while time.monotonic()<deadline:
  if not select.select([owner_in],[],[],.02)[0]:
   if process.poll() is not None:break
   continue
  data=os.read(owner_in,4096)
  if not data:
   assert not buffer and requested_stop
   owner_eof=True
   os.write(retire_out,b'XRFDONE1'+cookie+struct.pack('<II',1,0));os.close(retire_out);retire_out=-1
   break
  buffer.extend(data)
  while len(buffer)>=16:
   magic,op,flags,reserved,request,bytes_=struct.unpack_from('<4sBBHII',buffer)
   assert magic==b'XNC1' and op==4 and not flags and not reserved and request and 6<=bytes_<=1476
   if len(buffer)<16+bytes_:break
   body=bytes(buffer[16:16+bytes_]);del buffer[:16+bytes_]
   assert body[:6]==peer
   payload=body[6:]
   if payload[:4]==b'WRS1':
    assert len(payload)==893 and hmac.compare_digest(hmac.new(key,payload[:877],hashlib.sha256).digest()[:16],payload[877:])
    assert struct.unpack_from('<Q',payload,4)[0]==session
    valid=struct.unpack_from('<I',payload,16)[0];state=struct.unpack_from('<I',payload,24)[0]
    assert valid&39==39 and payload[109:365].split(b'\0')[0]==b'Channel song'
    statuses+=1;paused=paused or state==2
   elif payload[:4]==b'WRA1':
    assert len(payload)==48 and hmac.compare_digest(hmac.new(key,payload[:32],hashlib.sha256).digest()[:16],payload[32:])
    assert struct.unpack_from('<QIi',payload,4)==(session,1,1)
    receipts+=1
   elif payload[:4]==b'WRM1':
    assert len(payload)==48 and hmac.compare_digest(hmac.new(key,payload[:32],hashlib.sha256).digest()[:16],payload[32:])
    valid,native,index=struct.unpack_from('<III',payload,16)
    assert struct.unpack_from('<Q',payload,4)[0]==session and valid==1
    assert native in (0,1,2,3,5) and index==(4 if native==5 else native)
    if not all_modes:assert (native,index)==(5,4)
    seen_modes.add(native)
    modes+=1
   elif payload[:4]==b'WLBR':
    assert library_profile and len(payload)==941 and hmac.compare_digest(hmac.new(key,payload[:-16],hashlib.sha256).digest()[:16],payload[-16:])
    assert struct.unpack_from('<QIi',payload,4)==(session,1,0)
    assert struct.unpack_from('<QIIII',payload,20)==(7,0,1,1,1)
    assert payload[92:157].split(b'\0')[0]==b'model:42' and payload[157:413].split(b'\0')[0]==b'Channel song'
    library_replies+=1
   else:raise AssertionError('Unexpected service payload')
   os.write(owner_out,struct.pack('<4sIII',b'XNA1',request,0,4))
   os.write(owner_out,struct.pack('<4sIII6s2xII',b'XNT1',32,request,0,peer,0,0))
   if payload[:4]==b'WRS1' and statuses==1 and not receipts:os.write(owner_out,inbound())
   if receipts==1 and payload[:4]==b'WRA1':os.write(owner_out,inbound()) # same ID: cached receipt, no second native PAUSE
   if library_profile and receipts==2 and payload[:4]==b'WRA1':os.write(owner_out,inbound(library_request))
   if library_profile and library_replies==1 and payload[:4]==b'WLBR':os.write(owner_out,inbound(library_request))
   if statuses>=2 and paused and receipts==2 and (not mode_profile or modes) and (not all_modes or len(seen_modes)==5) and (not library_profile or library_replies==2) and not requested_stop:
    requested_stop=True;process.send_signal(signal.SIGTERM)
 assert owner_eof and statuses>=2 and paused and receipts==2 and (not mode_profile or modes)
 assert process.wait(timeout=5)==0
 print('REMOTE_SERVICE_OWNER_MODEL_PASS: real ARM service, SDK status, pause, duplicate receipt, SIGTERM, client EOF and retirement receipt',flush=True)
 if mode_profile:print('REMOTE_SERVICE_MODE_MODEL_PASS: actual SDK query and authenticated native5/index4 packet',flush=True)
 if all_modes:
  assert seen_modes=={0,1,2,3,5}
  print('REMOTE_SERVICE_ALL_FIVE_MODES_PASS',flush=True)
finally:
 for fd in (owner_in,owner_out,retire_out):
  if fd>=0:os.close(fd)
 if process.poll() is None:process.kill();process.wait() # PC-only failed fixture cleanup
