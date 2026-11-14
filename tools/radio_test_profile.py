"""Select an explicitly reviewed radio ELF for instruction-only tests."""
import hashlib
import json
import sys
from pathlib import Path
from app_registry import ROOT
from generate_espnow_full_profile import render

def selected_radio():
    if '--radio-review' not in sys.argv:
        return None
    index = sys.argv.index('--radio-review')
    if index + 1 >= len(sys.argv):
        raise ValueError('--radio-review requires a local build directory')
    directory = Path(sys.argv[index + 1]).resolve()
    if not directory.is_relative_to((ROOT / 'work').resolve()):
        raise ValueError('Radio input must remain in work/')
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, expected in manifest['source_hashes'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale radio source: ' + name)
    payload = directory / 'radio.elf'
    if hashlib.sha256(payload.read_bytes()).hexdigest() != manifest['payload_elf_sha256']:
        raise ValueError('Radio ELF identity differs')
    render(directory)  # Independently reconstruct and cross-check the image/profile.
    return payload, manifest
