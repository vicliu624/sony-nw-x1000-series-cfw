"""Decode an explicit local JPEG with local M5GFX sources. PC only; no MCU build."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from app_registry import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--decoder-dir', required=True, type=Path,
                        help='Local M5GFX src/lgfx/utility directory; no download is attempted')
    args = parser.parse_args()
    picture = args.image.resolve()
    decoder = args.decoder_dir.resolve()
    implementation, header = decoder / 'lgfx_tjpgd.c', decoder / 'lgfx_tjpgd.h'
    if not implementation.is_file() or not header.is_file():
        parser.error('Missing explicit local M5GFX JPEG sources')
    data = picture.read_bytes()
    if not 3 <= len(data) <= 524288 or not data.startswith(b'\xff\xd8\xff'):
        parser.error('Expected an extracted JPEG within the remote compressed-image limit')
    out = ROOT / 'work/core2-jpeg-compat' / str(time.time_ns())
    out.mkdir(parents=True, exist_ok=False)
    fixture = ROOT / 'tools/fixtures/core2_jpeg_compat.c'
    flags = ['gcc-12', '-std=c99', '-O1', '-fsanitize=address', '-I' + str(decoder)]
    objects = []
    for index, source in enumerate((fixture, implementation)):
        target = out / (str(index) + '.o')
        warnings = ['-Wall', '-Wextra', '-Werror'] if source == fixture else []
        subprocess.run([*flags, *warnings, '-c', str(source), '-o', str(target)], check=True)
        objects.append(str(target))
    binary = out / 'decoder.host'
    subprocess.run(['gcc-12', '-fsanitize=address', *objects, '-o', str(binary)], check=True)
    run = subprocess.run([str(binary), str(picture)], capture_output=True, text=True, timeout=20)
    (out / 'decoder.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    try:
        result = json.loads(run.stdout)
    except ValueError:
        result = {'exit_code': run.returncode}
    passed = (run.returncode == 0 and result.get('prepare') == 0 and
              result.get('decode') == 0 and result.get('pixels', 0) > 0)
    report = dict(passed=passed, decoder=result, host_address_sanitizer=True,
                  picture_bytes=len(data), picture_sha256=hashlib.sha256(data).hexdigest(),
                  codec_sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (implementation, header)},
                  fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                  firmware_created=False, device_accessed=False,
                  limits=['Codec/pool/division match the current JPEG path; final affine RGB565 sprite and LCD are not exercised.',
                          'Local vendor source identity is recorded; this is not complete Core2 or PNG qualification.'])
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('Report:', out / 'report.json')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
