"""Offline authentication of explicit standard-peer CAPTURE records; no device IO."""
from pathlib import Path
import argparse,json
from espnow_known_key_frame import analyze,load_key

def analyze_lines(lines,key):
    rows=[];seen={};conflicts=[]
    for number,line in enumerate(lines,1):
        if not line.startswith(('CAPTURE ','RAW_ACTION ')):continue
        try:
            if len(line)>4096:raise ValueError('oversize record')
            tokens=line.split()[1:]
            fields=dict(token.split('=',1) for token in tokens)
            native=line.startswith('RAW_ACTION ')
            names={'fcs','bytes','hex'} if native else {'fcs','length','frame'}
            if len(tokens)!=3 or len(fields)!=3 or set(fields)!=names or fields['fcs']!=('0' if native else '1'):raise ValueError('invalid fields')
            raw=bytes.fromhex(fields['hex' if native else 'frame'])
            if len(raw)!=int(fields['bytes' if native else 'length']) or not (55 if native else 59)<=len(raw)<=(1560 if native else 1564):raise ValueError('invalid length')
            frame=raw if native else raw[:-4];result,payloads=analyze(frame,key)
            row={'line':number,'canonical_native_header':native,**result}
            if len(payloads)==1:
                identity=(frame[10:16],result['pn'])
                # Retry/sequence/duration fields can change without changing
                # the encrypted content; compare ciphertext and MIC, not header.
                value=frame[32:]
                if identity in seen:
                    previous,first=seen[identity]
                    row['duplicate_ciphertext']=value==previous
                    if value!=previous:conflicts.append({'first_line':first,'line':number,'pn':result['pn']})
                else:seen[identity]=(value,number)
            rows.append(row)
        except (ValueError,UnicodeError):rows.append({'line':number,'invalid_capture_record':True})
    authenticated=sum(len(row.get('matched_profiles',[]))==1 for row in rows)
    return {'capture_records':len(rows),'authenticated_records':authenticated,'invalid_records':sum(bool(r.get('invalid_capture_record')) for r in rows),'authenticated_pn_ciphertext_conflicts':conflicts,'records':rows,'fcs_crc_verified':False,'hardware_origin_verified':False,'device_accessed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--log',type=Path,required=True);p.add_argument('--lmk-file',type=Path,required=True);a=p.parse_args()
    try:
        key=load_key(a.lmk_file)
        with a.log.open(encoding='ascii') as source:report=analyze_lines(source,key)
        print(json.dumps(report,indent=2))
        return 0 if report['authenticated_records'] and not report['invalid_records'] and not report['authenticated_pn_ciphertext_conflicts'] else 2
    except (OSError,ValueError,UnicodeError):
        print(json.dumps({'error':'Unreadable or invalid capture/key input; key material omitted.'}));return 64
if __name__=='__main__':raise SystemExit(main())
