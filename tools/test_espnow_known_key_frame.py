"""Synthetic diagnostic classifier tests; never represents a captured RF vector."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile
from Crypto.Cipher import AES
from espnow_known_key_frame import ROOT,PROFILES,analyze,decode_body
OUT=ROOT/'work/espnow-known-key-frame-tests';OUT.mkdir(parents=True,exist_ok=True)
key=bytes(range(16));header=bytes.fromhex('d040000002060708090a020102030405ffffffffffff0000');pn=0x010203040506;iv=bytes([6,5,0,0x20,4,3,2,1]);body=bytes.fromhex('7f18fe3401020304dd0818fe34040100ff80')
def seal(profile,plain=body):
    name,prefix,mask=profile;fc=int.from_bytes(header[:2],'little');aad=(fc&~0x70 if mask else fc).to_bytes(2,'little')+header[4:22]+bytes(2);cipher=AES.new(key,AES.MODE_CCM,nonce=bytes([prefix])+header[10:16]+pn.to_bytes(6,'big'),mac_len=8);cipher.update(aad);data,tag=cipher.encrypt_and_digest(plain);return header+iv+data+tag
rows=[]
for profile in PROFILES:
    frame=seal(profile);r,p=analyze(frame,key);assert r['matched_profiles']==[profile[0]] and p[profile[0]]==bytes.fromhex('00ff80');rows.append({'synthetic_profile':profile[0],'only_expected_profile_authenticated':True})
    altered=bytearray(frame);altered[-1]^=1;r,p=analyze(bytes(altered),key);assert not p and not r['matched_profiles'] and not any(c['mic_authenticated'] for c in r['candidates'])
    r,p=analyze(frame,bytes([0xff])*16);assert not p
    for version,length in ((1,0),(1,250),(2,0),(2,251),(2,1470)):
        payload=bytes((i*17)&255 for i in range(length));parts=[payload[i:i+250] for i in range(0,length,250)] or [b''];encoded=bytes.fromhex('7f18fe3401020304')
        for i,part in enumerate(parts):encoded+=bytes([221,len(part)+5])+bytes.fromhex('18fe3404')+bytes([version|(16 if i+1<len(parts) else 0)])+part
        result,opened=analyze(seal(profile,encoded),key);assert result['matched_profiles']==[profile[0]] and opened[profile[0]]==payload and result['candidates'][PROFILES.index(profile)]['version']==version
r,p=analyze(seal(PROFILES[0],body[:8]+b'\x00'+body[9:]),key);assert not p and any(c.get('mic_authenticated') and c.get('body_valid') is False for c in r['candidates'])
try:analyze(b'\0'*55,key)
except ValueError:pass
else:raise AssertionError('invalid header accepted')
with tempfile.TemporaryDirectory(dir=OUT) as temporary:
    folder=Path(temporary);source=folder/'frame.bin';secret=folder/'lmk.private';target=folder/'payload.bin';source.write_bytes(seal(PROFILES[2]));secret.write_bytes(key)
    command=[sys.executable,str(ROOT/'tools/espnow_known_key_frame.py'),'--frame',str(source),'--lmk-file',str(secret),'--output-payload',str(target)]
    run=subprocess.run(command,capture_output=True,text=True,check=True);report=json.loads(run.stdout);assert target.read_bytes()==bytes.fromhex('00ff80') and report['matched_profiles']==[PROFILES[2][0]] and key.hex() not in run.stdout
    # Explicit FCS stripping and hex-file input, with no key on the command line.
    hex_input=folder/'frame.hex';hex_input.write_text((source.read_bytes()+bytes(4)).hex());secret.write_text(key.hex());run=subprocess.run([sys.executable,str(ROOT/'tools/espnow_known_key_frame.py'),'--frame',str(hex_input),'--hex','--fcs','--lmk-file',str(secret)],capture_output=True,text=True,check=True);assert json.loads(run.stdout)['matched_profiles']==[PROFILES[2][0]]
    target.unlink();altered=bytearray(source.read_bytes());altered[-1]^=1;source.write_bytes(altered);run=subprocess.run(command,capture_output=True,text=True);assert run.returncode==64 and not target.exists() and key.hex() not in run.stdout
report={'passed':True,'synthetic_only':True,'cases':rows,'v1_v2_boundary_cases_per_profile':5,'binary_and_empty_payloads':True,'explicit_hex_fcs_input':True,'bad_mic_wrong_key_rejected':True,'authenticated_bad_body_not_published':True,'cli_key_file_not_echoed':True,'payload_output_only_after_authentication':True,'device_accessed':False,'physical_wire_profile_proven':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/espnow_known_key_frame.py','tools/test_espnow_known_key_frame.py']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
