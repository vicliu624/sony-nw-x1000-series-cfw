"""Whole native secure endpoint and real host journal bridged to radio ARM code.

All PC-only; modeled DMA/ROM/completion producer, no physical ESP-NOW claim.
"""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,select,struct,subprocess,sys
from Crypto.Cipher import AES
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R6,UC_ARM_REG_R4
from app_registry import ROOT
ARM='--arm' in sys.argv
DRIVER='--driver' in sys.argv
if DRIVER and '--arm' not in sys.argv:raise ValueError('iwreq ABI driver test requires ARM926')
GUARD='--guard' in sys.argv or DRIVER
if GUARD and '--candidate' not in sys.argv:raise ValueError('guard test requires actual candidate profile')
OUT=ROOT/('work/espnow-secure-chain-arm' if ARM else 'work/espnow-secure-chain');OUT.mkdir(exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):radio=runpy.run_path(str(ROOT/'tools/test_radio_completion_hook.py'))
cpu,put,word,call,free_count,command=[radio[n] for n in ('cpu','put','word','call','free_count','command')]
symbols=radio['symbols'];tx=symbols['xnow_full_tx'];rx=symbols['xnow_full_rx'];completion=symbols['xnow_tx_completion'];request=radio['env']['request'];radio['env']['env']['queue_result'][0]=0
candidate_identity=None
if '--candidate' in sys.argv:
 from marvell_firmware import parse
 from prepare_espnow_radio_candidate import memory
 candidate=Path(sys.argv[sys.argv.index('--candidate')+1]).resolve();manifest_path=candidate.parent.parent/'manifest.json'
 manifest=json.loads(manifest_path.read_text());blob=candidate.read_bytes();assert hashlib.sha256(blob).hexdigest()==manifest['candidate_sha256']
 loaded=memory(parse(blob))
 for name,a in (('xnow_full_tx',tx),('xnow_full_rx',rx),('xnow_tx_completion',completion)):assert manifest['controls'][name]['address']==a
 for name,a in manifest['entries'].items():assert symbols[name]==a
 for a,data in radio['sections']:
  if a<tx and a<rx and a<completion:assert bytes(loaded[a+i] for i in range(len(data)))==data
 for section in manifest['immutable_segments']:
  assert hashlib.sha256(bytes(loaded[section['address']+i] for i in range(section['bytes']))).hexdigest()==section['sha256']
 for record in parse(blob):
  if record.command==1:cpu.mem_write(record.address,record.data)
 cpu.ctl_remove_cache(0,0x20000);cpu.ctl_remove_cache(0xc0001000,0xc0018000)
 candidate_identity={'sha256':manifest['candidate_sha256'],'occupied_span_bytes':manifest['occupied_span_bytes'],'radio_image_loaded_in_unicorn':True}
 if GUARD:cpu.mem_write(0x17320,bytes(32)) # modeled original startup-table reclamation
 if DRIVER:
  cpu.mem_write(0xc000785c,bytes.fromhex('021122334455'));put(0x04001bc4,0xc000785c) # fixed original BSS MAC slot

node=call(0xc000465c,word(0xc000ee4c));ctx=word(node+20);frame=word(node+8);put(ctx+16,frame)
ring=0x201000;config=0xc000dc8c+4*32
for offset,value in ((0,ring),(8,4096),(16,0x200700),(20,0x200704),(24,0x7b4)):put(config+offset,value)
B=ROOT/'work/external-tls-probe/bearssl-0.6';archive=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'
assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
sources=['tools/fixtures/xnow_secure_chain.c',*['runtime/platform/espnow/'+n for n in ('xnow_endpoint.c','xnow_endpoint_security.c','xnow_peer.c','xnow_full.c','xnow_security.c','xnow_ccmp.c','xnow_pn.c','xnow_pn_file.c','xnow_wire.c','xnow_keyring.c','xnow_keywrap.c')],'runtime/native/sha256.c']
extra=[]
if GUARD:
 from generate_espnow_full_profile import render
 (OUT/'full_radio_profile.h').write_text(render(candidate.parent.parent));sources.append('runtime/platform/espnow/xnow_full_guard.c');extra=['-DXNOW_CHAIN_GUARD','-I',str(OUT),'-I',str(ROOT/'runtime/platform/espnow')]
if DRIVER:
 sources.append('runtime/platform/espnow/xnow_sd8686_full.c');extra+=['-DXNOW_CHAIN_DRIVER','-Wl,--wrap=fopen','-Wl,--wrap=fopen64','-Wl,--wrap=socket','-Wl,--wrap=close','-Wl,--wrap=ioctl']
 (OUT/'driver-info.txt').write_text('sd8686-9.70.3.p32-26409.p51-(FP4)\n')
exe=OUT/('chain.arm' if ARM else 'chain.host')
if ARM:
 lib=ROOT/'work/arm-signal-tests/lib';archive=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
 for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
 sources+=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I',str(B/'inc'),*extra,*sources,str(archive),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(exe)],cwd=ROOT,check=True)
 launch=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(exe)]
else:
 subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I',str(B/'inc'),*extra,*sources,str(archive),'-o',str(exe)],cwd=ROOT,check=True)
 launch=[str(exe)]
