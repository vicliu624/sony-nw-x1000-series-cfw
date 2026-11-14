"""Check the source-built Homebrew, language cache and player anchors offline."""
import io
import json
import time

from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_player_met_anchor import patch_met_anchor
from player_prepare_bridge import build_external_language


def offset(elf, address, count):
    matches = [segment for segment in elf.iter_segments()
               if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address
               and address + count <= segment['p_vaddr'] + segment['p_filesz']]
    assert len(matches) == 1, (hex(address), count)
    segment = matches[0]
    return segment['p_offset'] + address - segment['p_vaddr']


def check(base, owner, combined):
    occupied = bytearray(owner)
    occupied[offset(ELFFile(io.BytesIO(owner)), 0x4d7ff0, 16)] = 1
    try:
        patch_met_anchor(bytes(occupied), mapped_stub=0x4d7ff0)
    except ValueError as error:
        assert str(error) == 'Composed Met slot occupied'
    else:
        raise AssertionError('Occupied composed slot accepted')
    # Compare all mapped bytes outside the declared anchors and ELF headers.
    old_elf = ELFFile(io.BytesIO(base))
    new_elf = ELFFile(io.BytesIO(combined))
    assert old_elf['e_entry'] == new_elf['e_entry']
    for segment in old_elf.iter_segments():
        if segment['p_type'] != 'PT_LOAD':
            continue
        address, count = segment['p_vaddr'], segment['p_filesz']
        before = bytearray(segment.data())
        start = offset(new_elf, address, count)
        after = combined[start:start + count]
        if segment['p_offset'] == 0:
            header_end = old_elf['e_phoff'] + old_elf['e_phnum'] * old_elf['e_phentsize']
            before[:header_end] = after[:header_end]
        for site, size in ((0xff3c, 4), (0x27c610, 4), (0x4d7ff0, 16)):
            if address <= site and site + size <= address + count:
                at = site - address
                before[at:at + size] = after[at:at + size]
        assert before == after, hex(address)


if __name__ == '__main__':
    work = ROOT / 'work/player-composition' / str(time.time_ns())
    base, owner, combined, report = build_external_language(work)
    check(base, owner, combined)
    (work / 'SpiderApp.home-language-player.analysis-only.elf').write_bytes(owner)
    (work / 'SpiderApp.home-language-player-met.analysis-only.elf').write_bytes(combined)
    report.update(passed=True, analysis_only=True, ready_to_flash=False,
                  firmware_package_created=False, device_accessed=False,
                  additional_elf_bytes=0, combined_growth_bytes=len(combined) - len(base),
                  original_mapped_payload_preserved_except_anchors=True)
    (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
