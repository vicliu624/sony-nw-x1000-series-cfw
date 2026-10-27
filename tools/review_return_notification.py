"""Record bounded REA location review plus independent inactive/ack replays."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];area=ROOT/'work/rea-return-gap';expected='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0';rows=[]
for name,address in [('manager-change-14e14','0x14e14'),('manager-event-b614','0xb614'),('manager-reap-11998','0x11998')]:
 path=area/(name+'.json');result=json.loads(path.read_text());assert not result.get('isError');evidence=result['structuredContent'];assert evidence['subject']['digest']['sha256']==expected
 assert 'FUN_'+format(int(address,16),'08x') in evidence['normalized_result']
 rows.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'address':address,'accepted_for_function_identity':True})
path=area/'manager-notify-bd74.json';result=json.loads(path.read_text())['structuredContent'];selection=result['raw_result']['selection'];assert selection['mapped_address']=='0x13d74' and selection['procedure_address']=='0x13d2c'
rows.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'requested':'0xbd74','selection':selection,'accepted_for_function_identity':False,'reason':'Resolved as file offset; mapped address differs from requested virtual address.'})
for name in ('manager-inactive-a62c-exact','manager-inactive-a62c-assembly'):
 path=area/(name+'.json');result=json.loads(path.read_text());assert result.get('isError') is True
 rows.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'accepted_for_function_identity':False,'reason':'Explicit name not resolved; retained as tool limitation only.'})
inputs=[]
for name in ('native-inactive-notification-contract.json','native-manager-change-wrong-ack.json','native-manager-change-ack-registered.json'):
 path=ROOT/'sources'/name;report=json.loads(path.read_text());assert report.get('sysmgrd_sha256')==expected
 inputs.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'sysmgrd_sha256':expected,'REA_location_review':rows,'instruction_replay_inputs':inputs,'source_hashes':{entry['path']:entry['sha256'] for entry in rows+inputs},'finding':'Notification return0 is not inactive acknowledgement. Existing manager replay requires matching current-app acknowledgement before target activation.','remaining':'Real application receipt, cleanup and acknowledgement production/delivery remain unqualified.','limits':['REA pseudocode identity accepted only for explicitly matched functions; ambiguous/missing targets rejected.','Original notification and manager instruction replays still use virtual registry/callback/IPC services.','No inference that the player released display or storage; no firmware generated.']}
(ROOT/'sources/native-return-notification-review.json').write_text(json.dumps(report,indent=2)+'\n');print('REA location and original notification/acknowledgement evidence reviewed; physical lifecycle remains unqualified.')