err=(OUT/'stderr.log').open('w');process=subprocess.Popen([*launch,hex(tx),hex(rx),hex(completion),str(OUT)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
counts={'R':0,'W':0,'T':0,'I':0,'M':0,'J':0};pns=[];rejected_pns=[];passed=False
try:
 while True:
  ready,_,_=select.select([process.stdout],[],[],30)
  if not ready:raise RuntimeError('Live integration driver did not issue the next request within30 seconds')
  line=process.stdout.readline()
  if not line:break
  line=line.strip()
  if line.startswith('PASS '):passed=True;break
  fields=line.split();kind=fields[0];assert kind in counts;counts[kind]+=1
  if kind=='R':
   address=int(fields[1],16);cpu.mem_write(request,struct.pack('<4H',0x86,20,0x55aa,0)+struct.pack('<HHII',0,0,address,0));cpu.mem_write(0xc000edf4,b'\0');cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001);cpu.emu_start(0x8079,0x9b40,count=30000)
   assert cpu.reg_read(UC_ARM_REG_PC)==0x9a46 and cpu.reg_read(UC_ARM_REG_R6)==0
   response='0 '+format(word(request+16),'08x')
  elif kind=='W':command(int(fields[1],16),int(fields[2],16));response='0'
  elif kind=='M':
   value=word(0xc000a190);put(0xc000a190,value^1);response='0'
  elif kind in ('T','J'):
   pointer=word(completion);assert pointer and word(tx+16)==4
   body_bytes=struct.unpack('<H',cpu.mem_read(pointer,2))[0];header=bytes(cpu.mem_read(pointer+2,24));body=bytes(cpu.mem_read(pointer+32,body_bytes));assert body_bytes==1536 and header[1]&64
   iv=body[:8];pn=iv[0]|iv[1]<<8|int.from_bytes(iv[4:8],'little')<<16;(pns if kind=='T' else rejected_pns).append(pn)
   nonce=b'\x10'+header[10:16]+pn.to_bytes(6,'big');aad=bytes((header[0],(header[1]&0xc7)|64))+header[4:22]+bytes((header[22]&15,0))
   aes=AES.new(bytes(range(16)),AES.MODE_CCM,nonce=nonce,mac_len=8);aes.update(aad);plain=aes.decrypt_and_verify(body[8:-8],body[-8:]);assert plain[:4]==b'\x7f\x18\xfe\x34'
   offset=8;payload=b''
   while offset<len(plain):
    assert plain[offset]==221;length=plain[offset+1];assert plain[offset+2:offset+6]==b'\x18\xfe\x34\x04';payload+=plain[offset+7:offset+2+length];offset+=2+length
   assert payload==bytes((i*17+7)&255 for i in range(1470))
   if kind=='T':radio['finish'](pointer,0,0)
   else:
    def stop_rejected(u,pc,size,unused):
     if pc==0x9eba:u.emu_stop()
    hook=cpu.hook_add(UC_HOOK_CODE,stop_rejected)
    cpu.reg_write(UC_ARM_REG_R4,pointer);cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
    cpu.emu_start(0x9eb5,0x9ebc,count=30000);cpu.hook_del(hook)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x9eba and word(completion+12)==2
   assert free_count()==3;response='0'

  else:
   incoming=bytes.fromhex(fields[1]);body=incoming[24:];packet=bytearray(32+len(body));struct.pack_into('<H',packet,0,len(body)+48);packet[2:26]=incoming[:24];packet[32:]=body
   record=bytearray(16)+packet;struct.pack_into('<H',record,2,0xbeef);cpu.mem_write(ring,bytes(record));put(0x200704,(len(record)+3)&~3)
   assert call(0x4b9c,4,0,ctx)==len(body)+48 and call(symbols['xnow_radio_full_receive'],frame,ctx)==0;response='0'
  process.stdin.write(response+'\n');process.stdin.flush()
 process.stdin.close();code=process.wait(timeout=15);assert code==0 and passed,(code,(OUT/'stderr.log').read_text())
finally:
 if process.poll() is None:process.terminate();process.wait(timeout=10)
 err.close()
assert pns==[1,1025] and rejected_pns==[1026] and free_count()==3 and word(rx+56)==0
assert call(0x1360,frame)==0
headers=['runtime/platform/espnow/'+n for n in ('xnow_endpoint.h','xnow_endpoint_security.h','xnow_peer.h','xnow_full.h','xnow_security.h','xnow_ccmp.h','xnow_pn.h','xnow_pn_file.h','xnow_wire.h','xnow_keyring.h','xnow_keywrap.h','xnow_full_guard.h','xnow_sd8686_full.h')]
report={'passed':True,'candidate_identity':candidate_identity,'native_endpoint_crypto_and_real_host_journal':True,'host_asan_ubsan':not ARM,'arm926_original_libc':ARM,'original_command_dispatch_and_compiled_radio':True,'independent_tx_aesccm_authentication':True,'transmitted_pns_across_endpoint_restart':pns,'pre_mac_rejected_pns':rejected_pns,'original_task5_rejection_drains_stop':True,'maximum_payload':1470,'pmk_rotation_preserves_lmk_and_pn_namespace':True,'bounded_guard_and_lease_invalidation':GUARD,'linux_iwreq_ioctl_transport_mocked':DRIVER,'probe_does_not_enable_rx_channel_set_readback_before_open':DRIVER,'reclaimed_scatter_excluded_from_runtime_identity':GUARD,'rx_capacity_retry_and_persistent_replay_rejection':True,'mic_failure_then_valid_same_pn_accepted':True,'stop_workspace_erased_and_pool_restored':True,'transactions':counts,'native_side_is_host_not_arm':not ARM,'hardware_dma_rom_queue_completion_and_scheduling_modeled':True,'physical_interoperability':False,'device_accessed':False,'radio_reserved_bytes':radio['report']['combined_reserved_bytes'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*headers,'tools/test_xnow_secure_chain.py']},'radio_source_hashes':radio['report']['source_hashes'],'bearssl_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
