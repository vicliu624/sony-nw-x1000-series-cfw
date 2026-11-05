"""Check Settings localization and omission of the legacy Language app; PC only."""
import contextlib,io,json,time
from app_registry import ROOT
from build_release import player_setup_files
from release_firmware import build
from test_builtin_firmware import audit

policy=json.loads((ROOT/'config/release.json').read_text());assert 'language' not in policy['apps']
out=ROOT/'work/language-retirement-review'/str(time.time_ns());out.mkdir(parents=True)
launcher=out/'launcher';repository=out/'repository';apps=out/'apps'
for folder,name in ((launcher,'app'),(repository,'repository.conf'),(apps/'store','app'),(apps/'language','app')):
 folder.mkdir(parents=True,exist_ok=True);(folder/name).write_bytes(b'fixture')
setup=player_setup_files(launcher,repository,apps)
assert set(setup)=={'HOMEBREW/launcher/app','HOMEBREW/repository/repository.conf','HOMEBREW/apps/store/app'}
with contextlib.redirect_stdout(io.StringIO()):
 firmware,build_report=build(out/'firmware',out/'player',builtin_localization=True)
 report=audit(firmware)
assert build_report['native_language_settings'] and not build_report['external_language_files_generated']
assert not (out/'player/HOMEBREW/languages').exists()
report.update(legacy_language_app_published=False,legacy_language_app_in_setup=False,external_language_files_generated=False,firmware_installed=False)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix(),legacy_app_in_release=False,legacy_app_in_setup=False,stock_settings_language=True,device_accessed=False),indent=2))
