"""Prepare root-STX overlay from retained complete translations; no UPG/device writes."""
import hashlib,io,json,sys,tarfile,time
from pathlib import Path
from app_registry import ROOT
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_stx
from language_pack import validate_wording
base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='947acd961e019b79a07e006f21ce3751e2a555a23768f5ec21b769aa8bf093b4'
_,parts=unpack(base.read_bytes(),require_stock=False)
prefix='usr/local/share/gemini/res/stx/'
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
 old={code:archive.extractfile('./'+prefix+'ucs2-dev-'+code+'.stx').read() for code in ('jp','en','cs','ct')}
sources={'en':ROOT/'work/english-wording-review-2/ucs2-dev-en.stx',
         'cs':ROOT/'work/chinese-wording-review-2/zh-CN.stx',
         'ct':ROOT/'work/chinese-wording-review-2/zh-TW.stx'}
new={'jp':old['jp'],**{code:p.read_bytes() for code,p in sources.items()}}
japanese=parse_stx(old['jp']);out=ROOT/'work/builtin-localization'/str(time.time_ns());out.mkdir(parents=True)
rows=[]
for code,data in new.items():
 texts=validate_wording(data)
 missing=[i for i,text in enumerate(japanese) if text and (i>=len(texts) or not texts[i])]
 assert not missing,(code,missing)
 target=out/'root-overlay'/prefix/('ucs2-dev-'+code+'.stx');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 rows.append(dict(code=code,bytes=len(data),previous_bytes=len(old[code]),delta_bytes=len(data)-len(old[code]),sha256=hashlib.sha256(data).hexdigest(),required_japanese_missing=0))
report=dict(prepared=True,resource_overlay_only=True,reference_upg=base.relative_to(ROOT).as_posix(),
            languages=rows,total_delta_bytes=sum(r['delta_bytes'] for r in rows),
            native_settings_switch_implemented=False,external_hooks_removed=False,firmware_generated=False,device_accessed=False,
            inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [base,*sources.values(),Path(__file__)]})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='inputs'},indent=2))
