"""Read-only audit of a local built-in-language UPG; no device access."""
import argparse
import hashlib
import io
import json
import struct
import sys
import tarfile
from pathlib import Path
from app_registry import ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
from upg import unpack
from builtin_language import SETTINGS_SHA
from language_pack import validate_wording
from resources import parse_stx

def files(raw):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        assert len(names) == len(set(names)), 'Duplicate archive names'
        return {m.name: (m, archive.extractfile(m).read() if m.isfile() else None) for m in members}

def audit_wordings(before, after):
    translation_files = {
        'jp': (),
        'en': ('x1000-en-missing.json', 'x1000-en-japanese-fallbacks.json'),
        'cs': ('x1000-zh-CN.json',),
        'ct': ('x1000-zh-TW.json',),
    }
    prefix = './usr/local/share/gemini/res/stx/ucs2-dev-'
    languages = {}
    japanese = validate_wording(after[prefix + 'jp.stx'][1])
    for code, documents in translation_files.items():
        name = prefix + code + '.stx'
        data = after[name][1]
        texts = validate_wording(data)
        assert all(not text or (i < len(texts) and texts[i]) for i, text in enumerate(japanese))
        expected = parse_stx(before[name][1]) + ['Homebrew', 'Homebrew unavailable.\nCheck HOMEBREW.']
        for document in documents:
            translations = json.loads((ROOT / 'translations' / document).read_text(encoding='utf-8'))
            for index, text in translations['translations'].items():
                expected[int(index)] = text
        assert len(texts) == len(expected), code
        for index, (actual, original) in enumerate(zip(texts, expected)):
            assert actual == original, (code, index)
        languages[code] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return languages


def replay_language_settings(original, patched):
    from elftools.elf.elffile import ELFFile
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_LR

    market = 1

    def stock_boundary(uc, pc, size, context):
        if pc in (0xe5f4, 0xf6c0):
            uc.reg_write(UC_ARM_REG_R0, market if pc == 0xf6c0 else 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    def emulator(image):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(0x8000, 0x1000000)
        for segment in ELFFile(io.BytesIO(image)).iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                cpu.mem_write(segment['p_vaddr'], segment.data())
        cpu.mem_map(0x50000000, 4096)
        cpu.mem_map(0x60000000, 0x10000)
        cpu.hook_add(UC_HOOK_CODE, stock_boundary)
        return cpu

    def query(cpu, item):
        cpu.mem_write(0x60000000, bytes(8))
        cpu.reg_write(UC_ARM_REG_R0, item)
        cpu.reg_write(UC_ARM_REG_R1, 0x60000000)
        cpu.reg_write(UC_ARM_REG_R2, 0x60000004)
        cpu.reg_write(UC_ARM_REG_SP, 0x6000f000)
        cpu.reg_write(UC_ARM_REG_LR, 0x50000000)
        cpu.emu_start(0x751ec, 0x50000000, count=10000)
        assert cpu.reg_read(UC_ARM_REG_PC) == 0x50000000
        pointer, count = struct.unpack('<II', cpu.mem_read(0x60000000, 8))
        assert count <= 100
        return list(struct.unpack(f'<{count}I', cpu.mem_read(pointer, count * 4))) if count else []

    before, after = emulator(original), emulator(patched)
    items = sorted({struct.unpack('<I', before.mem_read(0x3f611c + i * 20, 4))[0]
                    for i in range(95)})
    for market in (1, 2):
        for item in items:
            rows = query(before, item)
            expected = rows + [0xf80000] if market == 1 and item == 2 else rows
            assert query(after, item) == expected, (market, item)
    return 2 * len(items)


def audit(path, *, replay_settings=False):
    _, parts = unpack(Path(path).read_bytes(), require_stock=False)
    original = [(ROOT / f'work/upg-jp/verified-{i}.bin').read_bytes() for i in range(4)]
    assert parts[:3] == original[:3]
    before, after = files(original[3]), files(parts[3])
    player = './usr/local/bin/SpiderApp'
    assert hashlib.sha256(after[player][1]).hexdigest() == SETTINGS_SHA
    languages = audit_wordings(before, after)
    report_file = Path(path).parent / 'verification.json'
    manifest = json.loads(report_file.read_text(encoding='utf-8'))
    assert manifest['native_language_settings'] and not manifest['external_language_files_generated']
    allowed = {'./' + name for name in manifest['system_changes']}
    changed = []
    for name in set(before) | set(after):
        if name not in before or name not in after:
            assert name in allowed
            changed.append(name)
            continue
        a, b = before[name], after[name]
        assert (a[0].mode, a[0].uid, a[0].gid, a[0].type, a[0].linkname, a[0].mtime) == (
                b[0].mode, b[0].uid, b[0].gid, b[0].type, b[0].linkname, b[0].mtime), name
        if a[1] != b[1]:
            assert name in allowed, name
            changed.append(name)
    assert all('HOMEBREW/languages' not in n for n in after)
    def footprint(entries):
        sizes = [len(data) for _, data in entries.values() if data is not None]
        return dict(regular_file_bytes=sum(sizes), regular_file_4k_blocks=sum((n+4095)//4096 for n in sizes))
    old_size, new_size = footprint(before), footprint(after)
    report = dict(passed=True, device_accessed=False, flashed=False, ready_to_flash=False,
                  sdk_integrated=False, languages=languages, stock_components_0_to_2_unchanged=True,
                  undeclared_file_changes=False, existing_metadata_preserved=True,
                  changed_files=sorted(changed), stock_footprint=old_size, candidate_footprint=new_size,
                  regular_file_growth_bytes=new_size['regular_file_bytes']-old_size['regular_file_bytes'],
                  regular_file_4k_growth_bytes=4096*(new_size['regular_file_4k_blocks']-old_size['regular_file_4k_blocks']),
                  limits=['Regular-file block estimate excludes filesystem metadata and reserved blocks.',
                          'This localization-only build has no player SDK activation or remote Settings switch.',
                          'No physical boot, storage handoff or sleep/wake qualification.'])
    if replay_settings:
        report['arm_list_replay_cases'] = replay_language_settings(before[player][1], after[player][1])
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('--replay-settings', action='store_true', help='Compare native list queries with the stock firmware in Unicorn')
    args = parser.parse_args()
    print(json.dumps(audit(args.firmware, replay_settings=args.replay_settings), indent=2))
