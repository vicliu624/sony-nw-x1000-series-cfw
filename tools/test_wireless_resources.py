"""Check unified labels against the pinned original resources; no device."""
import hashlib
import io
import json
import tarfile
import re
from app_registry import ROOT
from release_firmware import complete_wordings
from resources import append_stx, parse_stx
from wireless_resources import compose

raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
    wordings = {}
    for member in archive:
        if member.isfile() and member.name.startswith('./usr/local/share/gemini/res/stx/') and member.name.endswith('.stx'):
            data = archive.extractfile(member).read()
            for label in ('Homebrew', 'Homebrew unavailable.\nCheck HOMEBREW.', 'Wireless Remote'):
                data, _ = append_stx(data, label)
            wordings[member.name.rsplit('-', 1)[1][:-4]] = data
    swd = archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-100-00.swd').read()
    mode_layout = archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-139-00.swd').read()
complete_wordings(wordings)
original_mode_layout=mode_layout
result, layout, mode_layout, ids = compose(wordings, swd, mode_layout)
assert ids == dict(wifi=7311, espnow=7312, mode_title=7313)
for language, original in wordings.items():
    before, after = parse_stx(original), parse_stx(result[language])
    assert after[:len(before)] == before
    assert after[7310] == 'Wireless Remote' and after[7311:7313] == ['Wi-Fi', 'ESP-NOW']
assert b'tid.2:\t"tid-7312"' in mode_layout and b'tid.12:' not in layout
assert b'"tid-7313"' in layout
from test_native_settings_count import replay
native=replay((ROOT/'work/targets-jp/SpiderApp').read_bytes())
assert native['templates'][0x1d]['resource']==13900
third=re.search(rb'^tid\.2:\s*"tid-(\d+)"',mode_layout,re.M)
assert third, 'Native control0x1d uses sid-139-00: missing third option mapping'
assert all(parse_stx(data)[int(third[1])]=='ESP-NOW' for data in result.values())
refusals = []
for name, words, ui, choices in (('empty', {}, swd,original_mode_layout), ('duplicate', wordings, layout,mode_layout),
                       ('wrong-layout', wordings, b'',original_mode_layout),('wrong-choice-page',wordings,swd,b''),
                       ('different-counts', dict(wordings, mismatch=append_stx(next(iter(wordings.values())), 'extra')[0]), swd,original_mode_layout)):
    try:
        compose(words, ui, choices)
    except ValueError:
        refusals.append(name)
    else:
        raise AssertionError(name)
print(json.dumps(dict(passed=True, languages=len(result), resource_ids=ids,
                     refusals=refusals, original_text_preserved=True,
                     device_accessed=False, firmware_created=False), indent=2))
