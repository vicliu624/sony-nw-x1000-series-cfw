"""Generate completed external Simplified/Traditional STX data, never UPG."""
from pathlib import Path
import io,tarfile,json,hashlib,sys,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_stx
from wording import complete_missing,replace_verified_texts
from language_pack import validate_wording
w=ROOT/'work/chinese-wording-review-2';w.mkdir(exist_ok=False);source=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert hashlib.sha256(source.read_bytes()).hexdigest()=='947acd961e019b79a07e006f21ce3751e2a555a23768f5ec21b769aa8bf093b4';_,parts=unpack(source.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as archive:raw={code:archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-'+code+'.stx').read()for code in ['jp','cs','ct']}
japanese=parse_stx(raw['jp']);results=[];allowed={4301,4306,7147,*range(7116,7126)}
for label,code in [('zh-CN','cs'),('zh-TW','ct')]:
 path=ROOT/('translations/x1000-'+label+'.json');document=json.loads(path.read_text());assert document['base_firmware_upg_sha256']==hashlib.sha256(source.read_bytes()).hexdigest();changes={int(i):s for i,s in document['translations'].items()};before=parse_stx(raw[code]);missing={i for i,(a,b)in enumerate(zip(japanese,before))if a and not b};assert missing==set(document['empty_ids'])
 complete=complete_missing(raw[code],raw['jp'],{i:changes[i]for i in missing});other={i:s for i,s in changes.items()if i not in missing};complete=replace_verified_texts(complete,{i:before[i]for i in other},other);after=validate_wording(complete)
 assert all(after[i]for i,s in enumerate(japanese)if s)
 assert all(a==b for i,(a,b)in enumerate(zip(before,after))if i not in changes)
 kana={i for i,s in enumerate(after)if re.search('[\u3040-\u30ff]',s)};assert kana<=allowed,(label,sorted(kana-allowed))
 for i,s in changes.items():
  assert re.findall('[\ue000-\uf8ff]',s)==re.findall('[\ue000-\uf8ff]',japanese[i]),i
  assert not re.search(r'one[ -]?seg',s,re.I)
  assert all(sum(1 if ord(c)<128 else 2 for c in line)<=24 for line in s.split('\n'))
 out=w/(label+'.stx');out.write_bytes(complete);report={'passed':True,'language':label,'stock_code':code,'artifact':str(out.relative_to(ROOT)),'sha256':hashlib.sha256(complete).hexdigest(),'bytes':len(complete),'empty_records_completed':len(missing),'changed_records':len(changes),'resource_records':len(after),'missing_required_records':0,'unmodified_records_preserved':True,'max_changed_line_halfwidth_units':24,'remaining_kana_ids':sorted(kana),'translation_API_used':False,'system_partition_bytes_added':0,'firmware_generated':False,'hardware_tested':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [source,path,ROOT/'scripts/wording.py',Path(__file__)]}};(w/(label+'-report.json')).write_text(json.dumps(report,indent=2)+'\n');results.append(report)
(w/'report.json').write_text(json.dumps({'passed':True,'languages':results,'hardware_tested':False},indent=2)+'\n');print(json.dumps([{k:r[k]for k in ['language','bytes','empty_records_completed','changed_records','missing_required_records']}for r in results],indent=2))
