"""Native full C backend -> original host dispatcher -> compiled radio code.

Synthetic ROM queues/RX DMA/completion producer; no device or RF acceptance.
"""
from Crypto.Cipher import AES
from pathlib import Path
import contextlib,ctypes,hashlib,io,json,runpy,struct,subprocess
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R6
from app_registry import ROOT
OUT=ROOT/'work/espnow-full-integration';OUT.mkdir(exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):radio=runpy.run_path(str(ROOT/'tools/test_radio_completion_hook.py'))
cpu,put,word,call,free_count,command=[radio[n] for n in ('cpu','put','word','call','free_count','command')]
symbols=radio['symbols'];tx=symbols['xnow_full_tx'];rx=symbols['xnow_full_rx'];completion=symbols['xnow_tx_completion']
request=radio['env']['request'];radio['env']['env']['queue_result'][0]=0
shared=OUT/'backend.so';sources=['runtime/platform/espnow/xnow_full.c','runtime/platform/espnow/xnow_wire.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',*sources,'-o',str(shared)],cwd=ROOT,check=True)
lib=ctypes.CDLL(str(shared));U=ctypes.c_uint32;P=ctypes.c_void_p
READ=ctypes.CFUNCTYPE(ctypes.c_int,P,U,ctypes.POINTER(U));WRITE=ctypes.CFUNCTYPE(ctypes.c_int,P,U,U)
class IO(ctypes.Structure):_fields_=[('context',P),('read',READ),('write',WRITE)]
class Layout(ctypes.Structure):_fields_=[('tx',U),('rx',U),('completion',U)]
class Spans(ctypes.Structure):_fields_=[('context',P),('read',P),('write',P)]
class Full(ctypes.Structure):_fields_=[('io',IO),('layout',Layout),('sequence',U),('inflight',U),('fault',ctypes.c_int),('stopping',ctypes.c_int),('spans',Spans)]
class Result(ctypes.Structure):_fields_=[('token',U),('status',U),('raw',U)]
class Wire(ctypes.Structure):_fields_=[('version',ctypes.c_uint8),('random',ctypes.c_uint8*4),('elements',ctypes.c_uint16),('length',ctypes.c_size_t)]
class Received(ctypes.Structure):_fields_=[('source',ctypes.c_uint8*6),('info',Wire),('flags',U)]
lib.xnow_full_open.argtypes=[ctypes.POINTER(Full),ctypes.POINTER(IO),ctypes.POINTER(Layout)]
lib.xnow_full_send.argtypes=[ctypes.POINTER(Full),P,ctypes.c_uint,P,P,ctypes.c_size_t]
lib.xnow_full_send_protected.argtypes=[ctypes.POINTER(Full),P,P,ctypes.c_size_t]
lib.xnow_full_tx_result.argtypes=[ctypes.POINTER(Full),ctypes.POINTER(Result)]
lib.xnow_full_receive_action.argtypes=[ctypes.POINTER(Full),P,P,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
lib.xnow_full_receive.argtypes=[ctypes.POINTER(Full),P,ctypes.c_size_t,ctypes.POINTER(Received)]
lib.xnow_full_stop_step.argtypes=[ctypes.POINTER(Full)]
errors=[];counts=[0,0];fail_upload=[False];ambiguous=[False]
def read(context,address,out):
 try:
  cpu.mem_write(request,struct.pack('<4H',0x86,20,0x55aa,0)+struct.pack('<HHII',0,0,address,0))
  cpu.mem_write(0xc000edf4,b'\0');cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
  cpu.emu_start(0x8079,0x9b40,count=30000)
  assert cpu.reg_read(UC_ARM_REG_PC)==0x9a46 and cpu.reg_read(UC_ARM_REG_R6)==0
  out[0]=word(request+16);counts[0]+=1;return 0
 except Exception as error:errors.append(repr(error));return -1
def write(context,address,value):
 try:
  if fail_upload[0] and address<0xc000a190 and 0xc0008b4c<=address:
   fail_upload[0]=False;return -1
  command(address,value);counts[1]+=1
  if ambiguous[0] and address==tx+4 and word(tx+16)==2:ambiguous[0]=False;return -1
  return 0
 except Exception as error:errors.append(repr(error));return -1
callbacks=(READ(read),WRITE(write));io_api=IO(None,*callbacks);layout=Layout(tx,rx,completion);native=Full()
assert lib.xnow_full_open(ctypes.byref(native),ctypes.byref(io_api),ctypes.byref(layout))==0
# Initialize the actual singleton work allocation and original RX ring reader.
node=call(0xc000465c,word(0xc000ee4c));ctx=word(node+20);frame=word(node+8);put(ctx+16,frame)
ring=0x201000;config=0xc000dc8c+4*32
for offset,value in ((0,ring),(8,4096),(16,0x200700),(20,0x200704),(24,0x7b4)):put(config+offset,value)
def inject(body,protected=False):
 packet=bytearray(32+len(body));struct.pack_into('<H',packet,0,len(body)+48);packet[2]=0xd0;packet[3]=0x40 if protected else 0
 packet[6:12]=bytes.fromhex('021122334455');packet[12:18]=bytes.fromhex('0266778899aa');packet[18:24]=b'\xff'*6;packet[32:]=body
 record=bytearray(16)+packet;struct.pack_into('<H',record,2,0xbeef);cpu.mem_write(ring,bytes(record));put(0x200704,(len(record)+3)&~3)
 assert call(0x4b9c,4,0,ctx)==len(body)+48
 assert call(symbols['xnow_radio_full_receive'],frame,ctx)==0
nonce=ctypes.create_string_buffer(b'1234');destination=ctypes.create_string_buffer(bytes.fromhex('0266778899aa'));cases=[]
for version,length in ((1,0),(1,1),(1,250),(2,251),(2,1470)):
 data=bytes((i*37+length)&255 for i in range(length));payload=ctypes.create_string_buffer(data)
 assert lib.xnow_full_send(ctypes.byref(native),destination,version,nonce,payload,length)==0
 packet=word(completion);assert packet and free_count()==2
 n=struct.unpack('<H',cpu.mem_read(packet,2))[0];body=bytes(cpu.mem_read(packet+32,n))
 assert lib.xnow_full_tx_result(ctypes.byref(native),ctypes.byref(Result()))==2
 inject(body);assert free_count()==1
 # Actual compiled completion hook calls original free; native acknowledges token.
 radio['finish'](packet,length&1,0x00070302);result=Result()
 assert lib.xnow_full_tx_result(ctypes.byref(native),ctypes.byref(result))==0 and result.status==length&1
 out=ctypes.create_string_buffer(1470);info=Received()
 assert lib.xnow_full_receive(ctypes.byref(native),out,1470,ctypes.byref(info))==0
 assert info.info.length==length and out.raw[:length]==data and bytes(info.source)==bytes.fromhex('0266778899aa') and free_count()==3
 cases.append({'version':version,'payload_bytes':length,'native_to_radio_words_and_original_release':True})
# Independently AES-CCM-encrypted frames traverse native/compiled radio TX.
protected_cases=[]
for version,length in ((1,250),(2,1470)):
 data=bytes((i*31+7)&255 for i in range(length));clear=b'\x7f\x18\xfe\x34'+b'1234'
 for at in range(0,length,250):
  chunk=data[at:at+250];more=version==2 and at+len(chunk)<length
  clear+=bytes((221,5+len(chunk)))+b'\x18\xfe\x34\x04'+bytes((version|(16 if more else 0),))+chunk
 header=bytes.fromhex('d04000000266778899aa021122334455ffffffffffff0000');key=bytes(range(16));pn=0x010203040506
 aes=AES.new(key,AES.MODE_CCM,nonce=b'\x10'+header[10:16]+pn.to_bytes(6,'big'),mac_len=8)
 aad=header[:2]+header[4:22]+b'\0\0';aes.update(aad);ciphertext,tag=aes.encrypt_and_digest(clear)
 raw_pn=pn.to_bytes(6,'little');iv=raw_pn[:2]+b'\0\x20'+raw_pn[2:];encrypted=header+iv+ciphertext+tag
 local=ctypes.create_string_buffer(header[10:16]);wire=ctypes.create_string_buffer(encrypted)
 before_count=len(radio['env']['env']['queued'])
 wrong_local=ctypes.create_string_buffer(bytes.fromhex('021111111111'))
 assert lib.xnow_full_send_protected(ctypes.byref(native),wrong_local,wire,len(encrypted))==-3
 invalid=bytearray(encrypted);invalid[4]=255
 assert lib.xnow_full_send_protected(ctypes.byref(native),local,ctypes.create_string_buffer(bytes(invalid)),len(invalid))==-3
 invalid=bytearray(encrypted);invalid[26]=1
 assert lib.xnow_full_send_protected(ctypes.byref(native),local,ctypes.create_string_buffer(bytes(invalid)),len(invalid))==-3
 assert len(radio['env']['env']['queued'])==before_count and free_count()==3
 assert lib.xnow_full_send_protected(ctypes.byref(native),local,wire,len(encrypted))==0
 pointer=word(completion);assert pointer and cpu.mem_read(pointer+3,1)[0]&64
 assert bytes(cpu.mem_read(pointer+32,len(encrypted)-24))==encrypted[24:]
 assert bytes(cpu.mem_read(pointer+6,18))==header[4:22]
 assert struct.unpack('<H',cpu.mem_read(pointer,2))[0]==len(encrypted)-24
 radio['finish'](pointer,0,0);result=Result();assert lib.xnow_full_tx_result(ctypes.byref(native),ctypes.byref(result))==0 and free_count()==3
 protected_cases.append({'application_bytes':length,'protected_body_bytes':len(encrypted)-24,'source_destination_and_ciphertext_retained':True})
 # Reverse source/destination for a real-layout protected RX frame.
 incoming=header[:4]+header[10:16]+header[4:10]+header[16:]
 incoming_nonce=b'\x10'+incoming[10:16]+pn.to_bytes(6,'big')
 incoming_aad=incoming[:2]+incoming[4:22]+b'\0\0'
 aes=AES.new(key,AES.MODE_CCM,nonce=incoming_nonce,mac_len=8);aes.update(incoming_aad);crypt,tag=aes.encrypt_and_digest(clear)
 inject(iv+crypt+tag,True)
 assert free_count()==2
 info=Received();plain_out=ctypes.create_string_buffer(1470)
 assert lib.xnow_full_receive(ctypes.byref(native),plain_out,1470,ctypes.byref(info))==3 and free_count()==2
 raw=ctypes.create_string_buffer(1560);written=ctypes.c_size_t(999);verified_local=ctypes.create_string_buffer(incoming[4:10])
 assert lib.xnow_full_receive_action(ctypes.byref(native),verified_local,raw,1,ctypes.byref(written))==-3 and written.value==999 and free_count()==2
 assert lib.xnow_full_receive_action(ctypes.byref(native),verified_local,raw,1560,ctypes.byref(written))==0
 canonical=raw.raw[:written.value];assert canonical==incoming+iv+crypt+tag and free_count()==3
 aes=AES.new(key,AES.MODE_CCM,nonce=incoming_nonce,mac_len=8);aes.update(incoming_aad)
 assert aes.decrypt_and_verify(canonical[32:-8],canonical[-8:])==clear
 protected_cases[-1]['original_ring_protected_rx_and_canonical_native_read']=True

# Upload failure aborts a real original allocation, no pending completion.
fail_upload[0]=True
assert lib.xnow_full_send(ctypes.byref(native),destination,1,nonce,b'x',1)==-1
assert not native.fault and free_count()==3 and word(completion)==0
# Actual queue rejection is handled by original d800, no double release.
radio['env']['env']['queue_result'][0]=1
assert lib.xnow_full_send(ctypes.byref(native),destination,1,nonce,b'x',1)==-5 and free_count()==3
radio['env']['env']['queue_result'][0]=0
# Drain actual RX queue and wait for an actual submitted packet on stop.
assert lib.xnow_full_send(ctypes.byref(native),destination,1,nonce,b'x',1)==0
pending=word(completion);body=bytes(cpu.mem_read(pending+32,16));inject(body)
assert lib.xnow_full_stop_step(ctypes.byref(native))==2 and free_count()==2
assert lib.xnow_full_stop_step(ctypes.byref(native))==2 and word(rx+56)==0
radio['finish'](pending,0,0);assert lib.xnow_full_stop_step(ctypes.byref(native))==0 and free_count()==3
# Ambiguous submit retains radio ownership and poisons native without retry/free.
assert lib.xnow_full_open(ctypes.byref(native),ctypes.byref(io_api),ctypes.byref(layout))==0
ambiguous[0]=True
assert lib.xnow_full_send(ctypes.byref(native),destination,1,nonce,b'x',1)==-4 and native.fault
pending=word(completion);assert pending and free_count()==2
before=len(radio['env']['env']['queued'])
assert lib.xnow_full_send(ctypes.byref(native),destination,1,nonce,b'x',1)==-4
assert lib.xnow_full_stop_step(ctypes.byref(native))==-4 and len(radio['env']['env']['queued'])==before
radio['finish'](pending,1,0) # fixture cleanup, not a native unsafe retry/reset
assert free_count()==3 and not errors
assert call(0x1360,frame)==0
report={'passed':True,'cases':cases,'protected_cases':protected_cases,'all_word_transactions_execute_original_dispatcher':True,'original_rx_ring_and_compiled_rx_executed':True,'actual_original_packet_pool_and_release':True,'upload_abort_and_queue_rejection_release':True,'stop_drain_and_pending_completion':True,'ambiguous_commit_no_retry_or_force_free':True,'callback_errors':errors,'read_commands':counts[0],'write_commands':counts[1],'hardware_dma_queue_completion_and_scheduling_modeled':True,'physical_interoperability':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_full.h','tools/test_xnow_full_integration.py']},'radio_source_hashes':radio['report']['source_hashes']}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
