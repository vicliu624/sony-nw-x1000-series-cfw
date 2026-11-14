"""Check the legacy external-language prepare bridge offline."""
import io
import json
import time

from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from player_prepare_bridge import PREPARE_BRIDGE, build_external_prepare, patch_prepare_bridge, prepare_bridge


def check(base, patched, stock, guards):
    elf=ELFFile(io.BytesIO(base))
    def offset(address,count):
        s=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz'])
        return int(s['p_offset']+address-s['p_vaddr'])
    restored=bytearray(patched)
    for address,count in ((0x718e0,4),(0x71aa4,4),(PREPARE_BRIDGE,len(prepare_bridge()))):
        at=offset(address,count);restored[at:at+count]=base[at:at+count]
    assert bytes(restored)==base and len(patched)==len(base)
    assert patched[offset(0x4d7ff0,16):offset(0x4d7ff0,16)+16]==base[offset(0x4d7ff0,16):offset(0x4d7ff0,16)+16]
    for guard in guards:
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
    return refusals


if __name__ == '__main__':
    work = ROOT / 'work/player-prepare-composition' / str(time.time_ns())
    stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
    base, artifact, report = build_external_prepare(work, stock)
    guards = report['native_guard_checks']
    refusals = check(base, artifact.read_bytes(), stock, guards)
    report.update(passed=True, source_composition_sha256=report['base_sha256'],
                  mapped_payload_preserved_except_bridge=True, met_stub_unchanged=True,
                  existing_native_guard_spans_unchanged=True, existing_native_guard_span_count=len(guards),
                  refusals=refusals, edit=report['prepare_edit'])
    (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
