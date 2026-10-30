"""Create a local paired demo bundle from verified offline builds. Never deploys."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,time,zipfile
ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'runtime/apps/glass-marble'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args()
 version=(APP/'VERSION').read_text().strip();out=(a.output or ROOT/'work/aqua-link-demo'/version).resolve()
 if not out.is_relative_to((ROOT/'work').resolve()) or out.exists():raise ValueError('Choose a new directory under project work')
 native=json.loads((ROOT/'work/glass-marble/build.json').read_text())
 fw=ROOT/'work/glass-marble-mosaico-firmware';firm=json.loads((fw/'build-receipt.json').read_text())
 if not native['built'] or native['version']!=version or not firm['built'] or firm['target']!='esp32s31':raise ValueError('Missing matching build')
 if not firm.get('stack_budget_passed'):raise ValueError('S31 task-stack regression must pass')
 for name,digest in native['app_inputs'].items():
  if sha(ROOT/name)!=digest:raise ValueError('Changed native build input: '+name)
 for name,digest in firm['inputs'].items():
  if sha(APP/name)!=digest:raise ValueError('Changed firmware build input: '+name)
 for name,digest in firm['outputs'].items():
  if sha(fw/name)!=digest:raise ValueError('Changed firmware output: '+name)
 for report in ('glass-marble-tests','glass-marble-owner-tests'):
  record=json.loads((ROOT/'work'/report/'report.json').read_text())
  if not record['passed']:raise ValueError('Missing offline pass: '+report)
  for name,digest in record.get('sources',record.get('source_hashes',{})).items():
   if sha(ROOT/name)!=digest:raise ValueError('Changed tested source: '+name)
 out.mkdir(parents=True)
 def copy(source,relative):
  target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 package=ROOT/'work/glass-marble/HOMEBREW/apps/glass-marble'
 if sha(package/'app')!=native['app_sha256'] or sha(package/'radio-worker')!=native['worker_sha256']:raise ValueError('Changed native binaries')
 for source in package.iterdir():
  if source.is_file():copy(source,Path('x1060/HOMEBREW/apps/glass-marble')/source.name)
 radio=ROOT/Path(native['radio_manifest']).parent
 manifest=json.loads((radio/'manifest.json').read_text())
 for name,key in [('sd8686.bin','candidate_sha256'),('helper_sd.bin','helper_sha256')]:
  source=radio/'candidate'/name
  if sha(source)!=manifest[key]:raise ValueError('Radio candidate mismatch')
  copy(source,Path('x1060/HOMEBREW/data/glass-marble/candidate')/name)
 for name in firm['outputs']:copy(fw/name,Path('mosaico')/name)
 for name in ('flash_args','flash_project_args'):
  if (fw/name).exists():copy(fw/name,Path('mosaico')/name)
 lock=ROOT/'work/glass-marble-mosaico-source/mosaico/dependencies.lock'
 if sha(lock)!=firm['dependencies_lock_sha256']:raise ValueError('Resolved dependency lock mismatch')
 copy(lock,'mosaico/dependencies.lock')
 for source,name in [(ROOT/'work/glass-marble/build.json','native-build.json'),(fw/'build-receipt.json','mosaico-build.json'),(radio/'manifest.json','radio-manifest.json'),(ROOT/'work/glass-marble-tests/report.json','physics-and-codec.json'),(ROOT/'work/glass-marble-owner-tests/report.json','owner-lifecycle.json')]:copy(source,Path('verification')/name)
 copy(ROOT/'work/glass-marble-tests/aqua-link-water-alpha2.gif','preview.gif')
 guide=(ROOT/'docs/apps/GLASS_MARBLE.md').read_text().replace('[BUILD](../BUILD.md)','the project build guide (`docs/BUILD.md`)')
 (out/'GUIDE.md').write_text(guide)
 for source in APP.rglob('*'):
  if source.is_file() and '__pycache__' not in source.parts:copy(source,Path('source/runtime/apps/glass-marble')/source.relative_to(APP))
 for name in ('tools/test_glass_marble.py','tools/test_glass_marble_owner.py','tools/test_aqua_stack_budget.py','tools/fixtures/glass_marble.c','tools/fixtures/glass_marble_owner.c','sources/esp-mosaico-glass-marble-sources.json'):
  copy(ROOT/name,Path('source')/name)
 for name in ('xnow_full.h','xnow_full.c','xnow_full_guard.h','xnow_full_guard.c','xnow_sd8686_full.h','xnow_sd8686_full.c','xnow_full_control.c','VERSION'):
  relative=Path('runtime/platform/espnow')/name;copy(ROOT/relative,Path('source')/relative)
 for name in ('tools/test_xnow_span_guard.c','tools/test_xnow_span_guard.py','tools/test_xnow_full_control.c','tools/test_xnow_full_integration.py','tools/fixtures/full_owner_ipc.c'):
  copy(ROOT/name,Path('source')/name)
 # Preserve vendor notices alongside this local firmware binary.
 bases=[('mosaico-bsp',ROOT/'work/mosaico-bsp'),('esp-idf',ROOT/'work/mosaico-idf'),('managed',ROOT/'work/glass-marble-mosaico-source/mosaico/managed_components')]
 for label,base in bases:
  for source in base.rglob('*'):
   if source.is_file() and '.git' not in source.parts and re.fullmatch(r'(LICENSE|LICENCE|COPYING|NOTICE)(\..*)?',source.name,re.I):copy(source,Path('licenses')/label/source.relative_to(base))
 for name in ('LICENSE','THIRD_PARTY.md'):
  if (ROOT/name).exists():copy(ROOT/name,Path('licenses/project')/name)
 (out/'README.txt').write_text('AQUA LINK '+version+' - LOCAL EXPERIMENTAL DEMO\n\n'
  'X1060: native application plus exact radio candidate on exposed user storage.\n'
  'A foreground managed launcher is required. This is not a Sony firmware update.\n'
  'Mosaico: ESP32-S31 firmware, bootloader, partition table and flashing metadata.\n'
  'The preview is a software simulation, not a recording of device operation.\n'
  'GUIDE.md explains mounting, millimetre calibration, controls and offline scope.\n\n'
  'This bundle was built and packaged on the PC; no device was written or flashed.\n'
  'Hardware interoperability, timing and full APF/USB/sleep lifecycle remain open.\n'
  'Retain factory/rollback inputs before separately authorized device installation.\n'
  'The X1060 radio files derive from local Sony inputs: keep this bundle local; do not publish it.\n'
  'The source overlay builds inside the full project; it is not a standalone SDK.\n')
 record={'version':version,'packaged':True,'published':False,'device_written':False,'hardware_tested':False,'managed_launcher_required':True,'deployable':False,'packager_sha256':sha(Path(__file__)),'native_app_sha256':native['app_sha256'],'mosaico_app_sha256':firm['outputs']['glass_marble.bin'],'packet_bytes':120}
 (out/'package.json').write_text(json.dumps(record,indent=2)+'\n')
 files=sorted(x for x in out.rglob('*') if x.is_file())
 (out/'files.sha256').write_text(''.join(sha(x)+'  '+x.relative_to(out).as_posix()+'\n' for x in files))
 archive=out.parent/('Aqua-Link-'+version+'-local-demo.zip')
 if archive.exists():archive=out.parent/('Aqua-Link-'+version+'-'+str(time.time_ns())+'.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for source in sorted(out.rglob('*')):
   if source.is_file():z.write(source,source.relative_to(out).as_posix())
 print(json.dumps({'folder':str(out),'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,**record},indent=2))
if __name__=='__main__':main()
