"""Check the built-in localization/player SDK composition offline; no UPG."""
import hashlib
import io
import json
import re
import struct
import time
import contextlib,runpy,sys

from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_player_host import patch_owner_anchor
from build_player_met_anchor import patch_met_anchor
from player_prepare_bridge import patch_prepare_bridge, PREPARE_BRIDGE, prepare_bridge
from build_home_feedback import build as home_build
from builtin_language import enable_settings

BASE_SHA = '4ca0755d3fe3322cf14c60ccbc456a344d5293e1cbd59665a1c2b9ebd11bbbd8'
native_settings_profile=bool(globals().get('native_settings_profile',False) or '--native-settings' in sys.argv)
profile='native-settings' if native_settings_profile else 'builtin-language'
out = ROOT / ('work/native-settings-player-composition' if native_settings_profile else 'work/builtin-player-composition') / str(time.time_ns())
out.mkdir(parents=True)

def offset(raw, address, count):
    elf = ELFFile(io.BytesIO(raw))
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'
                and s['p_vaddr'] <= address
                and address + count <= s['p_vaddr'] + s['p_filesz']]
    assert len(segments) == 1
    s = segments[0]
    return int(s['p_offset'] + address - s['p_vaddr'])

if native_settings_profile:
    with contextlib.redirect_stdout(io.StringIO()):settings_composition=runpy.run_path(str(ROOT/'tools/prepare_remote_settings_row.py'))
    base=settings_composition['artifact'].read_bytes();home_report=settings_composition['home_report']
    BASE_SHA='0dbd8c94e1502173faa52bb96394ae9bcfdbb55e74b496e4a42eed95589d2ea3'
else:
    home, symbols, home_report = home_build(out / 'home')
    editable = bytearray(home)
    descriptor = offset(home, symbols['hb_error_descriptor'], 48)
    struct.pack_into('<I', editable, descriptor + 4, 99999)
    struct.pack_into('<I', editable, descriptor + 20, 0)
    base = enable_settings(bytes(editable))
assert hashlib.sha256(base).hexdigest() == BASE_SHA

owner, owner_edit = patch_owner_anchor(base)
combined, met_edit = patch_met_anchor(owner, mapped_stub=0x4d7ff0)
checks = []
for path in sorted((ROOT / 'runtime/platform/player').glob('stock_*.c')):
    text = path.read_text(encoding='utf-8')
    arrays = [(m.start(), m.group(1), bytes(int(v, 16) for v in
              re.findall(r'0x([0-9a-fA-F]+)', m.group(2))))
              for m in re.finditer(r'(\w+)\[32\]\s*=\s*\{([^}]+)\}', text)]
    calls = [(*m.groups(), m.start()) for m in re.finditer(
        r'xw_stock_image_match\(\s*(0x[0-9a-fA-F]+)u?\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*(\w+)\s*\)', text)]
    if path.name == 'stock_volume.c':
        constants = dict(re.findall(r'#define\s+(REGION_\w+)\s+(0x[0-9a-fA-F]+)u?', text))
        calls.append((constants['REGION_BEGIN'], hex(int(constants['REGION_END'], 16)
                      - int(constants['REGION_BEGIN'], 16)), 'expected', len(text)))
    for start, length, name, position in calls:
        expected = next(value for at, ident, value in reversed(arrays)
                        if ident == name and at < position)
        address, count = int(start, 16), int(length, 16)
        at = offset(owner, address, count)
        assert len(expected) == 32
        assert hashlib.sha256(owner[at:at + count]).digest() == expected, path.name
        checks.append(dict(source=path.relative_to(ROOT).as_posix(), address=start, bytes=count))
assert len(checks) >= 17
pre_prepare = combined
stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
combined, prepare_edit = patch_prepare_bridge(combined, stock, profile=profile)
# Restore all declared SDK edits: the full result must equal the language base.
restored = bytearray(combined)
for address, count in ((0xff3c, 4), (0x27c610, 4), (0x4d7ff0, 16),
                       (0x718e0, 4), (0x71aa4, 4),
                       (PREPARE_BRIDGE, len(prepare_bridge()))):
    at = offset(base, address, count)
    restored[at:at + count] = base[at:at + count]
assert bytes(restored) == base
refusals = []
for name, address in (('changed-code', 0x20000), ('occupied-bridge', PREPARE_BRIDGE),
                      ('changed-language-data', 0x4d8000)):
    mutated = bytearray(pre_prepare)
    mutated[offset(pre_prepare, address, 1)] ^= 1
    try:
        patch_prepare_bridge(bytes(mutated), stock, profile=profile)
    except ValueError:
        refusals.append(name)
    else:
        raise AssertionError(name)
try:
    patch_prepare_bridge(pre_prepare, stock)
except ValueError:
    refusals.append('wrong-profile')
else:
    raise AssertionError('Built-in image accepted as the external-language profile')
# The restored native STX lifecycle and new Settings descriptor must survive.
for address, count in ((0x3a25c, 4), (0xec46c, 4), (0xec870, 4), (0x4d8000, 44)):
    at = offset(base, address, count)
    assert combined[at:at + count] == base[at:at + count]
assert len(combined) == len(base)
artifact = out / 'SpiderApp.builtin-player-met.analysis-only.elf'
artifact.write_bytes(combined)
report = dict(passed=True, analysis_only=True, ready_to_flash=False,
              device_accessed=False, firmware_package_created=False,
              base_sha256=BASE_SHA, candidate_sha256=hashlib.sha256(combined).hexdigest(),
              native_settings_profile=native_settings_profile,
              artifact=artifact.relative_to(ROOT).as_posix(), elf_growth_bytes=0,
              settings_resource_review=(settings_composition['out']/'report.json').relative_to(ROOT).as_posix() if native_settings_profile else None,
              native_language_lifecycle_preserved=True, settings_data_preserved=True,
              owner_edit=owner_edit, met_edit=met_edit, native_guards=checks,
              prepare_bridge_pending=False, prepare_edit=prepare_edit,
              undeclared_changes=False, refusals=refusals,
              historical_candidate_dependency=False, home_source_hashes=home_report['source_hashes'],
              source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
              limits=['No hardware boot, sleep/wake or partition qualification.',
                      'Paired host build and full firmware assembly remain separate checks.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
