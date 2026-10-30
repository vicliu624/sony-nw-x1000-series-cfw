"""PC-only authenticated analysis of owned ESP-NOW captures with an explicit LMK.

Candidate profiles are hypotheses, never live fallback or a wire compatibility
claim. Every candidate requires an8-byte MIC plus complete ESP-NOW body decode.
No key search, network/device access or unauthenticated plaintext output.
"""
from pathlib import Path
import argparse,hashlib,json
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[1]
PROFILES=(('management',0x10,False),('espnow-nonce0-management-aad',0,False),('espnow-nonce0-legacy-aad',0,True))
OUI=bytes.fromhex('18fe34')
def decode_body(body):
    if len(body)<15 or len(body)>1520 or body[:4]!=b'\x7f'+OUI:raise ValueError('invalid ESP-NOW body')
    offset=8;version=None;chunks=[]
    while offset<len(body):
        if len(body)-offset<7 or body[offset]!=221:raise ValueError('invalid vendor element')
        length=body[offset+1];flags=body[offset+6];current=flags&15;more=bool(flags&16)
        if length<5 or offset+length+2>len(body) or body[offset+2:offset+5]!=OUI or body[offset+5]!=4:raise ValueError('invalid vendor element')
        if current not in (1,2) or (current==1 and flags&0xf0) or (current==2 and flags&0xe0):raise ValueError('invalid version/flags')
        if version is None:version=current
        elif current!=version or current==1:raise ValueError('invalid continuation')
        chunks.append(body[offset+7:offset+length+2]);offset+=length+2
        if more!=(offset<len(body)):raise ValueError('invalid continuation')
    payload=b''.join(chunks)
    if len(payload)>(250 if version==1 else 1470):raise ValueError('invalid payload size')
    return version,payload
def analyze(frame,key):
    if len(key)!=16:raise ValueError('LMK must contain16 bytes')
    if len(frame)<55 or len(frame)>1560 or frame[0]!=0xd0 or frame[1]&0xc7!=0x40 or frame[22]&15:raise ValueError('unsupported protected Action header')
    if frame[16:22]!=b'\xff'*6 or frame[4]&1 or frame[10]&1 or not any(frame[4:10]) or not any(frame[10:16]):raise ValueError('unsupported addresses')
    iv=frame[24:32]
    if iv[2] or iv[3]&0x3f!=0x20:raise ValueError('invalid CCMP IV')
    pn=int.from_bytes(iv[:2]+iv[4:8],'little')
    if not pn:raise ValueError('invalid PN')
    fc=(int.from_bytes(frame[:2],'little')&~0x3800)|0x4000;address=frame[4:22];sequence=bytes([frame[22]&15,0]);tail=frame[10:16]+pn.to_bytes(6,'big');results=[];payloads={}
    for name,prefix,mask_subtype in PROFILES:
        aad=(fc&~0x70 if mask_subtype else fc).to_bytes(2,'little')+address+sequence
        cipher=AES.new(key,AES.MODE_CCM,nonce=bytes([prefix])+tail,mac_len=8);cipher.update(aad)
        try:body=cipher.decrypt_and_verify(frame[32:-8],frame[-8:])
        except ValueError:results.append({'profile':name,'mic_authenticated':False});continue
        try:version,payload=decode_body(body)
        except ValueError:results.append({'profile':name,'mic_authenticated':True,'body_valid':False});continue
        results.append({'profile':name,'mic_authenticated':True,'body_valid':True,'version':version,'payload_bytes':len(payload),'payload_sha256':hashlib.sha256(payload).hexdigest()});payloads[name]=payload
    return {'frame_sha256':hashlib.sha256(frame).hexdigest(),'pn':pn,'key_id':iv[3]>>6,'candidates':results,'matched_profiles':list(payloads),'hardware_origin_verified':False},payloads
def load_key(path):
    data=Path(path).read_bytes()
    if len(data)==16:return data
    try:
        text=data.decode('ascii').strip()
        if len(text)==32:return bytes.fromhex(text)
    except (UnicodeError,ValueError):pass
    raise ValueError('LMK file must contain16 binary bytes or32 hex digits')
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--frame',type=Path,required=True);parser.add_argument('--hex',action='store_true',help='Frame file contains hex text instead of raw bytes');parser.add_argument('--fcs',action='store_true',help='Explicitly remove a captured trailing4-byte FCS');parser.add_argument('--lmk-file',type=Path,required=True);parser.add_argument('--output-payload',type=Path,help='New file under project work/; only one authenticated/valid profile may match');args=parser.parse_args()
    try:
        frame=args.frame.read_bytes()
        if args.hex:frame=bytes.fromhex(frame.decode('ascii'))
        if args.fcs:
            if len(frame)<4:raise ValueError('frame too short')
            frame=frame[:-4]
        report,payloads=analyze(frame,load_key(args.lmk_file))
        if args.output_payload:
            target=args.output_payload.resolve()
            if not target.is_relative_to((ROOT/'work').resolve()) or len(payloads)!=1 or target.exists():raise ValueError('payload output requires one authenticated profile and a new path under work/')
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as out:out.write(next(iter(payloads.values())))
        print(json.dumps(report,indent=2));return 0 if payloads else 2
    except (OSError,UnicodeError,ValueError):
        print(json.dumps({'error':'Invalid/unreadable input, unsupported frame, or refused payload output; key material omitted.'}));return 64
if __name__=='__main__':raise SystemExit(main())
