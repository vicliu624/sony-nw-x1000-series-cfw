"""Execute real bench C with mocked IDF boundaries; never connects to hardware."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
from Crypto.Cipher import AES
from espnow_known_key_frame import PROFILES,analyze
from analyze_espnow_capture_log import analyze_lines
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/espnow-standard-peer-tests';OUT.mkdir(parents=True,exist_ok=True)
include=OUT/'include';include.mkdir(exist_ok=True)
for name in ['esp_now.h','esp_wifi.h','esp_event.h','esp_netif.h','esp_idf_version.h','driver/usb_serial_jtag.h','freertos/FreeRTOS.h','freertos/queue.h']:
    p=include/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* Host IDF boundary supplied by fixture. */\n')
sources=['tools/fixtures/standard_peer.c','tools/fixtures/standard_peer_stubs.h','runtime/platform/espnow/standard-peer/main/peer.c']
binary=OUT/'peer-test'
subprocess.run(['gcc','-std=c99','-D_POSIX_C_SOURCE=200809L','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-g','-I',str(include),sources[0],'-o',str(binary)],cwd=ROOT,check=True)
p=subprocess.run([str(binary)],cwd=ROOT,capture_output=True,text=True,timeout=20)
assert p.returncode==0,p.stderr
capture_cases=[]
with tempfile.TemporaryDirectory(dir=OUT) as temporary:
    frame_file=Path(temporary)/'synthetic-frame.bin'
    header=bytes.fromhex('d040000002060708090a020000000000ffffffffffff0000')
    key=bytes(range(16));pn=0x010203040506;iv=bytes([6,5,0,0x20,4,3,2,1])
    for name,prefix,mask in PROFILES:
        for version,length in ((1,0),(1,250),(2,0),(2,251),(2,1470)):
            payload=bytes((i*17)&255 for i in range(length));chunks=[payload[i:i+250] for i in range(0,length,250)] or [b'']
            body=bytes.fromhex('7f18fe3401020304')
            for i,chunk in enumerate(chunks):body+=bytes([221,len(chunk)+5])+bytes.fromhex('18fe3404')+bytes([version|(16 if i+1<len(chunks) else 0)])+chunk
            fc=int.from_bytes(header[:2],'little');aad=(fc&~0x70 if mask else fc).to_bytes(2,'little')+header[4:22]+bytes(2)
            cipher=AES.new(key,AES.MODE_CCM,nonce=bytes([prefix])+header[10:16]+pn.to_bytes(6,'big'),mac_len=8);cipher.update(aad)
            ciphertext,mic=cipher.encrypt_and_digest(body);frame=header+iv+ciphertext+mic
            frame_file.write_bytes(frame+bytes(4)) # Synthetic FCS; no RF/CRC claim.
            run=subprocess.run([str(binary),str(frame_file)],capture_output=True,text=True,check=True,timeout=20)
            lines=[line for line in run.stdout.splitlines() if line.startswith('CAPTURE ')]
            assert len(lines)==1;fields=dict(item.split('=',1) for item in lines[0].split()[1:]);retained=bytes.fromhex(fields['frame'])
            assert fields['fcs']=='1' and int(fields['length'])==len(retained) and retained==frame+bytes(4)
            result,opened=analyze(retained[:-4],key);assert result['matched_profiles']==[name] and opened[name]==payload
            native_line=f'RAW_ACTION fcs=0 bytes={len(frame)} hex={frame.hex()}'
            native_result=analyze_lines([native_line],key);assert native_result['authenticated_records']==1 and native_result['records'][0]['canonical_native_header']
            log_result=analyze_lines(lines+lines,key)
            assert log_result['authenticated_records']==2 and not log_result['authenticated_pn_ciphertext_conflicts'] and log_result['records'][1]['duplicate_ciphertext']
            bad_record='CAPTURE fcs=1 length=1 frame=00'
            assert analyze_lines([bad_record],key)['invalid_records']==1
            changed=bytearray(body);changed[4]^=1
            second=AES.new(key,AES.MODE_CCM,nonce=bytes([prefix])+header[10:16]+pn.to_bytes(6,'big'),mac_len=8);second.update(aad)
            other,tag=second.encrypt_and_digest(bytes(changed));conflicting=header+iv+other+tag+bytes(4)
            conflict_line=f'CAPTURE fcs=1 length={len(conflicting)} frame={conflicting.hex()}'
            assert len(analyze_lines(lines+[conflict_line],key)['authenticated_pn_ciphertext_conflicts'])==1
            altered=bytearray(retained[:-4]);altered[-1]^=1;assert not analyze(bytes(altered),key)[1]
            capture_cases.append({'profile':name,'version':version,'payload_bytes':length,'exact_capture_and_authenticated_payload':True})
report={'passed':p.returncode==0,'stdout':p.stdout,'stderr':p.stderr,'device_accessed':False,'idf_radio_mocked':True,'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,'tools/test_standard_espnow_peer.py','tools/espnow_known_key_frame.py','tools/analyze_espnow_capture_log.py']}}
report.update(capture_classifier_cases=capture_cases,synthetic_capture_only=True,physical_ciphertext_preservation_proven=False)
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(p.returncode)
