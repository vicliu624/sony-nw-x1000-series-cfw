"""Actual libc launcher ELF against a regular-file QEMU display, not hardware."""
from pathlib import Path
import hashlib,json,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];build=ROOT/'work/libc-launcher-review/build.json';metadata=json.loads(build.read_text());app=ROOT/metadata['artifact'];assert hashlib.sha256(app.read_bytes()).hexdigest()==metadata['sha256']
lib=ROOT/'work/arm-signal-tests/lib';work=ROOT/'work/libc-device-failure-review';work.mkdir(exist_ok=True)
assert not Path('/dev/fb/0').exists() and not Path('/dev/icx_touch_screen').exists()
with tempfile.TemporaryDirectory(dir=work) as temporary:
 prefix=Path(temporary);fake=prefix/'dev/fb/0';fake.parent.mkdir(parents=True);fake.write_bytes(b'ORDINARY FILE')
 run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),'--native',str(ROOT/'work/libc-launcher-review/apps')],capture_output=True,text=True,timeout=15)
 assert run.returncode==2,(run.returncode,run.stderr)
 opened=re.search(r'open\("/dev/fb/0",[^\n]* = (\d+)',run.stderr);assert opened,run.stderr
 fd=opened.group(1);tail=run.stderr[opened.end():]
 assert re.search(r'ioctl\('+fd+r',[^\n]*errno=25',tail) and 'close('+fd+') = 0' in tail
 assert '/dev/icx_touch_screen' not in tail and fake.read_bytes()==b'ORDINARY FILE'
 report={'passed':True,'candidate_sha256':metadata['sha256'],'actual_candidate_failure_exit':2,'display_closed':True,'touch_not_opened':True,'fixture_unchanged':True,'trace':run.stderr,'hardware_tested':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),build,lib/'libc.so.6',lib/'ld-linux.so.3']},'limits':['Actual ELF only unsupported display path; no successful physical rendering or handoff.']}
 (ROOT/'sources/native-libc-device-failure-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Actual libc launcher: ENOTTY display failure closes descriptor; no touch or writes.')
