"""Read-only audit of a local built-in-language UPG; no device access."""
import argparse
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path
from app_registry import ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
from upg import unpack
from builtin_language import SETTINGS_SHA
from language_pack import validate_wording

def files(raw):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        assert len(names) == len(set(names)), 'Duplicate archive names'
        return {m.name: (m, archive.extractfile(m).read() if m.isfile() else None) for m in members}

def audit(path):
    _, parts = unpack(Path(path).read_bytes(), require_stock=False)
    original = [(ROOT / f'work/upg-jp/verified-{i}.bin').read_bytes() for i in range(4)]
    assert parts[:3] == original[:3]
    before, after = files(original[3]), files(parts[3])
    player = './usr/local/bin/SpiderApp'
    assert hashlib.sha256(after[player][1]).hexdigest() == SETTINGS_SHA
    # Independent retained translation comparison, including Homebrew IDs.
    expected = {'en': ROOT/'work/english-wording-review-2/ucs2-dev-en.stx',
                'cs': ROOT/'work/chinese-wording-review-2/zh-CN.stx',
                'ct': ROOT/'work/chinese-wording-review-2/zh-TW.stx'}
    languages = {}
    jp = validate_wording(after['./usr/local/share/gemini/res/stx/ucs2-dev-jp.stx'][1])
    for code in ('jp', 'en', 'cs', 'ct'):
        name = './usr/local/share/gemini/res/stx/ucs2-dev-' + code + '.stx'
        data = after[name][1]
        texts = validate_wording(data)
        assert all(not text or (i < len(texts) and texts[i]) for i, text in enumerate(jp))
        if code in expected:
            assert data == expected[code].read_bytes(), code
        languages[code] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
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
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.firmware), indent=2))
