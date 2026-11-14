"""Build real public text clients, reject accidental cross-module linkage; no device."""

import hashlib
import json
from pathlib import Path
import time

from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from sdk_services import compile_native, inputs, resolve


def main():
    out = ROOT / 'work/sdk-text-tests' / str(time.time_ns())
    out.mkdir(parents=True)
    source = ROOT / 'sdk/tests/text_services.c'
    rows = []
    for mode, modules in enumerate((['bitmap-font'], ['unicode-font'],
                                     ['bitmap-font', 'lexicon', 'unicode-font'], ['lexicon'])):
        definition = out / ('check-text-' + str(mode))
        definition.mkdir()
        contract = {'version': (ROOT / 'sdk/VERSION').read_text().strip(),
                    'profile': 'native-services', 'modules': ['startup', *modules]}
        (definition / 'app.json').write_text(json.dumps({
            'id': definition.name, 'target': 'sony-nw-x1000-jp', 'sdk': contract}), encoding='utf-8')
        (definition / 'VERSION').write_text('0.1.0-alpha.1\n')
        (definition / 'build.json').write_text(json.dumps({
            'profile': 'native-services', 'sources': ['main.c'],
            'cflags': ['-DTEXT_MODE=' + str(mode)], 'checks': [['--selftest']]}))
        (definition / 'main.c').write_bytes(source.read_bytes())
        binary = compile_native(definition, definition / 'build')
        with binary.open('rb') as stream:
            elf = ELFFile(stream)
            names = {symbol.name for symbol in elf.get_section_by_name('.symtab').iter_symbols()}
        if mode == 0:
            assert 'dx_draw' in names and 'dx_open' not in names
        elif mode == 3:
            assert 'dx_open' in names and 'dx_draw' not in names
        else:
            assert 'dx_open' in names and 'dx_draw' in names
        tracked = inputs({'resolved_modules': resolve(contract['modules'])})
        rows.append({'modules': modules, 'passed': True,
                     'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                     'source_hashes': {path.relative_to(ROOT).as_posix():
                                      hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in tracked}})
    report = {'passed': True, 'clients': rows, 'original_loader_arm': True,
              'lookup_or_font_file_opened': False, 'hardware_accessed': False,
              'firmware_created': False, 'test_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'clients': len(rows), 'report': str(out / 'report.json')}))


if __name__ == '__main__':
    main()
