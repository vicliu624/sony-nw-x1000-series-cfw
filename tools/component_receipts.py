"""Validate local build receipts and their exact recorded inputs."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = (ROOT / 'work').resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if path.is_symlink():
        raise ValueError('Receipt/artifact must not be a symlink')
    path = path.resolve()
    if not path.is_relative_to(WORK) or not path.is_file():
        raise ValueError('Expected existing private work input')
    return path


def receipt(path):
    path = private(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    for name, expected in data['source_hashes'].items():
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file() or digest(source) != expected:
            raise ValueError('Stale source/input: ' + name)
    return path, data


def artifact(path, expected, size):
    path = private(path)
    if path.stat().st_size != size or digest(path) != expected:
        raise ValueError('Artifact identity mismatch: ' + path.name)
    return dict(local=path.relative_to(ROOT).as_posix(), bytes=size, sha256=expected)


def native_sdk_build(path):
    path, build = receipt(path)
    archive = path.parent / 'lib/libxnow.a'
    if path.name != 'build.json' or build.get('built') is not True:
        raise ValueError('Expected a native ESP-NOW SDK build receipt')
    identity = artifact(archive, build['archive_sha256'], build['archive_bytes'])
    for name, expected in build.get('abi_library_hashes', {}).items():
        if digest(private((ROOT / name).resolve())) != expected:
            raise ValueError('Native SDK ABI library changed: ' + name)
    return path, ROOT / identity['local'], build


def validate_linked_inputs(built):
    for key in ('linked_input_hashes', 'linked_library_hashes'):
        for name, expected in built.get(key, {}).items():
            linked = (ROOT / name.replace('\\', '/')).resolve()
            if digest(private(linked)) != expected:
                raise ValueError('Component linked input differs: ' + name)


def component_build(path, leaf):
    path, built = receipt(path)
    if (path.name != 'build.json' or built.get('built') is not True or
            not isinstance(built.get('artifact'), str)):
        raise ValueError('Component build receipt differs: ' + leaf)
    executable = private(built['artifact'])
    if executable != path.parent / leaf:
        raise ValueError('Component build receipt differs: ' + leaf)
    validate_linked_inputs(built)
    return path, built, artifact(executable, built['sha256'], built['bytes'])
