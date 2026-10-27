"""Derive an uninstalled resource-SID ELF from the hash-bound feedback ELF."""
from pathlib import Path
import json,hashlib,io,struct
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/home-feedback-build-review-1';resources=ROOT/'work/home-feedback-resource-review-1';out=ROOT/'work/home-feedback-resource-elf-review-1';out.mkdir(exist_ok=False)
base=json.loads((source/'build.json').read_text());raw=(source/'SpiderApp.feedback.analysis-only.elf').read_bytes();assert hashlib.sha256(raw).hexdigest()==base['candidate_sha256']
for name,digest in base['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
res=json.loads((resources/'report.json').read_text());assert res['proposed_sid']==99999 and res['added_tid']==7309
for row in res['system_entries']:
 p=resources/'overlay'/row['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['new_sha256']
b=bytearray(raw);elf=ELFFile(io.BytesIO(raw));address=base['symbols']['hb_error_descriptor']
offset=next(s['p_offset']+address-s['p_vaddr'] for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+48<=s['p_vaddr']+s['p_filesz'])
assert struct.unpack_from('<12I',b,offset)==(745,0,1,0,0,base['symbols']['hb_error_text'],0,0,0,0,0,2)
struct.pack_into('<I',b,offset+4,99999);struct.pack_into('<I',b,offset+20,0)
assert all(a==c or i in set(range(offset+4,offset+8))|set(range(offset+20,offset+24)) for i,(a,c) in enumerate(zip(raw,b)))
artifact=out/'SpiderApp.resource.analysis-only.elf';artifact.write_bytes(b)
report={'profile':'resource-feedback-analysis-only','base_candidate_sha256':base['candidate_sha256'],'candidate_sha256':hashlib.sha256(b).hexdigest(),'symbols':base['symbols'],'sid':99999,'tid':7309,'descriptor_address':hex(address),'changed_words':2,'file_size_changed':False,'requires_resource_overlay':str(resources.relative_to(ROOT)/'overlay'),'resource_manifest_sha256':hashlib.sha256((resources/'report.json').read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'firmware_created':False,'ready_to_flash':False}
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['profile','candidate_sha256','changed_words','file_size_changed','ready_to_flash']},indent=2))
