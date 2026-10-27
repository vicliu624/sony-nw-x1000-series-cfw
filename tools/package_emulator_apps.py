"""Package the reviewed external apps and source; never connect to a player."""
from pathlib import Path
import hashlib,json,shutil,zipfile,struct,zlib
ROOT=Path(__file__).resolve().parents[1];firmware_version=(ROOT/'VERSION').read_text().strip();version=(ROOT/'runtime/apps/emulators/VERSION').read_text().strip();work=ROOT/'work/emulator-apps';test=json.loads((ROOT/'work/emulator-app-tests/report.json').read_text());assert test['passed']
out=ROOT/'dist'/firmware_version/'emulator-apps'/version;assert not out.exists(),'Preserve previous package';out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audio_test=json.loads((ROOT/'work/gbc-audio-integration/report.json').read_text());driver_test=json.loads((ROOT/'work/gbc-audio-research/native-dsp-ioctl.json').read_text());assert audio_test['passed'] and driver_test['passed']
reports=[]
for name in ['gbc','tamagotchi-id']:
 r=json.loads((work/name/'build.json').read_text());app=ROOT/r['artifact'];assert sha(app)==r['sha256']
 for source,digest in r['source_hashes'].items():assert sha(ROOT/source)==digest,source
 row=next(t for t in test['cases'] if t['case']==name+'-production-storage-rejection-and-touch-return');assert row['app_sha256']==sha(app)
 if name=='gbc':assert audio_test['production_app_sha256']==sha(app)
 shutil.copytree(work/name/'package',out/'PLAYER/HOMEBREW/apps'/name)
 for folder in ['roms','saves']:(out/'PLAYER/HOMEBREW/data'/name/folder).mkdir(parents=True)
 reports.append(r)
shutil.copyfile(ROOT/'docs/apps/EMULATORS.md',out/'README.md')
(out/'PREVIEW').mkdir()
for width,name in [(128,'tama-preview.png'),(160,'gbc-preview.png')]:
 raw=(ROOT/'work/emulator-app-tests'/f'render-{width}.rgb565').read_bytes();assert len(raw)==240*432*2;rgb=bytearray()
 for i in range(0,len(raw),2):
  value=int.from_bytes(raw[i:i+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 scan=b''.join(b'\0'+rgb[y*720:(y+1)*720]for y in range(432));(out/'PREVIEW'/name).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
(out/'REVIEW').mkdir();shutil.copyfile(ROOT/'work/emulator-app-tests/report.json',out/'REVIEW/tests.json')
shutil.copyfile(ROOT/'work/gbc-audio-integration/report.json',out/'REVIEW/audio-integration.json')
shutil.copyfile(ROOT/'work/gbc-audio-research/native-dsp-ioctl.json',out/'REVIEW/pcm-driver.json')
(out/'REVIEW/builds.json').write_text(json.dumps(reports,indent=2)+'\n')
# Source for both separately licensed executables; proprietary stock libraries excluded.
for folder in ['runtime/apps/emulators','runtime/native','runtime/platform','runtime/apps/diagnostics','third_party/gnuboy','third_party/tama-id']:
 shutil.copytree(ROOT/folder,out/'SOURCE'/folder,ignore=shutil.ignore_patterns('__pycache__','*.o'))
for n in ['start.c','start.S','stock_fs_bridge.c','stock_fs_bridge.h','stock_stat64.c','stock_stat64.h','target_abi.h']:
 p=out/'SOURCE/runtime/store'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'runtime/store'/n,p)
for n in ['test_gbc_schedule.c','test_pcm_owner.c','test_gbc_pcm.c','test_gbc_volume.c','test_gbc_audio_integration.py','check_gbc_pcm_driver.py','fixtures/gbc_pcm_preload.c','build_emulator_apps.py','test_emulator_apps.py','package_emulator_apps.py','test_emulator_cores.c','test_emulator_touch.c','test_emulator_render.c','test_tama_core.c','render_emulator_shells.c','fixtures/tama_memory_platform.c','fixtures/device_preload.c']:
 p=out/'SOURCE/tools'/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'tools'/n,p)
for name in ['fm_audio.c','fm_audio.h']:
 p=out/'SOURCE/runtime/apps/fm-radio'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'runtime/apps/fm-radio'/name,p)
(out/'SOURCE/VERSION').write_text(firmware_version+'\n')
(out/'NOTICE.txt').write_text('Two separate external executables. GB/GBC uses gnuboy (GPL-2.0; third_party/gnuboy/COPYING). Tamagotchi iD uses the tamaemu/Paramix derived core and A910 adapter (GPL-3.0; third_party/tama-id/core/LICENSE). Corresponding source is included under SOURCE. No commercial ROM, seed save, Sony binary, Python interpreter, firmware image or updater is included. App UI previews use synthetic pixels only.\n')
identity={'app_version':version,'project_version':firmware_version,'apps':[{k:r[k]for k in ['id','bytes','sha256']}for r in reports],'native_viewports':{'gbc':[40,48,160,144],'tamagotchi-id':[56,86,128,128]},'runtime':'C and existing ARM startup assembly, stock Sony libc','firmware_changes':False,'ROM_included':False,'hardware_tested':False,'virtual_buttons_tested':True,'one_to_one_renderer_tested':True,'audio_output':{'gbc':'OSS PCM with audio lead and bounded 30Hz presentation; alpha8 physical test pending','tamagotchi-id':False},'audio_integration_passed':True,'audio_error_details':'first failure stage, code, value; hardware cause not yet established','pcm_owner_probe':'separate diagnostics only, not compiled into GBC','session_handoff':'platform entry and original APF manager, candidate9'}
(out/'REVIEW/identity.json').write_text(json.dumps(identity,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
z=out.parent/('NW-X1000-emulator-apps-'+version+'.zip');assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,9)as a:
 for p in sorted(out.rglob('*')):
  if p.is_file():a.write(p,p.relative_to(out).as_posix())
  elif not any(p.iterdir()):a.writestr(p.relative_to(out).as_posix()+'/',b'')
with zipfile.ZipFile(z)as a:
 assert a.testzip() is None
 for p in out.rglob('*'):
  if p.is_file():assert a.read(p.relative_to(out).as_posix())==p.read_bytes()
print(json.dumps({'zip':str(z),'bytes':z.stat().st_size,'sha256':sha(z),**identity},indent=2))
