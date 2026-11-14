"""Measure a reviewed root layout in ordinary PC files using Sony's ext2 formatter.

No image is mounted. No UPG, updater, physical device or installation is involved.
Host debugfs population is a capacity model, not Sony tar/kernel qualification.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile

from elftools.elf.elffile import ELFFile

from review_managed_remote_profile import ROOT, WORK, digest, private, receipt
from review_managed_root_capacity import compose_root_inventory, inventory

sys.path.insert(0, str(ROOT / 'scripts'))
from upg import unpack

STOCK_ROOT_SHA256 = 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
NAND_MODULE_SHA256 = '3263ab460d48160549dba1c67d96a9a76ee47ff93281d061a6c663b1c191cdd9'
BLOCK_BYTES = 4096
IMAGE_BYTES = 148 * 1048576
ENVIRONMENT = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LC_ALL': 'C', 'TZ': 'UTC'}


def quote(value):
    value = str(value)
    if any(char in value for char in ('"', '\\', '\n', '\r', '\0')):
        raise ValueError('Unsafe debugfs argument: ' + repr(value))
    return '"' + value + '"'


def validate_tree(rows):
    for name, row in rows.items():
        if (not name or name in ('.', '..') or name.startswith('/') or
                PurePosixPath(name).as_posix() != name or '..' in PurePosixPath(name).parts):
            raise ValueError('Noncanonical root path: ' + repr(name))
        quote(name)
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and rows.get(str(parent), {}).get('kind') != 'directory':
                raise ValueError('Missing/non-directory ancestor: ' + name)
        if row['kind'] not in ('file', 'directory', 'symlink'):
            raise ValueError('Unsupported archive object: ' + name)
        if row['kind'] == 'symlink':
            quote(row['target'])
            # This tool independently checks fast symlinks. Refuse other formats.
            if not row['target'] or len(row['target'].encode()) >= 60:
                raise ValueError('Unsupported long/empty symlink: ' + name)


def superblock_stats(raw, image_bytes):
    if len(raw) != 1024 or struct.unpack_from('<H', raw, 56)[0] != 0xef53:
        raise ValueError('Invalid ext2 superblock')
    inodes, blocks, reserved, free, free_inodes = struct.unpack_from('<5I', raw)
    block_bytes = 1024 << struct.unpack_from('<I', raw, 24)[0]
    if (block_bytes != BLOCK_BYTES or blocks * block_bytes != image_bytes or
            struct.unpack_from('<H', raw, 88)[0] != 128 or
            struct.unpack_from('<3I', raw, 92) != (0, 2, 1)):
        raise ValueError('Unexpected stock filesystem geometry/features')
    if not (0 <= reserved <= free <= blocks and 0 <= free_inodes <= inodes):
        raise ValueError('Invalid/exhausted filesystem accounting')
    return dict(block_bytes=block_bytes, total_blocks=blocks, inode_count=inodes,
                used_inodes=inodes - free_inodes, used_bytes=(blocks - free) * block_bytes,
                free_bytes=free * block_bytes, reserved_bytes=reserved * block_bytes,
                available_nonreserved_bytes=(free - reserved) * block_bytes)


def verify_inode(text, name, row, mtime):
    kind = dict(file='regular', directory='directory', symlink='symlink')[row['kind']]
    header = re.search(r'Type:\s*(\w+)\s+Mode:\s*([0-7]+)', text)
    owner = re.search(r'User:\s*(\d+)\s+Group:\s*(\d+)\s+Size:\s*(\d+)', text)
    stamp = re.search(r'mtime:\s*0x([0-9a-fA-F]+)', text)
    if (not header or header[1] != kind or int(header[2], 8) != row['mode'] or
            not owner or (int(owner[1]), int(owner[2])) != (row['uid'], row['gid']) or
            not stamp or int(stamp[1], 16) != mtime):
        raise ValueError('Inode metadata mismatch: ' + name)
    if row['kind'] == 'file' and int(owner[3]) != row['bytes']:
        raise ValueError('Inode size mismatch: ' + name)
    if row['kind'] == 'symlink':
        target = re.search(r'^Fast link dest: "([^"]*)"$', text, re.M)
        if not target or target[1] != row['target']:
            raise ValueError('Symlink target mismatch: ' + name)


def archive_inputs(raw):
    rows = inventory(raw)
    validate_tree(rows)
    data, times, root = {}, {}, None
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            name = member.name.removeprefix('./').rstrip('/')
            if name in ('', '.'):
                if not member.isdir() or root is not None:
                    raise ValueError('Ambiguous archive root')
                root = dict(kind='directory', bytes=0, mode=member.mode,
                            uid=member.uid, gid=member.gid, mtime=int(member.mtime))
                continue
            times[name] = int(member.mtime)
            if member.isfile():
                data[name] = archive.extractfile(member).read()
    if any(not 0 <= value <= 0xffffffff for value in times.values()):
        raise ValueError('Unsupported timestamp range')
    return rows, data, times, root


def partition_definition(data):
    raw = data['lib/modules/icx1087-nand-p.ko']
    if hashlib.sha256(raw).hexdigest() != NAND_MODULE_SHA256:
        raise ValueError('Unqualified NAND partition module')
    elf = ELFFile(io.BytesIO(raw))
    table = elf.get_section_by_name('.symtab').get_symbol_by_name('icx1087_nand_fixed_size_partitions')
    if not table or len(table) != 1 or table[0]['st_size'] != 32:
        raise ValueError('Unexpected partition table')
    symbol = table[0]
    entry = elf.get_section(symbol['st_shndx']).data()[symbol['st_value']:symbol['st_value'] + 32]
    size, offset = struct.unpack_from('<QQ', entry, 4)
    if size != IMAGE_BYTES or offset != 0:
        raise ValueError('Unexpected static root definition')
    return dict(module_sha256=NAND_MODULE_SHA256, definition_bytes=size,
                actual_physical_geometry_verified=False)


def verify_formatter(sysroot, stock_data):
    """Pin the formatter, ELF interpreter and recursive DT_NEEDED closure to Sony."""
    root = sysroot.resolve()
    if not root.is_relative_to(WORK) or not root.is_dir():
        raise ValueError('Expected prepared private Sony sysroot')
    pending = [root / 'bin/busybox']
    verified = {}
    while pending:
        path = pending.pop().resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Formatter dependency escapes sysroot')
        name = path.relative_to(root).as_posix()
        if name in verified:
            continue
        raw = path.read_bytes()
        if stock_data.get(name) != raw:
            raise ValueError('Formatter dependency differs from stock: ' + name)
        verified[name] = hashlib.sha256(raw).hexdigest()
        elf = ELFFile(io.BytesIO(raw))
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_INTERP':
                pending.append(root / segment.get_interp_name().lstrip('/'))
            if segment['p_type'] == 'PT_DYNAMIC':
                for tag in segment.iter_tags():
                    if tag.entry.d_tag != 'DT_NEEDED':
                        continue
                    choices = [root / folder / tag.needed for folder in ('lib', 'usr/lib')]
                    found = next((candidate for candidate in choices if candidate.is_file()), None)
                    if found is None:
                        raise ValueError('Missing Sony library: ' + tag.needed)
                    pending.append(found)
    return verified


def run(command, log, timeout=180):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                            errors='strict', timeout=timeout, env=ENVIRONMENT)
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('Local model command failed; see ' + str(log))
    if re.search(r'(Could not|not found|No space|Usage:|while (?:writing|allocating|creating|opening))',
                 result.stderr, re.I):
        raise ValueError('debugfs rejected operation; see ' + str(log))
    return result.stdout


def populate(area, profile, rows, data, times, root_metadata, sysroot):
    image = area / (profile + '.img')
    with image.open('xb') as stream:
        stream.truncate(IMAGE_BYTES)
    if image.is_symlink() or not stat.S_ISREG(image.stat().st_mode):
        raise ValueError('Model must be a new ordinary file')
    mkfs = ['qemu-arm', '-cpu', 'arm926', '-L', str(sysroot), str(sysroot / 'bin/busybox'),
            'mke2fs', '-F', '-b', str(BLOCK_BYTES), str(image)]
    run(mkfs, area / (profile + '-mkfs.log'))
    payloads = area / (profile + '-payloads')
    payloads.mkdir()
    commands, regular = [], []
    for name in sorted((name for name, row in rows.items() if row['kind'] == 'directory'),
                       key=lambda name: (name.count('/'), name)):
        if name != 'lost+found':
            commands.append('mkdir ' + quote('/' + name))
    for name, row in sorted(rows.items()):
        target = quote('/' + name)
        if row['kind'] == 'file':
            source = payloads / str(len(regular))
            source.write_bytes(data[name])
            commands.append('write ' + quote(source) + ' ' + target)
            blocks = (row['bytes'] + BLOCK_BYTES - 1) // BLOCK_BYTES
            if blocks:
                commands.append('fallocate ' + target + ' 0 ' + str(blocks - 1))
            regular.append(name)
        elif row['kind'] == 'symlink':
            commands.append('symlink ' + target + ' ' + quote(row['target']))
    metadata = dict(rows)
    if root_metadata:
        metadata[''] = root_metadata
    for name, row in sorted(metadata.items()):
        kind = dict(file=stat.S_IFREG, directory=stat.S_IFDIR, symlink=stat.S_IFLNK)[row['kind']]
        stamp = times[name] if name else root_metadata['mtime']
        for field, value in (('mode', '0' + format(kind | row['mode'], 'o')),
                             ('uid', row['uid']), ('gid', row['gid']),
                             ('mtime', '0x' + format(stamp, 'x'))):
            commands.append('set_inode_field ' + quote('/' + name) + ' ' + field + ' ' + str(value))
    script = area / (profile + '-populate.commands')
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    run(['/usr/sbin/debugfs', '-w', '-f', str(script), str(image)], area / (profile + '-populate.log'))
    run(['/usr/sbin/e2fsck', '-f', '-n', str(image)], area / (profile + '-fsck.log'))
    verify = area / (profile + '-readback')
    verify.mkdir()
    checks = ['dump ' + quote('/' + name) + ' ' + quote(verify / str(index))
              for index, name in enumerate(regular)]
    checks.extend('stat ' + quote('/' + name) for name in sorted(metadata))
    script = area / (profile + '-verify.commands')
    script.write_text('\n'.join(checks) + '\n', encoding='utf-8')
    output = run(['/usr/sbin/debugfs', '-f', str(script), str(image)], area / (profile + '-verify.log'))
    for index, name in enumerate(regular):
        actual = verify / str(index)
        if not actual.is_file() or actual.stat().st_size != rows[name]['bytes'] or digest(actual) != rows[name]['sha256']:
            raise ValueError('Regular content readback mismatch: ' + name)
    blocks = re.split(r'^debugfs:\s+stat "([^"\n]*)"\s*$', output, flags=re.M)
    if len(blocks) != 1 + 2 * len(metadata):
        raise ValueError('Incomplete metadata readback')
    for name, text in zip(blocks[1::2], blocks[2::2]):
        key = name.removeprefix('/')
        stamp = times[key] if key else root_metadata['mtime']
        verify_inode(text, key or '/', metadata[key], stamp)
    with image.open('rb') as stream:
        stream.seek(1024)
        result = superblock_stats(stream.read(1024), image.stat().st_size)
    result.update(profile=profile, image=image.relative_to(ROOT).as_posix(), image_sha256=digest(image),
                  image_bytes=image.stat().st_size, verified_regular_files=len(regular),
                  verified_inodes=len(metadata), dense_regular_file_blocks=True,
                  readonly_fsck_exit=0, formatter_command=mkfs)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capacity-review', type=Path, required=True)
    parser.add_argument('--sysroot', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'posix':
        raise ValueError('Run in the prepared Linux/WSL environment')
    capacity_path, capacity = receipt(args.capacity_review)
    layout_path, layout = receipt(capacity['layout_review'])
    if (not capacity['passed'] or not layout['prepared'] or not layout['analysis_only'] or
            layout['player_copies_in_final_layout'] != 1 or
            digest(layout_path) != capacity['layout_review_sha256']):
        raise ValueError('Expected a matching complete analysis layout')
    stock_path = private('work/upg-jp/verified-3.bin')
    stock_raw = stock_path.read_bytes()
    if hashlib.sha256(stock_raw).hexdigest() != STOCK_ROOT_SHA256:
        raise ValueError('Original Sony root differs')
    stock, stock_data, stock_times, stock_root = archive_inputs(stock_raw)
    firmware = private(layout['localization_input'])
    if digest(firmware) != layout['localization_input_sha256'] or digest(firmware) != capacity['localization_sha256']:
        raise ValueError('Localization input differs')
    _, parts = unpack(firmware.read_bytes(), require_stock=False)
    base, data, times, root_metadata = archive_inputs(parts[3])
    candidate = compose_root_inventory(base, layout['files'])
    validate_tree(candidate)
    inputs = {path.relative_to(ROOT).as_posix(): digest(path)
              for path in (capacity_path, layout_path, stock_path, firmware)}
    for name, row in layout['files'].items():
        path = private(layout_path.parent / 'root-overlay' / name)
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Overlay input changed: ' + name)
        inputs[path.relative_to(ROOT).as_posix()] = row['sha256']
        data[name] = raw
    for name in candidate:
        times.setdefault(name, 0)
    changes = {name: candidate.get(name) for name in stock.keys() | candidate.keys()
               if stock.get(name) != candidate.get(name)}
    if changes != {row['path']: row['candidate'] for row in capacity['changed_paths']}:
        raise ValueError('Full inventory differs from capacity review')
    definition = partition_definition(stock_data)
    sysroot = args.sysroot.resolve()
    formatter = verify_formatter(sysroot, stock_data)
    area = Path(tempfile.mkdtemp(prefix='layout-ext2-', dir=WORK))
    source_paths = ('tools/measure_layout_ext2.py', 'tools/review_managed_root_capacity.py',
                    'tools/review_managed_remote_profile.py', 'scripts/upg.py', 'scripts/upg_crypto.py')
    sources = {name: digest(ROOT / name) for name in source_paths}
    report = dict(passed=False, analysis_only=True, ready_to_flash=False,
                  device_accessed=False, firmware_created=False, physical_margin_verified=False,
                  capacity_review=capacity_path.relative_to(ROOT).as_posix(),
                  capacity_review_sha256=digest(capacity_path), partition_definition=definition,
                  formatter_closure=formatter, source_hashes=sources, input_hashes=inputs, profiles=[],
                  limitations=['Ordinary local files only; no mount, UPG, updater or device access.',
                               'Sony mkfs runs in ARM user emulation; host debugfs substitutes for stock tar/kernel.',
                               'Static 148MiB definition does not qualify physical NAND geometry or bad-block behavior.',
                               'No RF, sleep/wake, USB, audio or installation qualification.'])
    try:
        report['profiles'].append(populate(area, 'stock', stock, stock_data, stock_times, stock_root, sysroot))
        report['profiles'].append(populate(area, 'candidate', candidate, data, times, root_metadata, sysroot))
        report['used_growth_bytes'] = report['profiles'][1]['used_bytes'] - report['profiles'][0]['used_bytes']
        report['model_nonreserved_margin_bytes'] = report['profiles'][1]['available_nonreserved_bytes']
        if any(digest(ROOT / name) != value for name, value in sources.items()):
            raise ValueError('Measurement source changed during run')
        if any(digest(private(name)) != value for name, value in inputs.items()):
            raise ValueError('Measurement input changed during run')
        if verify_formatter(sysroot, stock_data) != formatter:
            raise ValueError('Formatter closure changed during run')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (area / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(dict(passed=report['passed'], report=(area / 'report.json').relative_to(ROOT).as_posix(),
                              used_growth_bytes=report.get('used_growth_bytes'),
                              model_nonreserved_margin_bytes=report.get('model_nonreserved_margin_bytes'),
                              physical_margin_verified=False, firmware_created=False)))


if __name__ == '__main__':
    main()
