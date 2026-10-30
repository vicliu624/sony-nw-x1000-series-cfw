"""Assemble an explicitly non-deployable local review; no player/network IO."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/chat-managed-review-kit'
if OUT.exists():raise ValueError('Review directory already exists; preserve the previous snapshot')
chat=ROOT/'work/espnow-chat-app';launcher=ROOT/'work/chat-managed-launcher-dev3-review'
build=json.loads((chat/'build.json').read_text());check=json.loads((launcher/'chat-check.json').read_text())
assert build['version']=='0.1.0-dev.3' and build['device_written'] is False and build['deployable'] is False
for section in ('source_hashes','owner_sources','linked_library_sources'):
    for name,digest in build[section].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
assert check['passed'] and not check['hardware_qualified']
folder=chat/'HOMEBREW/apps/espnow-chat'
for name,digest in check['chat_files_sha256'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
assert hashlib.sha256((launcher/'launcher.elf').read_bytes()).hexdigest()==check['launcher_sha256']
process=json.loads((ROOT/'work/chat-managed-process/report.json').read_text());assert process['passed']
for name,digest in process['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
rollback=ROOT/'work/espnow-chat-known-running-20261028/HOMEBREW/apps/espnow-chat'
expected={'app':'34a84f2af68957772ea22e04cc7a053528159da39c72f575b6ed5a3109bca713','radio-worker':'77d0a92af2ec9d96770c4caa34fc6adbdf6f4792b2218e393356b4592318b083'}
for name,digest in expected.items():assert hashlib.sha256((rollback/name).read_bytes()).hexdigest()==digest
OUT.mkdir()
shutil.copytree(folder,OUT/'CANDIDATE/espnow-chat')
shutil.copy2(launcher/'launcher.elf',OUT/'CANDIDATE/launcher-review.elf')
shutil.copytree(rollback,OUT/'ROLLBACK/espnow-chat-dev2')
evidence=OUT/'EVIDENCE';evidence.mkdir()
for source,name in [(chat/'build.json','chat-build.json'),(launcher/'build.json','launcher-build.json'),(launcher/'chat-check.json','arm-contract-check.json'),(ROOT/'work/chat-managed-process/report.json','host-process-check.json'),(ROOT/'work/chat-ui-owner-eof/report.json','ui-eof-check.json')]:shutil.copy2(source,evidence/name)
(OUT/'READ_FIRST.md').write_text('''# Local review only — do not deploy

This snapshot pairs chatdev.3 with the managed-radio launcher review. It is not
a complete ESP-NOW implementation or an install/flash package. No updater,
automatic installation or radio-image loading command is included.

CANDIDATE contains the ARM chat/worker and separate launcher review. ROLLBACK
contains the identified running dev.2 chat files. These files do not provide a
verified rollback for the currently installed launcher: its live identity could
not be read because the Terminal connection timed out. Do not replace it.

Offline evidence covers compiled ARM CLI/render/catalog/contract checks and
host fork/exec with actual chat-client/owner code. Delayed modeled recovery keeps
foreground after UI SIGKILL; owner crash without DONE keeps foreground uncertain.
Radio/cnmgr effects, user mount distinction and test worker path are substituted.
Physical graphical HOME, APF deadlines, USB, sleep and network restoration remain
unqualified. Normal manager state does not prove current AP/Terminal reachability.

The player was not changed by snapshot assembly. Before any live candidate test,
first restore authenticated Terminal access, identify and preserve the installed
launcher, review the exact test scope, and keep RF/image changes disabled until
the non-radio lifecycle path has passed. Existing SDKalpha.7 archives are unchanged.
''')
files={p.relative_to(OUT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.rglob('*') if p.is_file()}
report={'review_only':True,'deployable':False,'chat_version':build['version'],'launcher_rollback_verified':False,'chat_rollback_hashes_verified':True,'physical_lifecycle_qualified':False,'device_written':False,'firmware_created':False,'files':files}
(OUT/'REVIEW_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'review_directory':str(OUT.relative_to(ROOT)),'files':len(files),'deployable':False,'launcher_rollback_verified':False,'device_written':False},indent=2))
