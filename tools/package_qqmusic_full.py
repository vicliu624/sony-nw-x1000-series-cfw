"""Package actual native full-import executable; local only, no player IO."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from market_metadata import descriptions
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',required=True);parser.add_argument('--name',required=True);parser.add_argument('--app-version',default=(ROOT/'runtime/apps/qqmusic/VERSION').read_text().strip());args=parser.parse_args()
assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+',args.app_version)
native=(ROOT/args.candidate).resolve();assert native.is_relative_to(ROOT/'work')
assert re.fullmatch(r'qqmusic-x1060-full-[0-9]+',args.name)
codec=ROOT/'work/qqmusic-codec'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
build=json.loads((native/'build.json').read_text());preview=bool(build.get('audio_preview_enabled'))
entry_report=ROOT/('work/qqmusic-preview-native-boot/report.json' if preview else 'work/qqmusic-device-full-check/report.json')
checks=json.loads(entry_report.read_text())
assert checks['passed'] and checks['candidate_sha256']==build['app_sha256']
if preview:
 pipeline_path=ROOT/'work/qqmusic-preview-pipeline/report.json';pipeline=json.loads(pipeline_path.read_text())
 assert pipeline['passed'] and pipeline['candidate_sha256']==build['app_sha256'] and len(pipeline['cases'])==6
 assert pipeline['actual_local_https_new_download'] and pipeline['actual_user_stage_receipt_source_decode_transport_client_service']
 for report in (checks,pipeline):
  for name,digest in report['fixture_sources'].items():assert sha(ROOT/name)==digest
assert build['imports_enabled'] and not build['host_session_fixture'] and sha(native/'app')==build['app_sha256']
for name,digest in build['sources'].items():assert sha(ROOT/name)==digest
binary=(native/'app').read_bytes();assert b'--host-session' not in binary and b'/dev/mock-user' not in binary and b'Imports remain disabled' not in binary
assert all(marker not in binary for marker in (b'cnmgr_init',b'cnmgr_fin',b'cnmgr_power_on',b'cnmgr_connect'))
assert all(marker in binary for marker in (b'wifi-helper',b'qq_wifi_ensure',b'qq_wifi_cancel',b'qq_wifi_close'))
helper=ROOT/'work/qqmusic-wifi/wifi-helper';helper_build=json.loads((helper.parent/'build.json').read_text());assert helper_build['built'] and sha(helper)==helper_build['helper_sha256']
for name,digest in helper_build['sources'].items():assert sha(ROOT/name)==digest
transport=json.loads((ROOT/'work/qqmusic-stock-daemon-transport/report.json').read_text());assert transport['passed'] and transport['original_daemon_handlers'] and {r['case'] for r in transport['cases']}=={'ready','borrowed','cancel','late_cancel'}
for name,digest in transport['source_hashes'].items():assert sha(ROOT/name)==digest
clock_check=json.loads((ROOT/'work/qqmusic-clock-gate/report.json').read_text());assert clock_check['passed'] and clock_check['candidate_sha256']==build['app_sha256']
wifi_check=json.loads((ROOT/'work/qqmusic-wifi-tests/report.json').read_text());assert wifi_check['passed']
for name,digest in wifi_check['source_hashes'].items():assert sha(ROOT/name)==digest
version=(ROOT/'VERSION').read_text().strip();out=ROOT/'dist'/version/args.name;out.mkdir(parents=True,exist_ok=False)
app=out/'HOMEBREW/apps/qqmusic';(app/'resources').mkdir(parents=True);(app/'lib').mkdir()
shutil.copyfile(native/'app',app/'app');(app/'app').chmod(0o755)
shutil.copyfile(helper,app/'wifi-helper');(app/'wifi-helper').chmod(0o755)
stock_manager=helper.parent/'libcnmgr.so.1';assert sha(stock_manager)==helper_build['stock_library_sha256'];shutil.copyfile(stock_manager,app/'lib/libcnmgr.so.1')
font=ROOT/'work/qqmusic-font/QQMusicUI.otf';assert sha(font)==FONT_SHA256;shutil.copyfile(font,app/'resources'/font.name)
for name,folder in [('libcares.so.2','stock-resolver-probe'),('librt.so.1','stock-resolver-probe'),('libpthread.so.0','stock-resolver-probe'),('libm.so.6','qqmusic-codec')]:shutil.copyfile(ROOT/'work'/folder/name,app/'lib'/name)
(app/'app.ini').write_text(f'api=1\nid=qqmusic\nname=QQ Music\nversion={args.app_version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={(app/"app").stat().st_size}\nsha256={sha(app/"app")}\n')
for suffix in ('svg','png'):shutil.copyfile(ROOT/'runtime/apps/qqmusic/assets'/('icon.'+suffix),app/('icon.'+suffix))
metadata=dict(descriptions()['qqmusic'],id='qqmusic',version=args.app_version)
if preview:metadata['changes']='Adds guarded 30-second previews, source preservation, stop/restore status and bounded PCM feeding. Native audio hardware acceptance remains pending.'
(app/'app-info.json').write_text(json.dumps(metadata,indent=2)+'\n')
(app/'files.sha256').write_text('HBFILES1\n'+''.join(f'{sha(p)} {p.stat().st_size} {p.relative_to(app).as_posix()}\n' for p in sorted(app.rglob('*')) if p.is_file()))
for name in ('HOMEBREW/data/qqmusic','MUSIC'):
    directory=out/name;directory.mkdir(parents=True);(directory/'.keep').write_bytes(b'')
shutil.copyfile(ROOT/'docs/apps/QQ_MUSIC.md',out/'README.md')
if preview:
 with (out/'README.md').open('a') as guide:
  guide.write('\n\n## Preview candidate '+args.app_version+'\n\nThis complete native candidate includes 30-second track previews alongside MGG-to-tagged-MP3 import. Software acceptance uses fresh synthetic HTTPS downloads; physical sound, timing and AudioC restoration still require acceptance. It is not marked hardware-qualified.\n\nMerge only HOMEBREW into the exposed user-storage root using the existing deployment method. Preserve existing HOMEBREW/data/qqmusic and MUSIC contents. This package does not include a launcher, firmware updater, account session or music. QQ Check is unchanged and is not included. SOURCE, REVIEW and LICENSES stay on the computer. No USB connection is required for network operation; disconnect USB storage ownership before launching.\n\nIn song details, use the preview button to prepare/download/play up to 30 seconds, and tap it again to stop. Import remains disabled until audio cleanup completes. Downloaded originals and public checksum receipts stay under HOMEBREW/data/qqmusic; exported MP3 files stay under MUSIC. Preview checks the reviewed installed software identity and refuses unknown configurations. It does not alter the system clock or write application data to the system partition.\n')
licenses=out/'LICENSES';licenses.mkdir()
for source,name in [('work/qqmusic-font/OFL.txt','Noto-OFL.txt'),('third_party/qqmusic-stb/LICENSE','stb-LICENSE.txt'),('work/external-tls-probe/bearssl-0.6/LICENSE.txt','BearSSL-LICENSE.txt'),('third_party/qqmusic-codecs/shine/COPYING','Shine-LGPL2.txt'),('third_party/qqmusic-codecs/tremor/COPYING','Tremor-COPYING.txt'),('third_party/qqmusic-codecs/ogg/COPYING','Ogg-COPYING.txt')]:shutil.copyfile(ROOT/source,licenses/name)
review=out/'REVIEW';review.mkdir();shutil.copyfile(native/'build.json',review/'build.json');shutil.copyfile(entry_report,review/'native-entry-check.json')
if preview:
 shutil.copyfile(pipeline_path,review/'preview-pipeline-check.json');shutil.copyfile(native/'profile-report.json',review/'preview-software-profile.json')
 shutil.copyfile(ROOT/'sources/qqmusic-font-subset.json',review/'font-subset.json')
else:
 for source,name in [('work/qqmusic-font-check/report.json','font-check.json'),('work/qqmusic-mapped-detach/report.json','mapped-detach.json'),('work/qqmusic-memory/report.json','memory-audit.json'),('sources/qqmusic-font-subset.json','font-subset.json')]:shutil.copyfile(ROOT/source,review/name)
shutil.copyfile(ROOT/'work/qqmusic-storage/report.json',review/'mount-parser-check.json')
if not preview:
 for source,name in [('work/qqmusic-touch/report.json','touch-feedback.json'),('work/qqmusic-network-diagnostic/report.json','network-diagnostic.json'),('sources/qqmusic-stock-wifi-ownership.json','stock-wifi-research.json')]:shutil.copyfile(ROOT/source,review/name)
for source,name in [('work/qqmusic-wifi/build.json','wifi-helper-build.json'),('work/qqmusic-wifi-tests/report.json','wifi-process-check.json'),('work/qqmusic-stock-daemon-transport/report.json','wifi-original-service-check.json'),('work/qqmusic-clock-gate/report.json','clock-gate-check.json')]:shutil.copyfile(ROOT/source,review/name)
if not preview:
 for source,name in [('work/qqmusic-runtime/report.json','cover-runtime-check.json'),('work/qqmusic-cover-job/report.json','cover-job-check.json'),('work/qqmusic-ui-native/report.json','ui-regression.json'),('work/qqmusic-clock-skew-checks/http-report.json','http-date-check.json')]:shutil.copyfile(ROOT/source,review/name)
if not preview:
 checker=ROOT/'dist/0.1.0-dev.16/qqmusic-startup-check-5/HOMEBREW/apps/qqcheck'
 assert checker.is_dir();shutil.copytree(checker,out/'HOMEBREW/apps/qqcheck')
 checker_out=out/'HOMEBREW/apps/qqcheck'
 checker_manifest=dict(line.split('=',1) for line in (checker_out/'app.ini').read_text().splitlines())
 checker_manifest['version']=args.app_version
 (checker_out/'app.ini').write_text(''.join(f'{key}={value}\n' for key,value in checker_manifest.items()))
 for suffix in ('svg','png'):shutil.copyfile(ROOT/'runtime/apps/qqcheck/assets'/('icon.'+suffix),checker_out/('icon.'+suffix))
 (checker_out/'files.sha256').write_text('HBFILES1\n'+''.join(f'{sha(p)} {p.stat().st_size} {p.relative_to(checker_out).as_posix()}\n' for p in sorted(checker_out.rglob('*')) if p.is_file() and p.name!='files.sha256'))
old=json.loads((ROOT/'work/qqmusic-live-session/session-wf6h8n75/native-final-check/build.json').read_text())
baseline={('runtime/apps/qqmusic/'+Path(p).name if p.startswith('runtime/apps/qqmusic_') else p):h for p,h in old['sources'].items()}
changed=sorted(p for p,h in build['sources'].items() if baseline.get(p)!=h)
# Source relocation invalidates historical equivalence; retain explicit differences.
source=out/'SOURCE';source.mkdir()
for name in build['sources'].keys()|helper_build['sources'].keys():
    assert not name.startswith('tools/fixtures/');target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
for folder in ('runtime/apps/qqmusic','runtime/native','runtime/store'):
    for path in (ROOT/folder).glob('*.h'):
        target=source/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
for folder in ('third_party/qqmusic-codecs','third_party/qqmusic-stb'):
    shutil.copytree(ROOT/folder,source/folder,dirs_exist_ok=True)
shutil.copytree(ROOT/'work/external-tls-probe/bearssl-0.6',source/'third_party/bearssl-0.6',ignore=shutil.ignore_patterns('build','.git'))
shutil.copyfile(native/'qqmusic_profile.h',source/'qqmusic_profile.h')
if preview:
 shutil.copyfile(native/'qqmusic_preview_profile.h',source/'qqmusic_preview_profile.h')
 for name in ('runtime/apps/qqmusic/build.py','runtime/apps/qqmusic/VERSION','tools/prepare_qqmusic_preview_profile.py'):
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
for name in ('tools/build_qqmusic_codec.py','tools/build_qqmusic_native.py','tools/build_qqmusic_wifi_helper.py','tools/subset_qqmusic_font.py','tools/prepare_qqmusic_font.py','tools/qqmusic_font_config.py','sources/qqmusic-codec-sources.json','sources/qqmusic-image-sources.json','sources/qqmusic-font-subset.json','sources/qqmusic-font-source.json','sources/qqmusic-cnmgr-api.json'):
    target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
(source/'objects').mkdir()
objects=[]
for i,name in enumerate(build['sources']):
    if Path(name).suffix not in ('.c','.S'):continue
    obj=codec/(str(i)+'-'+Path(name).stem+'.o');assert obj.is_file();shutil.copyfile(obj,source/'objects'/obj.name);objects.append('objects/'+obj.name)
shutil.copyfile(ROOT/'work/external-tls-probe/arm-build/libbearssl.a',source/'objects/libbearssl.a')
(source/'RELINK.json').write_text(json.dumps({'objects':objects,'additional_archive':'objects/libbearssl.a','compiler':'arm-linux-gnueabi-gcc','flags':['-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,--disable-new-dtags,-rpath,$ORIGIN/lib'],'stock_libraries':['libcares.so.2','librt.so.1','libm.so.6','libc.so.6','ld-linux.so.3'],'source_note':'Generated profile contains only this app installation identifiers and public CA roots, no account session. All source/build/relink content stays on PC.'},indent=2)+'\n')
lib=ROOT/'work/arm-signal-tests/lib'
for option,expected in [('--help','MGG download and tagged MP3 import enabled'),('--version',args.app_version)]:
    result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app/'app'),option],capture_output=True,text=True,check=True,timeout=10);assert expected in result.stdout
result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app/'wifi-helper'),'--help'],capture_output=True,text=True,check=True,timeout=10);assert 'Wi-Fi helper' in result.stdout
identity={'kind':'native full MGG-to-tagged-MP3 app; hardware acceptance pending','version':args.app_version,'native_wifi_acquisition':True,'wifi_control_withdrawn':False,'isolated_account_free_wifi_helper':True,'clock_error_prompt':True,'explicit_session_only_utc8_option':True,'system_clock_modified':False,'touch_feedback':True,'wifi_hardware_qualified':False,'font':{'filename':FONT_NAME,'bytes':FONT_BYTES,'sha256':FONT_SHA256},'imports_enabled':True,'hardware_qualified':False,'ready_to_flash':False,'host_adapter_included':False,'account_data_included':False,'all_persistent_app_data_under_verified_contents':True,'workspace':'/contents/HOMEBREW/data/qqmusic','music':'/contents/MUSIC','requires_usb_disconnected':True,'usb_driver_modified':False,'existing_homebrew_entry_required':True,'expected_mount_source':'/dev/mtdblock/2','live_pipeline_common_sources_changed':changed,'native_entry_checks_passed':True,'assembled_package_cli_passed':True,'app_sha256':sha(app/'app'),'wifi_helper_sha256':sha(app/'wifi-helper')}
identity['audio_preview_enabled']=preview
if preview:identity.update(preview_pipeline_synthetic_acceptance=True,preview_hardware_qualified=False,qqcheck_included=False)
(review/'package.json').write_text(json.dumps(identity,indent=2)+'\n')
(out/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(out).as_posix()}\n' for p in sorted(out.rglob('*')) if p.is_file()))
archive=out.parent/(out.name+'.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,6) as z:
    for p in sorted(out.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in out.rglob('*'):
        if p.is_file():assert z.read(p.relative_to(out).as_posix())==p.read_bytes()
    assert not any(name.endswith(('.upg','.private.json')) for name in z.namelist())
digest=sha(archive);Path(str(archive)+'.sha256').write_text(f'{digest}  {archive.name}\n')
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':digest,**identity},indent=2))
