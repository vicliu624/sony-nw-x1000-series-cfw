"""Remove external language code by exact reconstruction against retained base; no UPG."""
import hashlib,io,json,struct,sys,tarfile,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
source=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='947acd961e019b79a07e006f21ce3751e2a555a23768f5ec21b769aa8bf093b4'
_,parts=unpack(source.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:baseline=archive.extractfile('./usr/local/bin/SpiderApp').read()
assert hashlib.sha256(baseline).hexdigest()=='ea106d7d362793fe39450673b79e3cf77dbdd00bc1ba573b7e8f854d56dc53e0'
area=ROOT/'work/external-language-bridge-10-process-cache-final'
current=(area/'SpiderApp.external-language.analysis-only.elf').read_bytes();evidence=json.loads((area/'report.json').read_text())
assert hashlib.sha256(current).hexdigest()==evidence['sha256']=='213c4c777ff8f71e400bc1287d1096307b7c3fc48122ca4c0d81a88fcfc712a6'
old=ELFFile(io.BytesIO(baseline));elf=ELFFile(io.BytesIO(current));result=bytearray(current)
def offset(address,bytes):return next(s['p_offset']+address-s['p_vaddr'] for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+bytes<=s['p_vaddr']+s['p_filesz'])
for edit in evidence['callsite_edits']:
 at=offset(int(edit['address'],16),4);assert struct.unpack_from('<I',current,at)[0]==int(edit['after'],16)
 assert struct.unpack_from('<I',baseline,at)[0]==int(edit['before'],16)
 struct.pack_into('<I',result,at,int(edit['before'],16))
payload=offset(0x4d8000,evidence['payload_bytes']);assert baseline[payload:payload+evidence['payload_bytes']]==bytes(evidence['payload_bytes'])
result[payload:payload+evidence['payload_bytes']]=baseline[payload:payload+evidence['payload_bytes']]
for index,segment in enumerate(old.iter_segments()):
 if segment['p_type']=='PT_LOAD' and segment['p_flags']&2:
  struct.pack_into('<I',result,old['e_phoff']+index*old['e_phentsize']+20,segment['p_memsz'])
for index,section in enumerate(old.iter_sections()):
 if section.name=='.bss':struct.pack_into('<I',result,old['e_shoff']+index*old['e_shentsize']+20,section['sh_size'])
assert bytes(result)==baseline,'Unaccounted changes outside language hooks/cache'
out=ROOT/'work/builtin-player-base'/str(time.time_ns());out.mkdir(parents=True)
artifact=out/'SpiderApp.builtin-language.analysis-only.elf';artifact.write_bytes(result)
report=dict(prepared=True,artifact=artifact.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(result).hexdigest(),
            exact_pre_external_baseline=True,external_language_hooks_removed=3,external_payload_removed_bytes=evidence['payload_bytes'],
            cache_bss_extent_removed_bytes=evidence['bss_extent_added_bytes'],player_file_growth_bytes=0,
            settings_language_selector_enabled=False,remote_sdk_recomposition_pending=True,firmware_generated=False,device_accessed=False,
            source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
