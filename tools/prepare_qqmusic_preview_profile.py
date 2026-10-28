"""Pin observed/reviewed software identity for preview preflight, PC only.

Does not install, connect to the device or qualify hardware output.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-preview-audio'
record=json.loads((work/'device-local-identity-matches.json').read_text())
assert record['device_mode1_page']['entire_page_matches_local'] and record['device_mode1_page']['instruction']=='0130a0e3'
assert all(r['stock_equal'] for r in record['original_audio_apf_regions_equal'])
assert record['appproxy']['matches_original'] and record['sysmgrd']['matches_original']
selected={'spider':record['spider_matches'][0],'launcher':record['launcher_matches'][0],'proxy':{'path':'work/targets-jp/appproxy',**record['appproxy']},'manager':{'path':'work/targets-jp/sysmgrd',**record['sysmgrd']}}
lines=['/* Reviewed installed software identity; NOT physical audio qualification. */']
lines.append('static const struct qq_preview_handoff_policy qq_preview_reviewed_policy={')
for key,row in selected.items():
    path=ROOT/row['path'].replace('\\','/');data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    assert digest==row['sha256'] and len(data)==row['bytes']
    lines.append(' .'+key+'={'+str(len(data))+'u,{'+','.join('0x'+digest[i:i+2] for i in range(0,64,2))+'}},')
lines.append('};')
out=ROOT/'work/qqmusic-preview-native';out.mkdir(exist_ok=True)
(out/'qqmusic_preview_profile.h').write_text('\n'.join(lines)+'\n')
report={'generated':True,'device_identity_observed_read_only':True,'mode1_page_verified':True,'audio_device_accessed':False,'hardware_output_qualified':False,'profile_sha256':hashlib.sha256((out/'qqmusic_preview_profile.h').read_bytes()).hexdigest(),'inputs':{k:{'sha256':r['sha256'],'bytes':r['bytes']} for k,r in selected.items()},'limits':['Pins software preflight only; does not create an exclusive audio lease.','Full native owner adapter, current sound-device state and runtime audio acceptance remain separate gates.']}
(out/'profile-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
