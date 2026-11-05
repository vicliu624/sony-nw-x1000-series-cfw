"""Measure a reviewed UPG in a local copy of the populated stock ext2 model."""
import argparse
import io
import json
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path

from app_registry import ROOT
from prepare_managed_firmware_review import unpack
from review_managed_remote_profile import digest, private, receipt
from review_managed_root_capacity import inventory


def stats(path):
    with path.open('rb') as image:
        image.seek(1024)
        header = image.read(1024)
    assert struct.unpack_from('<H', header, 56)[0] == 0xef53
    inodes, blocks, reserved, free, free_inodes = struct.unpack_from('<5I', header)
    block = 1024 << struct.unpack_from('<I', header, 24)[0]
    assert block == 4096 and path.stat().st_size == blocks * block
    return dict(used_bytes=(blocks-free)*block, available_bytes=(free-reserved)*block,
                free_inodes=free_inodes, inode_count=inodes, image_bytes=blocks*block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--firmware-review')
    inputs.add_argument('--accepted-baseline', action='store_true',
                        help='Measure the pinned earlier Homebrew hardware-test package')
    args = parser.parse_args()
    if args.accepted_baseline:
        firmware = private('work/managed-firmware-review/1793817320395206222/DIAGNOSTIC-REVIEW-ONLY.UPG')
        expected = '0b5ede45ef0703bfdcff75a9fc1531c99f697c5e4d904a782294dd64b9516a49'
    else:
        _, review = receipt(args.firmware_review)
        firmware = private(review['artifact'])
        expected = review['sha256']
        assert review['final_root_inventory_verified']
    assert digest(firmware) == expected
    stock_root = private('work/upg-jp/verified-3.bin')
    assert digest(stock_root) == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
    stock = inventory(stock_root.read_bytes())
    _, parts = unpack(firmware.read_bytes(), require_stock=False)
    candidate = inventory(parts[3])
    model = json.loads((ROOT/'sources/native-stock-ext2-population.json').read_text())['profiles'][0]
    source = private(model['image'])
    before = stats(source)
    assert before['used_bytes'] == model['used_bytes']
    assert before['available_bytes'] == model['available_nonreserved_bytes']
    out = Path(tempfile.mkdtemp(prefix='reviewed-ext2-', dir=ROOT/'work'))
    image = out/'candidate.img'
    shutil.copyfile(source, image)
    commands, files = [], []
    changed = sorted(k for k in stock.keys() | candidate.keys() if stock.get(k) != candidate.get(k))
    with tarfile.open(fileobj=io.BytesIO(parts[3]), mode='r:gz') as archive:
        for name in sorted(changed, key=lambda k: (k.count('/'), k)):
            assert re.fullmatch(r'[A-Za-z0-9_./-]+', name)
            previous, current = stock.get(name), candidate.get(name)
            assert current and current['kind'] in ('directory', 'file')
            target = '/'+name
            if current['kind'] == 'directory':
                assert previous is None
                commands.append('mkdir '+target)
                kind = 0o40000
            else:
                assert previous is None or previous['kind'] == 'file'
                if previous:
                    commands.append('rm '+target)
                path = out/f'input-{len(files)}'
                path.write_bytes(archive.extractfile('./'+name).read())
                assert digest(path) == current['sha256']
                commands.append(f'write "{path}" {target}')
                if current['bytes']:
                    commands.append(f"fallocate {target} 0 {(current['bytes']-1)//4096}")
                files.append((target, current))
                kind = 0o100000
            commands.extend(f'set_inode_field {target} {field} {value}' for field, value in
                            [('mode', oct(kind | current['mode']).replace('0o','0')),
                             ('uid', current['uid']), ('gid', current['gid'])])

    def run(command, log):
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (out/log).write_text(result.stdout+result.stderr)
        assert result.returncode == 0, result.stderr[-2000:]
        return result

    script = out/'populate.commands'
    script.write_text('\n'.join(commands)+'\n')
    result = run(['debugfs','-w','-f',str(script),str(image)], 'populate.log')
    assert not re.search(r'Could not|not found|No space|Usage:|while (writing|allocating|creating|opening)', result.stderr, re.I)
    run(['e2fsck','-f','-n',str(image)], 'fsck.log')
    script = out/'verify.commands'
    script.write_text(''.join(f'dump {target} "{out/f"readback-{i}"}"\n' for i,(target,_) in enumerate(files)))
    run(['debugfs','-f',str(script),str(image)], 'verify.log')
    for i,(target,row) in enumerate(files):
        assert digest(out/f'readback-{i}') == row['sha256'], target
    after = stats(image)
    result = dict(passed=True, firmware_sha256=expected, model_before=before, model_after=after,
                  added_allocated_bytes=after['used_bytes']-before['used_bytes'],
                  changed_paths=len(changed), verified_files=len(files), readonly_fsck_exit=0,
                  device_accessed=False, physical_capacity_verified=False,
                  model_source_sha256=digest(source), tool_sha256=digest(Path(__file__)))
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(), **result),indent=2))


if __name__ == '__main__':
    main()
