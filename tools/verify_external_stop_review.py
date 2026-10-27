"""Independently compare an external-only review with its preserved base; PC only."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate')
    args = parser.parse_args()
    area = (ROOT / args.candidate).resolve()
    require(area.is_relative_to(ROOT / 'dist') and area.is_dir(), 'Invalid candidate')
    seen = set()
    for line in (area / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts
                and name not in seen, 'Invalid checksum path')
        path = area / name
        require(path.resolve().is_relative_to(area) and not path.is_symlink()
                and sha(path) == expected, f'Checksum mismatch: {name}')
        seen.add(name)
    require(seen == {p.relative_to(area).as_posix() for p in area.rglob('*')
                     if p.is_file() and p.name != 'SHA256SUMS'}, 'Unlisted files')
    report = json.loads((area / 'review/verification.json').read_text())
    require(report['profile'] == 'external-stop-fix-local-review', 'Wrong profile')
    require(not any(report[k] for k in ('ready_to_flash', 'device_written', 'hardware_tested')),
            'Invalid qualification claim')
    base = (ROOT / report['base_candidate']).resolve()
    require(base.is_relative_to(ROOT / 'dist') and base != area, 'Invalid base')
    upg = 'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
    require((area / upg).read_bytes() == (base / upg).read_bytes(), 'UPG changed')
    require(sha(area / upg) == report['upg_sha256'], 'UPG hash mismatch')
    def tree(folder):
        return {p.relative_to(folder).as_posix(): sha(p)
                for p in folder.rglob('*') if p.is_file()}
    before, after = tree(base / 'external'), tree(area / 'external')
    require(before.keys() == after.keys(), 'External paths changed')
    changed = [name for name in before if before[name] != after[name]]
    require(changed == ['HOMEBREW/launcher/app'] == report['external_changed_paths'],
            'Unexpected external changes')
    launcher = area / 'external/HOMEBREW/launcher/app'
    require(sha(launcher) == report['launcher_sha256']
            and launcher.stat().st_size == report['launcher_after_bytes'], 'Launcher mismatch')
    require(report['system_growth_from_base_bytes'] == 0, 'System growth mismatch')
    print(json.dumps({'passed': True, 'checksums_verified': len(seen),
                      'upg_identical_to_base': True, 'changed': changed,
                      'external_growth_bytes': launcher.stat().st_size
                      - (base / 'external/HOMEBREW/launcher/app').stat().st_size,
                      'ready_to_flash': False}, indent=2))


if __name__ == '__main__':
    main()
