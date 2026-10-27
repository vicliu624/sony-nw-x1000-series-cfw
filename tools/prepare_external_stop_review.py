"""Copy the unchanged diagnostic UPG with a reviewed external launcher; PC only."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-local-review', action='store_true', required=True)
    parser.add_argument('--revision', type=int, default=6)
    args = parser.parse_args()
    if args.revision < 6:
        raise ValueError('Use a new revision >= 6')
    version = (ROOT / 'VERSION').read_text().strip()
    base = ROOT / 'dist' / version / 'diagnostic-review-5'
    out = ROOT / 'dist' / version / f'diagnostic-review-{args.revision}'
    if out.exists():
        raise FileExistsError(out)
    build_path = ROOT / 'work/launcher-stop-fix-review/build.json'
    build = json.loads(build_path.read_text())
    launcher = ROOT / build['artifact']
    if not build['passed'] or build['version'] != version or digest(launcher) != build['sha256']:
        raise ValueError('Launcher build mismatch')
    reports = [
        ROOT / 'work/unresponsive-app-regression/report.json',
        ROOT / 'work/native-full-loop-stop-fix/report.json',
        ROOT / 'work/posix-full-loop-stop-fix/report.json',
    ]
    for path in [build_path, *reports]:
        report = json.loads(path.read_text())
        if not report.get('passed', report.get('all_bounded_checks_passed', False)):
            raise ValueError(f'Failed report: {path}')
        for name, expected in report['source_hashes'].items():
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT) or digest(source) != expected:
                raise ValueError(f'Stale input: {name}')
    subprocess.run([sys.executable, 'tools/verify_compact_feedback_diagnostic.py',
                    str(base.relative_to(ROOT))], cwd=ROOT, check=True)
    # Never repack UPG or mutate the base. The only external change is launcher/app.
    shutil.copytree(base / 'firmware', out / 'firmware')
    shutil.copytree(base / 'external', out / 'external')
    old = base / 'external/HOMEBREW/launcher/app'
    target = out / 'external/HOMEBREW/launcher/app'
    shutil.copyfile(launcher, target)
    base_files = {p.relative_to(base / 'external'): digest(p)
                  for p in (base / 'external').rglob('*') if p.is_file()}
    new_files = {p.relative_to(out / 'external'): digest(p)
                 for p in (out / 'external').rglob('*') if p.is_file()}
    changed = [str(p) for p in base_files if base_files[p] != new_files.get(p)]
    if set(base_files) != set(new_files) or changed != ['HOMEBREW/launcher/app']:
        raise ValueError(f'Unexpected external changes: {changed}')
    upg_name = 'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
    if (base / upg_name).read_bytes() != (out / upg_name).read_bytes():
        raise ValueError('UPG changed')
    review = out / 'review'
    review.mkdir()
    shutil.copytree(base / 'review', review / 'base-candidate-5')
    evidence = {str(p.relative_to(ROOT)): digest(p) for p in [build_path, *reports]}
    for index, path in enumerate([build_path, *reports]):
        shutil.copyfile(path, review / f'{index}-{path.parent.name}.json')
    report = {
        'profile': 'external-stop-fix-local-review', 'version': version,
        'revision': args.revision, 'base_candidate': str(base.relative_to(ROOT)),
        'upg_sha256': digest(out / upg_name), 'upg_bytes': (out / upg_name).stat().st_size,
        'upg_byte_identical_to_base': True, 'system_growth_from_base_bytes': 0,
        'external_changed_paths': changed,
        'launcher_before_bytes': old.stat().st_size,
        'launcher_after_bytes': target.stat().st_size,
        'launcher_sha256': digest(target), 'evidence': evidence,
        'ready_to_flash': False, 'device_written': False, 'hardware_tested': False,
    }
    (review / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    for language, title in [('', 'Local external-launcher review — do not install'),
                            ('.zh-CN', '本地外部启动器修正候选：暂不安装')]:
        (out / f'REVIEW{language}.md').write_text(
            (ROOT/'docs/STATUS.md').read_text(encoding='utf-8'), encoding='utf-8')
    (out / 'SHA256SUMS').write_text(''.join(
        digest(p) + '  ' + p.relative_to(out).as_posix() + '\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
