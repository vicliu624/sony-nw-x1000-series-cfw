"""Private RF vector through actual secure endpoint; no live radio operations."""
from pathlib import Path
import hashlib,json,subprocess
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/physical-ccmp-profile';capture=ROOT/'work/autonomous-espnow-test/live/rx01'
assert (OUT/'physical_vector.private.h').is_file(),'Run test_physical_ccmp_profile.py first'
wire_key=AES.new((capture/'pmk.private.bin').read_bytes(),AES.MODE_ECB).encrypt((capture/'lmk.private.bin').read_bytes())
sources=['tools/fixtures/physical_endpoint_profile.c']+['runtime/platform/espnow/'+n+'.c' for n in ('xnow_endpoint','xnow_endpoint_security','xnow_peer','xnow_full','xnow_security','xnow_ccmp','xnow_pn','xnow_wire')]+['runtime/native/sha256.c']
bear=ROOT/'work/external-tls-probe/bearssl-0.6';lib=ROOT/'work/arm-signal-tests/lib';flags=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(OUT),'-I'+str(bear/'inc')]
rows=[]
for name in ('host','arm'):
 target=OUT/('endpoint.'+name)
 if name=='host':command=['gcc',*flags,'-fsanitize=address,undefined','-g',*sources,str(ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'),'-o',str(target)]
 else:command=['arm-linux-gnueabi-gcc',*flags,'-Os','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(target)]
 subprocess.run(command,cwd=ROOT,check=True);run=subprocess.run([str(target)] if name=='host' else ['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(target)],capture_output=True,text=True,check=True,timeout=20)
 lines=run.stdout.splitlines();frame=bytes.fromhex(lines[lines.index('ESP_TX_FRAME')+1]);iv=frame[24:32];pn=int.from_bytes(iv[:2]+iv[4:],'little')
 aad=bytes([frame[0]&0x8f,(frame[1]&0xc7)|0x40])+frame[4:22]+bytes(2)
 cipher=AES.new(wire_key,AES.MODE_CCM,nonce=b'\0'+frame[10:16]+pn.to_bytes(6,'big'),mac_len=8);cipher.update(aad);plain=cipher.decrypt_and_verify(frame[32:-8],frame[-8:])
 import sys
 sys.path.insert(0,str(ROOT/'tools'));from espnow_known_key_frame import decode_body
 version,payload=decode_body(plain);assert version==2 and payload==bytes((i*19)&255 for i in range(1470)) and iv[3]==0xe0
 rows.append({'target':name,'physical_capture_rx_authenticated':True,'encrypted_tx_bytes':len(payload),'independent_AES_CCM_tx_verified':True,'tx_sha256':hashlib.sha256(frame).hexdigest(),'pn':pn})
report={'passed':True,'cases':rows,'live_reverse_encrypted_RF_tested':False,'storage_and_radio_transport_modeled':True,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_security.h','runtime/platform/espnow/xnow_endpoint_security.h']}}
(OUT/'endpoint-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
