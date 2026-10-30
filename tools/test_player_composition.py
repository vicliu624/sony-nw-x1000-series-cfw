"""Source-built Homebrew/language/player ELF compatibility; no UPG or device."""
from pathlib import Path
import hashlib,io,json,re,struct,time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_home_feedback import build as home_build
from release_firmware import add_language_cache
from build_player_host import patch_owner_anchor
w=ROOT/'work/player-composition'/str(time.time_ns());w.mkdir(parents=True)
home,symbols,home_report=home_build(w/'home')
def offset(raw,address,count):
 elf=ELFFile(io.BytesIO(raw))
 matches=[int(s['p_offset'])+address-int(s['p_vaddr']) for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and int(s['p_vaddr'])<=address and address+count<=int(s['p_vaddr'])+int(s['p_filesz'])]
 assert len(matches)==1,(hex(address),count,matches)
 return matches[0]
# Match the maintained release's Homebrew error descriptor edits.
data=bytearray(home);at=offset(home,symbols['hb_error_descriptor'],48)
struct.pack_into('<I',data,at+4,99999);struct.pack_into('<I',data,at+20,0)
baseline=add_language_cache(bytes(data),w)
composite,edit=patch_owner_anchor(baseline);at=offset(baseline,0xff3c,4)
assert len(composite)==len(baseline) and composite[:at]==baseline[:at] and composite[at+4:]==baseline[at+4:]
checks=[]
for path in sorted((ROOT/'runtime/platform/player').glob('stock_*.c')):
 text=path.read_text()
 arrays={name:bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]+)',values)) for name,values in re.findall(r'(\w+)\[32\]\s*=\s*\{([^}]+)\}',text)}
 calls=re.findall(r'xw_stock_image_match\(\s*(0x[0-9a-fA-F]+)u?\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*(\w+)\s*\)',text)
 if path.name=='stock_volume.c':
  constants=dict(re.findall(r'#define\s+(REGION_\w+)\s+(0x[0-9a-fA-F]+)u?',text))
  calls.append((constants['REGION_BEGIN'],hex(int(constants['REGION_END'],16)-int(constants['REGION_BEGIN'],16)),'expected'))
 for start,length,name in calls:
  address,count=int(start,16),int(length,16);expected=arrays[name];assert len(expected)==32
  actual=composite[offset(composite,address,count):offset(composite,address,count)+count]
  assert hashlib.sha256(actual).digest()==expected,(path.name,start,length,name)
  row=dict(source=str(path.relative_to(ROOT)),address=start,bytes=count,digest=name)
  if row not in checks:checks.append(row)
assert len(checks)>=17,len(checks)
hook=(ROOT/'runtime/platform/player/host_hook.c').read_text();digest=bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]+)',re.search(r'anchor_digest\[32\]=\{([^}]+)\}',hook).group(1)))
assert hashlib.sha256(composite[offset(composite,0xff3c,8):offset(composite,0xff3c,8)+8]).digest()==digest
artifact=w/'SpiderApp.home-language-player.analysis-only.elf';artifact.write_bytes(composite)
assert not list(w.rglob('*.UPG'))
report=dict(passed=True,analysis_only=True,ready_to_flash=False,firmware_package_created=False,device_accessed=False,baseline_sha256=hashlib.sha256(baseline).hexdigest(),composite_sha256=hashlib.sha256(composite).hexdigest(),anchor_edit=edit,additional_elf_bytes=0,native_guard_checks=checks,source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'tools/test_player_composition.py',ROOT/'tools/build_player_host.py',ROOT/'tools/release_firmware.py',ROOT/'runtime/platform/player/host_hook.c',ROOT/'runtime/apps/language/process_cache_entry.S',ROOT/'runtime/apps/language/process_cache.c',ROOT/'runtime/apps/language/package.c',ROOT/'runtime/apps/language/package.h',ROOT/'runtime/native/sha256.c']},home_source_hashes=home_report['source_hashes'],limits=['Source composition and guard equivalence only; no original GUI boot or background player runtime executes.','No installer, partition capacity, sleep/USB or physical qualification is implied.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
