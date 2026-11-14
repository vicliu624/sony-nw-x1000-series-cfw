"""Load a source-bound system overlay for a PC guest, without producing a UPG."""
import hashlib
import io
from pathlib import PurePosixPath
import stat
import tarfile
from app_registry import ROOT
from review_managed_remote_profile import receipt, digest
from review_managed_root_capacity import read_localization_root


def read_overlay(directory, rows):
    directory = directory.resolve()
    result = {}
    for name, row in rows.items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != name or '\\' in name:
            raise ValueError('Invalid guest overlay path: ' + name)
        source = directory / name
        if not source.resolve().is_relative_to(directory):
            raise ValueError('Guest overlay escapes its directory')
        parents = [source, *[directory.joinpath(*path.parts[:i]) for i in range(1, len(path.parts))]]
        if any(p.is_symlink() for p in parents):
            raise ValueError('Guest overlay contains a redirected path')
        info = source.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != row['bytes']:
            raise ValueError('Guest overlay file size/type changed: ' + name)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Guest overlay hash changed: ' + name)
        mode = int(row['mode'], 8)
        if mode & ~0o7777:
            raise ValueError('Invalid guest file mode')
        result[name] = (data, mode)
    return result


def load_layout(path):
    layout_path, layout = receipt(path)
    if not (layout.get('prepared') and layout.get('analysis_only') and
            layout.get('player_copies_in_final_layout') == 1 and not layout.get('firmware_created')):
        raise ValueError('Expected a single-player source analysis layout')
    host = layout['host_build']
    for name, sha in host['source_hashes'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Stale guest host source: ' + name)
    source, localized_root, source_sha = read_localization_root(layout)
    overlay_root = layout_path.parent / 'root-overlay'
    overlay = read_overlay(overlay_root, layout['files'])
    if hashlib.sha256(overlay['usr/local/lib/libx1000-player.so'][0]).hexdigest() != host['library_sha256']:
        raise ValueError('Guest library differs from the host composition')
    if hashlib.sha256(overlay[layout['player_payload_path']][0]).hexdigest() != host['candidate_sha256']:
        raise ValueError('Guest player differs from the host composition')
    with tarfile.open(fileobj=io.BytesIO(localized_root), mode='r:gz') as archive:
        app_list = overlay['etc/AppList.conf'][0] if 'etc/AppList.conf' in overlay else archive.extractfile('./etc/AppList.conf').read()
    metadata = {'layout_review': layout_path.relative_to(ROOT).as_posix(),
                'layout_sha256': digest(layout_path), 'localization_input_sha256': source_sha,
                'player_sha256': host['candidate_sha256'], 'library_sha256': host['library_sha256'],
                'firmware_created': False, 'device_accessed': False,
                'source_hashes': {**layout['source_hashes'], **host['source_hashes']}}
    inputs = [layout_path, source, *[overlay_root / name for name in overlay]]
    if 'localization_input' in layout:
        metadata['source_firmware_sha256'] = source_sha
    return localized_root, app_list, overlay, metadata, inputs
