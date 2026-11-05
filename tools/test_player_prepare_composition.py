"""Source-composed mapped prepare bridge, without a firmware/UPG package."""
import contextlib,hashlib,io,json,runpy,time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from player_prepare_bridge import patch_prepare_bridge,PREPARE_BRIDGE,prepare_bridge
with contextlib.redirect_stdout(io.StringIO()):
    composition=runpy.run_path(str(ROOT/'tools/test_player_composition.py'))
base=composition['combined_artifact'].read_bytes()
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
patched,edit=patch_prepare_bridge(base,stock)
elf=ELFFile(io.BytesIO(base))
def offset(address,count):
    s=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz'])
    return int(s['p_offset']+address-s['p_vaddr'])
restored=bytearray(patched)
for address,count in ((0x718e0,4),(0x71aa4,4),(PREPARE_BRIDGE,len(prepare_bridge()))):
    at=offset(address,count);restored[at:at+count]=base[at:at+count]
assert bytes(restored)==base and len(patched)==len(base)
assert patched[offset(0x4d7ff0,16):offset(0x4d7ff0,16)+16]==base[offset(0x4d7ff0,16):offset(0x4d7ff0,16)+16]
for guard in composition['checks']:
    address=int(guard['address'],16);count=guard['bytes'];at=offset(address,count)
    assert patched[at:at+count]==base[at:at+count],guard
refusals=[]
for name,address in (('occupied-slot',PREPARE_BRIDGE),('changed-action',0x718c0),('changed-coordinator',0x112fc),('changed-other-code',0x20000)):
    mutated=bytearray(base);mutated[offset(address,1)]^=1
    try:patch_prepare_bridge(bytes(mutated),stock)
    except ValueError:refusals.append(name)
    else:raise AssertionError(name)
try:patch_prepare_bridge(patched,stock)
except ValueError:refusals.append('already-patched')
else:raise AssertionError('Patched input accepted twice')
try:patch_prepare_bridge(stock,stock)
except ValueError:refusals.append('unmapped-original')
else:raise AssertionError('Unmapped original accepted')
work=ROOT/'work/player-prepare-composition'/str(time.time_ns());work.mkdir(parents=True)
artifact=work/'SpiderApp.prepare-bridge.analysis-only.elf';artifact.write_bytes(patched)
report=dict(passed=True,analysis_only=True,ready_to_flash=False,device_accessed=False,firmware_package_created=False,
            source_composition=str(composition['combined_artifact'].relative_to(ROOT)),
            source_composition_sha256=hashlib.sha256(base).hexdigest(),candidate_sha256=hashlib.sha256(patched).hexdigest(),
            mapped_payload_preserved_except_bridge=True,met_stub_unchanged=True,existing_native_guard_spans_unchanged=True,existing_native_guard_span_count=len(composition['checks']),refusals=refusals,edit=edit,
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/player_prepare_bridge.py','tools/test_player_prepare_composition.py','tools/test_player_composition.py')},
            limits=['Source-built Home/language/owner/Met composition plus mapped bridge only; no paired DSO dispatcher or actual SDK exit policy is activated.',
                    'Zero growth is relative to this source composition, not an original firmware size or partition-capacity guarantee.',
                    'No original loader boot, manager event ordering, hardware or recovery qualification.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
