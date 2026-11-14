"""Check the built-in localization/player SDK composition offline; no UPG."""
import hashlib
import io
import json
import sys
import time

from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_player_host import patch_owner_anchor
from build_player_met_anchor import patch_met_anchor
from builtin_language import SETTINGS_SHA, enable_home_settings
from player_prepare_bridge import (
    PREPARE_BRIDGE,
    build_builtin,
    patch_prepare_bridge,
    prepare_bridge,
)


def offset(raw, address, count):
    elf = ELFFile(io.BytesIO(raw))
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD'
                and s['p_vaddr'] <= address
                and address + count <= s['p_vaddr'] + s['p_filesz']]
    assert len(segments) == 1
    s = segments[0]
    return int(s['p_offset'] + address - s['p_vaddr'])


def check(base, combined, stock, profile):
    owner, _ = patch_owner_anchor(base)
    pre_prepare, _ = patch_met_anchor(owner, mapped_stub=0x4d7ff0)
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
    return refusals


if __name__ == '__main__':
    native_settings = '--native-settings' in sys.argv
    profile = 'native-settings' if native_settings else 'builtin-language'
    output_group = 'native-settings-player-composition' if native_settings else 'builtin-player-composition'
    out = ROOT / 'work' / output_group / str(time.time_ns())
    stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
    base, artifact, build_report = build_builtin(out, stock, native_settings=native_settings)
    expected_base = '0dbd8c94e1502173faa52bb96394ae9bcfdbb55e74b496e4a42eed95589d2ea3' if native_settings else SETTINGS_SHA
    assert hashlib.sha256(base).hexdigest() == expected_base
    refusals = check(base, artifact.read_bytes(), stock, profile)
    report = dict(build_report, passed=True, refusals=refusals,
                  native_language_lifecycle_preserved=True, settings_data_preserved=True,
                  prepare_bridge_pending=False, undeclared_changes=False,
                  historical_candidate_dependency=False,
                  source_sha256=hashlib.sha256((ROOT / 'tools/test_builtin_player_composition.py').read_bytes()).hexdigest(),
                  limits=['No hardware boot, sleep/wake or partition qualification.',
                          'Paired host build and full firmware assembly remain separate checks.'])
    if native_settings:
        from prepare_remote_settings_row import replay
        settings_report = ROOT / build_report['settings_resource_review']
        settings = json.loads(settings_report.read_text(encoding='utf-8'))
        home_dir = settings_report.parent / 'home'
        home_report = json.loads((home_dir / 'build.json').read_text(encoding='utf-8'))
        language_base = enable_home_settings(
            (home_dir / 'SpiderApp.feedback.analysis-only.elf').read_bytes(), home_report['symbols'])
        cases, list_cases = replay(language_base, base, int(settings['callback'], 16))
        report.update(arm_dispatch_cases=cases, native_list_replay_cases=list_cases)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
