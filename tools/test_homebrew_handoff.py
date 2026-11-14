"""Test the bounded JP Homebrew switch-mode composition on an explicit image."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from elftools.elf.elffile import ELFFile
from elftools.common.exceptions import ELFError
from app_registry import ROOT
from homebrew_handoff import compose, MODE_INSTRUCTION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    source = args.input.resolve()
    if args.input.is_symlink() or not source.is_relative_to(ROOT / 'work') or not source.is_file():
        raise ValueError('Use an explicit local analysis image under work')
    raw = source.read_bytes()
    changed, report = compose(raw)
    elf = ELFFile(io.BytesIO(raw))
    segment = next(s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'
                   and s['p_vaddr'] <= MODE_INSTRUCTION < s['p_vaddr'] + s['p_filesz'])
    offset = segment['p_offset'] + MODE_INSTRUCTION - segment['p_vaddr']
    assert [i for i, (a, b) in enumerate(zip(raw, changed)) if a != b] == [offset]
    assert changed[offset:offset + 4] == bytes.fromhex('0030a0e3')
    assert ELFFile(io.BytesIO(changed)).header == elf.header
    assert [dict(s.header) for s in ELFFile(io.BytesIO(changed)).iter_segments()] == [dict(s.header) for s in elf.iter_segments()]
    cases = ['exact-mode-edit', 'elf-layout-preserved']
    corrupt = bytearray(raw)
    corrupt[offset - 4] ^= 1
    for name, invalid in [('already-composed', changed), ('changed-adapter', bytes(corrupt)),
                          ('invalid-elf', bytes(52))]:
        try:
            compose(invalid)
        except (ValueError, AssertionError, ELFError):
            cases.append(name + '-refused')
        else:
            raise AssertionError(name + ' accepted')
    out = ROOT / 'work/homebrew-handoff-tests' / str(time.time_ns())
    out.mkdir(parents=True)
    (out / 'report.json').write_text(json.dumps({'passed': True, 'cases': cases,
        'input_sha256': hashlib.sha256(raw).hexdigest(), 'composition': report,
        'device_accessed': False, 'firmware_created': False}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'cases': cases, 'report': (out / 'report.json').relative_to(ROOT).as_posix()}, indent=2))


if __name__ == '__main__':
    main()
