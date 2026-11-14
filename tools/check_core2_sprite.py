"""Run the Core2 cover renderer with explicit local M5GFX sources on the PC."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from PIL import Image
from app_registry import ROOT


def cmake_path(path):
    value = path.as_posix()
    if any(character in value for character in ('"', '$', ';', '\n', '\r')):
        raise ValueError('Unsupported CMake path: ' + value)
    return '"' + value + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m5gfx-src', required=True, type=Path,
                        help='Existing M5GFX 0.2.32 src directory; never downloaded or modified')
    parser.add_argument('--image', type=Path, help='Optional extracted JPEG/PNG, kept local')
    args = parser.parse_args()
    vendor = args.m5gfx_src.resolve()
    identity = vendor.parent / 'library.json'
    if not identity.is_file() or json.loads(identity.read_text())['version'] != '0.2.32':
        parser.error('Use the same local M5GFX 0.2.32 source version as the Core2 profile')
    out = ROOT / 'work/core2-sprite' / str(time.time_ns())
    out.mkdir(parents=True)
    fixture = ROOT / 'tools/fixtures/core2_cover_sprite.cpp'
    renderer = ROOT / 'runtime/apps/wireless-remote/core2/src/cover_renderer.h'
    dimensions = ROOT / 'runtime/apps/wireless-remote/artwork_image.c'
    sources = [fixture, dimensions] + [vendor / name for name in (
        'lgfx/v1/lgfx_v1.cpp', 'lgfx/v1/lgfx_v1_panel.cpp',
        'lgfx/v1/lgfx_v1_platforms.cpp', 'lgfx/v1/LGFXBase.cpp', 'lgfx/v1/lgfx_fonts.cpp',
        'lgfx/Fonts/efont/lgfx_efont_cn.c', 'lgfx/Fonts/efont/lgfx_efont_ja.c',
        'lgfx/Fonts/efont/lgfx_efont_kr.c', 'lgfx/Fonts/efont/lgfx_efont_tw.c',
        'lgfx/Fonts/IPA/lgfx_font_japan.c', 'lgfx/utility/lgfx_miniz.c',
        'lgfx/utility/lgfx_pngle.c', 'lgfx/utility/lgfx_qoi.c', 'lgfx/utility/lgfx_tjpgd.c')]
    for source in sources:
        if not source.is_file():
            parser.error('Missing local source: ' + str(source))
    (out / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
project(core2_cover LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-O1 -ffunction-sections -fdata-sections)
add_link_options(-Wl,--gc-sections)
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL REQUIRED sdl2)
add_executable(cover
''' + '\n'.join(cmake_path(path) for path in sources) + '''
)
target_compile_definitions(cover PRIVATE LGFX_SDL)
target_include_directories(cover PRIVATE ''' + cmake_path(vendor) + ''' ${SDL_INCLUDE_DIRS})
target_link_libraries(cover PRIVATE ${SDL_LIBRARIES} pthread)
''', encoding='utf-8')
    inputs = set(sources) | {path for path in vendor.rglob('*') if path.is_file()} | {
        identity, renderer, Path(__file__), ROOT / 'runtime/apps/wireless-remote/artwork_image.h'}
    source_hashes = {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(inputs)}
    (out / 'input-hashes.json').write_text(json.dumps(source_hashes, indent=2) + '\n',
                                          encoding='utf-8')
    with (out / 'build.log').open('wb') as log:
        for command in (['cmake', '-S', str(out), '-B', str(out / 'build')],
                        ['cmake', '--build', str(out / 'build'), '-j2']):
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)

    cases = []
    for name, size, format in (('square', (32, 32), 'JPEG'),
                               ('landscape', (32, 24), 'PNG'),
                               ('portrait', (24, 48), 'JPEG')):
        path = out / (name + ('.png' if format == 'PNG' else '.jpg'))
        Image.new('RGB', size, (80, 120, 160)).save(path, format=format)
        cases.append((name, path, True, size, (80, 120, 160)))
    invalid = out / 'invalid.image'
    invalid.write_bytes(b'not an image')
    cases.append(('invalid', invalid, False, None, None))
    truncated = out / 'truncated.png'
    truncated.write_bytes((out / 'landscape.png').read_bytes()[:33])
    cases.append(('truncated', truncated, False, None, None))
    if args.image:
        picture = args.image.resolve()
        if not picture.is_file() or not 3 <= picture.stat().st_size <= 524288:
            parser.error('Expected an extracted image within the 512 KiB transport limit')
        copied_picture = out / 'explicit-local-image.input'
        copied_picture.write_bytes(picture.read_bytes())
        cases.append(('explicit-local-image', copied_picture, True, None, None))

    rows = []
    for name, path, expected, size, color in cases:
        run = subprocess.run([str(out / 'build/cover'), str(path), str(out / (name + '.ppm')),
                              '1' if expected else '0'], capture_output=True, text=True,
                             timeout=30, env=dict(os.environ, SDL_VIDEODRIVER='dummy'))
        (out / (name + '.log')).write_text(run.stdout + run.stderr, encoding='utf-8')
        if run.returncode:
            raise RuntimeError('Sprite case failed: ' + name + '; see ' + str(out))
        result = json.loads(run.stdout)
        assert result['decoded'] == expected
        if expected:
            assert result['copied'] == 9216 and result['outside'] == 67584
            if color:
                center = result['center_rgb']
                actual = ((center >> 16) & 255, (center >> 8) & 255, center & 255)
                assert max(abs(a - b) for a, b in zip(actual, color)) <= 12, (name, actual)
            if size and size[0] != size[1]:
                assert result['corner_rgb'] == result['background_rgb'], name
        rows.append(dict(case=name, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         input_bytes=path.stat().st_size, result=result))

    if any(hashlib.sha256(path.read_bytes()).hexdigest() != source_hashes[path.as_posix()]
           for path in inputs):
        raise RuntimeError('Renderer or vendor input changed during the check; see ' + str(out))
    report = dict(passed=True, cases=rows, firmware_created=False, device_accessed=False,
                  runtime_renderer_shared=True, color_depth=16, vendor_version='0.2.32',
                  source_hashes=source_hashes,
                  source_changed_during_run=False,
                  host_binary_sha256=hashlib.sha256((out / 'build/cover').read_bytes()).hexdigest(),
                  limits=['Software sprites and pixel copy only; no physical LCD, PSRAM, radio or timing qualification.',
                          'Local vendor sources are recorded; neither downloaded nor modified.'])
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'cases': len(rows), 'report': str(out / 'report.json'),
                      'firmware_created': False, 'device_accessed': False}, indent=2))


if __name__ == '__main__':
    main()
