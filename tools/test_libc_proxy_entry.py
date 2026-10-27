"""Feed original captured proxy argv into actual libc launcher ELF under QEMU."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import hashlib,json,re,shutil,subprocess,tempfile,argparse
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--registration-report',action='append');parser.add_argument('--report',default=str(evidence_path(ROOT,'native-libc-proxy-entry-tests.json').relative_to(ROOT)));options=parser.parse_args()
work=work_area(ROOT,'libc-proxy-entry-review')
composition=composition_path(ROOT);manifest=json.loads((composition/'manifest.json').read_text())
app=composition/'external/HOMEBREW/launcher/app';row=next(r for r in manifest['files'] if r['path']=='external/HOMEBREW/launcher/app');assert hashlib.sha256(app.read_bytes()).hexdigest()==row['sha256']
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
assert not Path('/dev/fb/0').exists() and not Path('/dev/icx_touch_screen').exists()
reports=options.registration_report or ['sources/native-manager-proxy-exec-request.json','sources/native-manager-proxy-noargs-exec.json'];cases=[]
tracked=[Path(__file__),composition/'manifest.json',app,lib/'libc.so.6',lib/'ld-linux.so.3']
with tempfile.TemporaryDirectory(dir=work) as temporary:
 prefix=Path(temporary);(prefix/'lib').mkdir()
 for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
 display=prefix/'dev/fb/0';display.parent.mkdir(parents=True);display.write_bytes(b'ORDINARY FILE')
 apps=prefix/'contents/HOMEBREW/apps';shutil.copytree(composition/'external/HOMEBREW/apps',apps)
 for relative in reports:
  captured=verify_report(ROOT,relative);tracked.append(ROOT/relative)
  for entry in captured['cases']:
   requests=entry['proxy_registration']['activation']['captured_frontend_exec_requests'];assert len(requests)==1
   request=requests[0];argv=request['argv'];assert request['path']==argv[0]=='/contents/HOMEBREW/launcher/app'
   run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-0',argv[0],'-strace',str(app),*argv[1:]],capture_output=True,text=True,timeout=15)
   assert run.returncode==2,(argv,run.returncode,run.stderr)
   found=re.search(r'open\("/dev/fb/0",[^\n]* = (\d+)',run.stderr);assert found,run.stderr
   tail=run.stderr[found.end():];assert 'close('+found.group(1)+') = 0' in tail
   assert '/dev/icx_touch_screen' not in tail and display.read_bytes()==b'ORDINARY FILE'
   cases.append({'target':entry['target'],'argv':argv,'exit':2,'entered_native_mode':True,'unsupported_display_closed':True,'trace':run.stderr})
 negative=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-0','unregistered-name','-strace',str(app)],capture_output=True,text=True,timeout=15)
 assert negative.returncode==64 and '/dev/fb/0' not in negative.stderr
report={'passed':True,'actual_candidate_sha256':row['sha256'],'original_proxy_captured_argv_cases':cases,'negative_control_exit':64,'hardware_tested':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'limits':['Original proxy argv capture is reused after source validation, not real process scheduling.','Actual current ELF and stock loader/libc execute under QEMU; display is a regular-file failure fixture.','No successful UI entry, Sony return, physical USB or device execution qualification.']}
output=(ROOT/options.report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
stamp_report(ROOT,report)
output.write_text(json.dumps(report,indent=2)+'\n');print(f'Actual libc launcher accepted {len(cases)} original proxy argv cases; negative control rejected; display cleaned up.')


