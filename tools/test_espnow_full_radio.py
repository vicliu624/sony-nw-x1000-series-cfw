"""Audit built full-radio container and reject malformed payloads; offline only."""
from pathlib import Path
import hashlib,json,struct,sys
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from marvell_firmware import parse,serialize
from prepare_espnow_radio_candidate import memory,STOCK_SHA,HELPER_SHA,RESERVED_START,RESERVED_END,BSS_START,BSS_END
from build_espnow_full_radio import construct,build
OUT=(Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'work/espnow-full-radio-review-3');manifest=json.loads((OUT/'manifest.json').read_text());stock=(OUT/'stock/sd8686.bin').read_bytes();candidate=(OUT/'candidate/sd8686.bin').read_bytes()
assert hashlib.sha256(stock).hexdigest()==STOCK_SHA and hashlib.sha256(candidate).hexdigest()==manifest['candidate_sha256']
assert serialize(parse(candidate))==candidate
assert all(s['address']!=0x17328 for s in manifest['immutable_segments'])
assert manifest['startup_only_segments'][0]['runtime_reclaimed']
assert (OUT/'stock/helper_sd.bin').read_bytes()==(OUT/'candidate/helper_sd.bin').read_bytes()
assert hashlib.sha256((OUT/'stock/helper_sd.bin').read_bytes()).hexdigest()==HELPER_SHA
old=memory(parse(stock));new=memory(parse(candidate));allowed=set()
for a,n in ((0x163ee,2),(0xc00026b0,4),(0x88d6,10),(0xd51c,8),(0x17328,8),(0x17338,8)):allowed.update(range(a,a+n))
assert all(new[a]==v for a,v in old.items() if a not in allowed)
assert set(new)-set(old)==set(range(RESERVED_START,RESERVED_END))
def read(a,n):return bytes(new[a+i] for i in range(n))
assert read(0x163ee,2)==bytes.fromhex('0322')
first=struct.unpack('<II',read(0x17328,8));second=struct.unpack('<II',read(0x17338,8))
assert first==(BSS_START,RESERVED_START-BSS_START) and second==(RESERVED_END,BSS_END-RESERVED_END)
assert read(0x88d6,6)==bytes.fromhex('014b1847c046') and struct.unpack('<I',read(0x88dc,4))[0]==manifest['entries']['xnow_radio_word_command_entry']
assert read(0xd51c,4)==bytes.fromhex('004b1847') and struct.unpack('<I',read(0xd520,4))[0]==manifest['entries']['xnow_radio_completion_entry']
assert struct.unpack('<I',read(0xc00026b0,4))[0]==manifest['entries']['xnow_radio_full_receive']
assert manifest['occupied_span_bytes']<=1900 and manifest['section_bytes']<=manifest['occupied_span_bytes']
# Fault injection must be rejected before a modified candidate can be returned.
area=OUT/'negative-tests';area.mkdir(exist_ok=True);payload=(OUT/'radio.elf').read_bytes();cases=[]
def reject(label,data):
 path=area/(label+'.elf');path.write_bytes(data)
 try:construct(stock,path)
 except (ValueError,KeyError):cases.append(label)
 else:raise AssertionError('accepted '+label)
with (OUT/'radio.elf').open('rb') as f:
 e=ELFFile(f);shoff=e['e_shoff'];shentsize=e['e_shentsize'];sections=list(e.iter_sections());state=next(s for s in sections if s.name=='.state');text_index=next(i for i,s in enumerate(sections) if s.name=='.text');state_index=next(i for i,s in enumerate(sections) if s.name=='.state');symtab=e.get_section_by_name('.symtab')
 function_index=next(i for i,s in enumerate(symtab.iter_symbols()) if s.name=='xnow_radio_full_receive');symvalue=symtab['sh_offset']+function_index*symtab['sh_entsize']+4
bad=bytearray(payload);struct.pack_into('<H',bad,18,3);reject('wrong-architecture',bad)
bad=bytearray(payload);struct.pack_into('<I',bad,shoff+text_index*shentsize+12,RESERVED_START-4);reject('out-of-reservation',bad)
bad=bytearray(payload);struct.pack_into('<I',bad,shoff+state_index*shentsize+4,8);reject('uninitialized-state-section',bad)
bad=bytearray(payload);struct.pack_into('<I',bad,shoff+state_index*shentsize+12,RESERVED_START);reject('overlapping-state',bad)
bad=bytearray(payload);struct.pack_into('<I',bad,symvalue,manifest['entries']['xnow_radio_full_receive']&~1);reject('non-thumb-entry',bad)
bad=bytearray(payload);bad[state['sh_offset']]^=1;reject('invalid-initial-control',bad)
bad=bytearray(stock);bad[100]^=1
try:construct(bytes(bad),OUT/'radio.elf')
except ValueError:cases.append('wrong-original-input')
else:raise AssertionError('accepted wrong stock')
helper=area/'wrong-helper.bin';helper.write_bytes(b'bad');new_output=area/'must-not-exist'
assert not new_output.exists()
try:build(OUT/'stock/sd8686.bin',helper,new_output)
except ValueError:cases.append('wrong-helper-before-output')
else:raise AssertionError('accepted helper')
assert not new_output.exists()
for malformed in (candidate[:-1],candidate+b'bad'):
 try:parse(malformed)
 except ValueError:pass
 else:raise AssertionError('accepted broken container')
report={'passed':True,'candidate_sha256':manifest['candidate_sha256'],'unchanged_original_bytes_outside_six_patch_ranges':True,'all_added_addresses_exact_reservation':True,'both_thumb_literal_alignments_verified':True,'scatter_and_pool_preserved':True,'helper_identical':True,'occupied_span_bytes':manifest['occupied_span_bytes'],'negative_payload_cases':cases,'malformed_container_rejected':True,'device_accessed':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
