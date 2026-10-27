"""Prepare complete English STX review from candidate8, without a firmware write."""
from pathlib import Path
import json,io,tarfile,hashlib,sys,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_stx
from wording import complete_missing,replace_verified_texts
w=ROOT/'work/english-wording-review-2';w.mkdir(exist_ok=False)
base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-8/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert hashlib.sha256(base.read_bytes()).hexdigest()=='ebbe63571060b6dbd21dac7fa20ad1c5463428dc7eb13cb966f066715ef5e248'
_,parts=unpack(base.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as tar:
 raw=tar.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-en.stx').read();jp=tar.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-jp.stx').read()
# Exclude appended Homebrew/error labels when defining original missing-ID set.
stock_jp=(ROOT/'work/resource-analysis/ucs2-dev-jp.stx').read_bytes()
missing_path=ROOT/'translations/x1000-en-missing.json';fallback_path=ROOT/'translations/x1000-en-japanese-fallbacks.json'
m=json.loads(missing_path.read_text());f=json.loads(fallback_path.read_text());missing={int(i):s for i,s in m['translations'].items()};fallback={int(i):s for i,s in f['translations'].items()}
before=parse_stx(raw);jp_texts=parse_stx(stock_jp)
full=complete_missing(raw,stock_jp,missing);full=replace_verified_texts(full,{i:before[i]for i in fallback},fallback);after=parse_stx(full)
allowed=set(sum(f['retained_non_english_ids'].values(),[]));remaining={i for i,s in enumerate(after[:len(jp_texts)])if re.search('[\u3040-\u30ff\u3400-\u9fff]',s)};assert remaining==allowed
assert not any(re.search(r'one[ -]?seg',s,re.I)for s in after)
assert all(after[i]for i,s in enumerate(jp_texts)if s)
changes=set(missing)|set(fallback);assert all(a==b for i,(a,b)in enumerate(zip(before,after))if i not in changes)
assert all(len(line)<=32 for s in list(missing.values())+list(fallback.values())for line in s.split('\n'))
(w/'ucs2-dev-en.stx').write_bytes(full)
report={'passed':True,'empty_entries_translated':len(missing),'nonempty_Japanese_fallbacks_translated':len(fallback),'unchanged_special_language_IME_font_ids':sorted(allowed),'original_index_count':len(before),'result_index_count':len(after),'missing_Japanese_nonempty_after':sum(bool(s)and not after[i]for i,s in enumerate(jp_texts)),'growth_bytes':len(full)-len(raw),'maximum_new_translation_line_characters':32,'terminology':'1seg','translation_API_used':False,'sha256':hashlib.sha256(full).hexdigest(),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [base,missing_path,fallback_path,ROOT/'scripts/wording.py',Path(__file__)]},'firmware_created':False,'hardware_tested':False}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='source_hashes'},indent=2))
